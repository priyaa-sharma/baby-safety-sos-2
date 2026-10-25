import time
import threading

SR, WIN, HOP = 16000, 5, 2  # sample rate, window seconds, check every N seconds
MODEL = "MIT/ast-finetuned-audioset-10-10-0.4593"


class CryDetector:
    def __init__(self, on_cry):
        self.on_cry = on_cry
        self.enabled, self.thr, self.secs, self.cooldown = True, 0.35, 6.0, 120.0
        self.score, self.level, self.status = 0.0, 0.0, "starting (loading audio model)..."
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            import numpy as np
            import torch
            import sounddevice as sd
            from transformers import AutoFeatureExtractor, AutoModelForAudioClassification
            extractor = AutoFeatureExtractor.from_pretrained(MODEL)
            model = AutoModelForAudioClassification.from_pretrained(MODEL).eval()
        except Exception as e:
            self.status = f"unavailable: {e}"
            return

        ids = [i for i, l in model.config.id2label.items()
               if "cry" in l.lower() or "whimper" in l.lower()]
        audio = np.zeros(SR * WIN, dtype=np.float32)
        lock = threading.Lock()

        def callback(indata, frames, t, status):
            nonlocal audio
            x = indata[:, 0]
            with lock:
                audio = np.concatenate([audio[len(x):], x])

        last_alert, cry_since, last_cry = 0.0, None, 0.0
        try:
            with sd.InputStream(samplerate=SR, channels=1, dtype="float32",
                                blocksize=1600, callback=callback):
                self.status = "listening"
                while True:
                    time.sleep(HOP)
                    if not self.enabled:
                        self.status, self.score, cry_since = "off", 0.0, None
                        continue
                    self.status = "listening"
                    with lock:
                        clip = audio.copy()
                    self.level = float(np.sqrt(np.mean(clip ** 2)))
                    if self.level < 0.005:  # near-silence: skip the model
                        self.score = 0.0
                    else:
                        inputs = extractor(clip, sampling_rate=SR, return_tensors="pt")
                        with torch.no_grad():
                            logits = model(**inputs).logits[0]
                        self.score = float(torch.sigmoid(logits)[ids].max())
                    now = time.time()
                    if self.score >= self.thr:
                        last_cry = now
                        cry_since = cry_since or now
                        if now - cry_since >= self.secs and now - last_alert >= self.cooldown:
                            last_alert = now
                            threading.Thread(target=self.on_cry, args=(self.score,), daemon=True).start()
                    elif cry_since and now - last_cry > 4:  # tolerate pauses between sobs
                        cry_since = None
        except Exception as e:
            self.status = f"microphone error: {e}"