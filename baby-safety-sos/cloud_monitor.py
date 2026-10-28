"""Per-browser-session camera and microphone monitoring for the Streamlit app."""

import queue
import threading
import time

import cv2
import numpy as np
from scipy.signal import resample_poly

from alerts import send_sos


AUDIO_MODEL = "MIT/ast-finetuned-audioset-10-10-0.4593"
AUDIO_RATE = 16000
AUDIO_WINDOW_SECONDS = 5
_VIDEO_LOCK = threading.Lock()
_AUDIO_LOCK = threading.Lock()
_AUDIO_INFERENCE_LOCK = threading.Lock()
_VIDEO_DETECTOR = None
_AUDIO_RESOURCES = None


def _get_audio_resources():
    global _AUDIO_RESOURCES
    with _AUDIO_LOCK:
        if _AUDIO_RESOURCES is None:
            import torch
            from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

            torch.set_num_threads(1)
            extractor = AutoFeatureExtractor.from_pretrained(AUDIO_MODEL)
            model = AutoModelForAudioClassification.from_pretrained(AUDIO_MODEL).eval()
            labels = model.config.id2label
            cry_ids = [
                index for index, label in labels.items()
                if "cry" in label.lower() or "whimper" in label.lower()
            ]
            if not cry_ids:
                raise RuntimeError("The audio model has no crying labels.")
            _AUDIO_RESOURCES = (torch, extractor, model, cry_ids)
        return _AUDIO_RESOURCES


class BrowserMonitor:
    def __init__(self):
        self._lock = threading.RLock()
        self._config = {}
        self._video_error = None
        self._video_retry_after = 0.0
        self._video_last_run = 0.0
        self._hold_start = None
        self._last_seen = 0.0
        self._last_hazard_alert = 0.0
        self._last_cry_alert = 0.0
        self._status = {
            "state": "waiting",
            "cry_status": "not started",
            "cry_score": 0.0,
            "updated": time.time(),
        }
        self._audio_queue = queue.Queue(maxsize=10)
        self._audio_thread = None
        self._audio_active = threading.Event()
        self._audio_error = None

    def update_config(self, config):
        with self._lock:
            self._config = dict(config)

    def get_status(self):
        with self._lock:
            return dict(self._status)

    def _update_status(self, **values):
        with self._lock:
            self._status.update(values)
            self._status["updated"] = time.time()

    def process_video(self, frame):
        now = time.monotonic()
        with self._lock:
            config = dict(self._config)

        if not config.get("armed", True):
            self._update_status(state="paused", hazard="", held_for=0.0)
            return frame

        if now < self._video_retry_after:
            return frame
        if now - self._video_last_run < 0.25:
            return frame
        self._video_last_run = now

        try:
            global _VIDEO_DETECTOR
            with _VIDEO_LOCK:
                if _VIDEO_DETECTOR is None:
                    from detector import HazardDetector
                    _VIDEO_DETECTOR = HazardDetector(
                        conf=float(config.get("conf", 0.30)),
                        near_px=int(config.get("near_px", 80)),
                    )
                _VIDEO_DETECTOR.conf = float(config.get("conf", 0.30))
                _VIDEO_DETECTOR.near_px = int(config.get("near_px", 80))
                image = frame.to_ndarray(format="bgr24")
                annotated, holding = _VIDEO_DETECTOR.process(image)
        except Exception as error:
            self._video_error = str(error)
            self._video_retry_after = now + 30.0
            self._update_status(state="video_error", error=self._video_error)
            return frame
        self._video_error = None

        state, hazard, held_for = "clear", "", 0.0
        alert = None
        if holding:
            self._hold_start = self._hold_start or time.time()
            self._last_seen = time.time()
            hazard, confidence = max(holding, key=lambda item: item[1])
            held_for = time.time() - self._hold_start
            state = "holding"
            if (
                held_for >= float(config.get("hold_secs", 1.5))
                and time.time() - self._last_hazard_alert
                >= float(config.get("cooldown", 60))
            ):
                self._last_hazard_alert = time.time()
                state = "alert_sent"
                alert = (
                    config.get("phone", ""),
                    config.get("guardian", "Parent"),
                    hazard,
                    confidence,
                    annotated.copy(),
                )
        elif self._hold_start and time.time() - self._last_seen > 1.0:
            self._hold_start = None

        self._update_status(
            state=state,
            hazard=hazard,
            held_for=round(held_for, 1),
            error=None,
        )
        if alert:
            threading.Thread(target=self._send_alert, args=alert, daemon=True).start()

        return type(frame).from_ndarray(annotated, format="bgr24")

    def process_audio(self, frame):
        with self._lock:
            cry_on = self._config.get("cry_on", True)
        if not cry_on:
            self._audio_active.clear()
            self._update_status(cry_status="off", cry_score=0.0)
            return frame

        self._audio_active.set()
        if self._audio_error:
            self._update_status(cry_status="unavailable: " + self._audio_error)
            return frame
        if self._audio_thread is None or not self._audio_thread.is_alive():
            self._audio_thread = threading.Thread(target=self._run_audio, daemon=True)
            self._audio_thread.start()

        try:
            samples = frame.to_ndarray()
            channels = len(frame.layout.channels)
            if samples.ndim == 2:
                samples = samples.mean(axis=0 if samples.shape[0] == channels else 1)
            if np.issubdtype(samples.dtype, np.integer):
                samples = samples.astype(np.float32) / max(
                    abs(np.iinfo(samples.dtype).min), np.iinfo(samples.dtype).max
                )
            else:
                samples = samples.astype(np.float32)
            if frame.sample_rate != AUDIO_RATE:
                from math import gcd
                common = gcd(frame.sample_rate, AUDIO_RATE)
                samples = resample_poly(
                    samples, AUDIO_RATE // common, frame.sample_rate // common
                ).astype(np.float32)
            self._audio_queue.put_nowait(samples)
        except queue.Full:
            try:
                self._audio_queue.get_nowait()
                self._audio_queue.put_nowait(samples)
            except queue.Empty:
                pass
        except Exception as error:
            self._audio_error = str(error)
            self._update_status(cry_status="microphone error: " + self._audio_error)
        return frame

    def stop_audio(self):
        self._audio_active.clear()
        self._audio_error = None
        while True:
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break
        self._update_status(cry_status="stopped")

    def stop_video(self):
        with self._lock:
            self._hold_start = None
            self._video_last_run = 0.0
        self._update_status(state="stopped")

    def _send_alert(self, *args, **kwargs):
        try:
            result = send_sos(*args, **kwargs)
            self._update_status(alert_result=result)
        except Exception as error:
            self._update_status(alert_result="Alert delivery failed: " + str(error))

    def _run_audio(self):
        try:
            torch, extractor, model, cry_ids = _get_audio_resources()
        except Exception as error:
            self._audio_error = str(error)
            self._update_status(cry_status="unavailable: " + self._audio_error)
            return

        window_size = AUDIO_RATE * AUDIO_WINDOW_SECONDS
        audio = np.zeros(0, dtype=np.float32)
        cry_since = None
        last_cry = 0.0
        next_check = time.monotonic()
        self._update_status(cry_status="listening")

        while self._audio_active.is_set():
            try:
                chunk = self._audio_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            audio = np.concatenate((audio, chunk))[-window_size:]
            if len(audio) < window_size or time.monotonic() < next_check:
                continue
            next_check = time.monotonic() + 2.0
            level = float(np.sqrt(np.mean(audio ** 2)))
            try:
                if level < 0.005:
                    score = 0.0
                else:
                    inputs = extractor(audio, sampling_rate=AUDIO_RATE, return_tensors="pt")
                    with _AUDIO_INFERENCE_LOCK:
                        with torch.no_grad():
                            logits = model(**inputs).logits[0]
                    score = float(torch.sigmoid(logits)[cry_ids].max())
            except Exception as error:
                self._audio_error = str(error)
                self._update_status(cry_status="audio inference error: " + self._audio_error)
                return

            with self._lock:
                config = dict(self._config)
            threshold = float(config.get("cry_thr", 0.35))
            self._update_status(cry_status="listening", cry_score=score)
            now = time.time()
            if not config.get("cry_on", True):
                cry_since = None
            elif score >= threshold:
                last_cry = now
                cry_since = cry_since or now
                if (
                    now - cry_since >= float(config.get("cry_secs", 6.0))
                    and now - self._last_cry_alert
                    >= float(config.get("cry_cooldown", 120.0))
                ):
                    self._last_cry_alert = now
                    threading.Thread(
                        target=self._send_alert,
                        args=(
                            config.get("phone", ""),
                            config.get("guardian", "Parent"),
                            "crying",
                            score,
                        ),
                        kwargs={"kind": "cry"},
                        daemon=True,
                    ).start()
            elif cry_since and now - last_cry > 4:
                cry_since = None
