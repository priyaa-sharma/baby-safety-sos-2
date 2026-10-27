import os
import json
import time
import threading
import cv2
from detector import HazardDetector
from alerts import send_sos

SETTINGS, LIVE, STATUS = "settings.json", "alerts/live.jpg", "alerts/status.json"
DEFAULTS = {"armed": True, "camera": 0, "guardian": "Parent", "phone": "",
            "conf": 0.30, "near_px": 80, "hold_secs": 1.5, "cooldown": 60}


def load_settings():
    s = dict(DEFAULTS)
    try:
        with open(SETTINGS) as f:
            s.update(json.load(f))
    except Exception:
        pass
    return s


def write_status(**d):
    d["updated"] = time.time()
    try:
        with open(STATUS + ".tmp", "w") as f:
            json.dump(d, f)
        os.replace(STATUS + ".tmp", STATUS)
    except Exception:
        pass


def write_live(frame):
    try:
        cv2.imwrite("alerts/live_tmp.jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 65])
        os.replace("alerts/live_tmp.jpg", LIVE)
    except Exception:
        pass


class Grabber:
    """Reads the camera in its own thread so we always process the NEWEST frame (no lag)."""

    def __init__(self, idx):
        backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
        self.cap = cv2.VideoCapture(int(idx), backend)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.frame, self.n, self.broken, self.alive = None, 0, False, True
        self.started = time.time()
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        fails = 0
        while self.alive:
            ok, f = self.cap.read()
            if ok:
                fails = 0
                with self.lock:
                    self.frame, self.n = f, self.n + 1
            else:
                fails += 1
                if fails > 30:
                    self.broken = True
                    break
                time.sleep(0.05)

    def get(self):
        with self.lock:
            return self.frame, self.n

    def stop(self):
        self.alive = False
        self.thread.join(timeout=1.5)
        self.cap.release()


def main():
    os.makedirs("alerts", exist_ok=True)
    print("Loading models...")
    det = HazardDetector()
    print("Monitoring started. Press Ctrl+C to stop.")
    grab, cam, last_n = None, None, -1
    s, last_cfg = load_settings(), 0.0
    hold_start, last_seen, last_alert, last_alert_time = None, 0.0, 0.0, None

    while True:
        now = time.time()
        if now - last_cfg > 2:  # pick up dashboard setting changes live
            s, last_cfg = load_settings(), now
            det.conf, det.near_px = float(s["conf"]), int(s["near_px"])

        if not s["armed"]:
            if grab:
                grab.stop()
                grab = None
            write_status(state="paused", alert_time=last_alert_time)
            time.sleep(1)
            continue

        if grab is None or cam != s["camera"]:
            if grab:
                grab.stop()
            grab, cam, last_n = Grabber(s["camera"]), s["camera"], -1

        frame, n = grab.get()
        no_frames = frame is None and time.time() - grab.started > 5
        if grab.broken or no_frames:
            write_status(state="camera_error", alert_time=last_alert_time)
            grab.stop()
            grab = None
            time.sleep(3)
            continue
        if frame is None or n == last_n:
            time.sleep(0.01)
            continue
        last_n = n

        t0 = time.time()
        out, holding = det.process(frame)
        now = time.time()
        state, hazard, held_for = "clear", "", 0.0

        if holding:
            hold_start = hold_start or now
            last_seen = now
            hazard, conf = max(holding, key=lambda h: h[1])
            held_for = now - hold_start
            state = "holding"
            if held_for >= float(s["hold_secs"]) and now - last_alert >= float(s["cooldown"]):
                last_alert, last_alert_time = now, time.strftime("%H:%M:%S")
                state = "alert_sent"
                threading.Thread(target=send_sos, daemon=True,
                                 args=(s["phone"], s["guardian"], hazard, conf, out.copy())).start()
        elif hold_start and now - last_seen > 1.0:  # tolerate brief detection gaps
            hold_start = None

        write_live(out)
        write_status(state=state, hazard=hazard, held_for=round(held_for, 1),
                     ms=round((time.time() - t0) * 1000), alert_time=last_alert_time)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Stopped.")