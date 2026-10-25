"""SOS delivery: Telegram (photo), ntfy push, optional Twilio. Saves snapshots + CSV history."""
import os
import csv
import datetime as dt
import requests
import cv2
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


def _ntfy(msg):
    topic = os.getenv("NTFY_TOPIC")
    if not topic:
        return None
    requests.post(f"https://ntfy.sh/{topic}", data=msg.encode("utf-8"),
                  headers={"Title": "Baby Safety SOS", "Priority": "urgent", "Tags": "rotating_light"},
                  timeout=10).raise_for_status()
    return "ntfy"


def _twilio(msg, phone, guardian):
    sid, token, sender = (os.getenv(k) for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER"))
    if not (sid and token and sender and phone and len(phone) > 5):
        return None
    from twilio.rest import Client
    c = Client(sid, token)
    c.messages.create(to=phone, from_=sender, body=msg)
    c.calls.create(to=phone, from_=sender,
                   twiml=f"<Response><Say voice='alice' loop='2'>Hello {guardian}. {msg}</Say></Response>")
    return "twilio call+sms"


def send_sos(phone, guardian, hazard, conf, frame=None):
    ts = dt.datetime.now()
    snap = ""
    if frame is not None:
        snap = f"{SNAP_DIR}/{ts:%Y%m%d_%H%M%S}.jpg"
        cv2.imwrite(snap, frame)

    msg = f"SOS! Your baby is holding a {hazard.replace('_', ' ')} at {ts:%H:%M:%S}. Please check now."
    sent, errors = [], []
    for name, fn in (("telegram", lambda: _telegram(msg, snap)),
                     ("ntfy", lambda: _ntfy(msg)),
                     ("twilio", lambda: _twilio(msg, phone, guardian))):
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