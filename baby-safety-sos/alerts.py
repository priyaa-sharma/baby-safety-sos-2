"""SOS delivery: Telegram photo, Telegram voice call (CallMeBot), optional ntfy push."""
import os
import csv
import datetime as dt
import requests
from dotenv import load_dotenv

load_dotenv()
LOG, SNAP_DIR = "alerts/log.csv", "alerts/snapshots"
os.makedirs(SNAP_DIR, exist_ok=True)


def _telegram(msg, snap):
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return None
    base = f"https://api.telegram.org/bot{token}"
    if snap:
        with open(snap, "rb") as f:
            r = requests.post(f"{base}/sendPhoto", data={"chat_id": chat, "caption": msg},
                              files={"photo": f}, timeout=20)
    else:
        r = requests.post(f"{base}/sendMessage", data={"chat_id": chat, "text": msg}, timeout=15)
    r.raise_for_status()
    return "telegram"


def _call(text):
    user = os.getenv("CALLMEBOT_USER")
    if not user:
        return None
    r = requests.get("http://api.callmebot.com/start.php",
                     params={"user": user, "text": text[:250], "lang": "en-US-Standard-B"}, timeout=30)
    r.raise_for_status()
    return "telegram call"


def _ntfy(msg):
    topic = os.getenv("NTFY_TOPIC")
    if not topic:
        return None
    requests.post(f"https://ntfy.sh/{topic}", data=msg.encode("utf-8"),
                  headers={"Title": "Baby Safety SOS", "Priority": "urgent", "Tags": "rotating_light"},
                  timeout=10).raise_for_status()
    return "ntfy"


def send_sos(phone, guardian, hazard, conf, frame=None, kind="hazard"):
    ts = dt.datetime.now()
    snap = ""
    if frame is not None:
        import cv2  # imported here so the online dashboard doesn't need OpenCV
        snap = f"{SNAP_DIR}/{ts:%Y%m%d_%H%M%S}.jpg"
        cv2.imwrite(snap, frame)

    if kind == "cry":
        msg = f"Your baby has been crying for a while (sound confidence {conf:.2f}) at {ts:%H:%M:%S}. Please check."
        spoken = "Alert. Your baby has been crying for a while. Please check now."
    else:
        msg = (
            f"SOS! Your baby is holding a {hazard.replace('_', ' ')} at "
            f"{ts:%H:%M:%S}. Please check now."
        )
        spoken = f"Alert. Your baby is holding {hazard.replace('_', ' ')}. Please check now."

    sent, errors = [], []
    for name, fn in (("telegram", lambda: _telegram(msg, snap)),
                     ("telegram call", lambda: _call(spoken)),
                     ("ntfy", lambda: _ntfy(msg))):
        try:
            r = fn()
            if r:
                sent.append(r)
        except Exception as e:
            errors.append(f"{name} failed: {e}")
    status = ("sent via " + ", ".join(sent)) if sent else "demo (no alert channel configured, nothing sent)"
    if errors:
        status += " | " + "; ".join(errors)

    os.makedirs("alerts", exist_ok=True)
    new = not os.path.exists(LOG)
    with open(LOG, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "hazard", "confidence", "status", "snapshot"])
        w.writerow([ts.strftime("%Y-%m-%d %H:%M:%S"), hazard, f"{conf:.2f}", status, snap])
    return status