import os
import json
import time
import pandas as pd
import streamlit as st
from alerts import send_sos, LOG

SETTINGS = "settings.json"
LIVE = "alerts/live.jpg"
STATUS = "alerts/status.json"

st.set_page_config(page_title="Baby Safety SOS", layout="wide")
st.markdown("""
<style>
.stApp {background:#FFF5F7;}
[data-testid="stSidebar"] {background:#FFE4EC;}
h1,h2,h3 {color:#5A3E4B;}
.card {background:#FFE4EC; border-radius:18px; padding:18px 22px; border:1px solid #F8BBD0; color:#5A3E4B; margin-bottom:12px;}
.danger {background:#FF8A9B; color:white; border-color:#FF8A9B;}
.stButton>button {background:#F48FB1; color:white; border:none; border-radius:12px;}
</style>""", unsafe_allow_html=True)


def load():
    d = {"armed": True, "camera": 0, "guardian": "Parent", "phone": "",
         "conf": 0.30, "near_px": 80, "hold_secs": 1.5, "cooldown": 60,
         "cry_on": True, "cry_thr": 0.35, "cry_secs": 6.0, "cry_cooldown": 120.0}
    try:
        with open(SETTINGS) as f:
            d.update(json.load(f))
    except Exception:
        pass
    d["phone"] = ""
    return d


def show_table(df):
    try:
        st.dataframe(df, width="stretch", hide_index=True)
    except TypeError:  # older Streamlit versions
        st.dataframe(df, use_container_width=True, hide_index=True)


cfg = load()
st.title("Baby Safety SOS")
st.caption("Live dashboard. Monitoring runs in monitor.py, so alerts keep working even if this page is closed.")

with st.sidebar:
    st.header("Monitor")
    cfg["armed"] = st.toggle("Camera monitoring ON", value=cfg["armed"])
    cfg["camera"] = int(st.number_input("Camera index", 0, 5, int(cfg["camera"])))
    st.header("Guardian")
    cfg["guardian"] = st.text_input("Name", cfg["guardian"])
    st.header("Hazard detection")
    cfg["conf"] = st.slider("Confidence threshold", 0.1, 0.9, float(cfg["conf"]), 0.05)
    cfg["near_px"] = st.slider("Hand-to-object distance (px)", 10, 150, int(cfg["near_px"]), 5)
    cfg["hold_secs"] = st.slider("Hold time before alert (sec)", 0.5, 5.0, float(cfg["hold_secs"]), 0.5)
    cfg["cooldown"] = st.slider("Cooldown between alerts (sec)", 10, 300, int(cfg["cooldown"]), 10)
    st.header("Cry detection")
    cfg["cry_on"] = st.toggle("Listen for crying", value=cfg["cry_on"])
    cfg["cry_thr"] = st.slider("Cry sensitivity threshold", 0.1, 0.9, float(cfg["cry_thr"]), 0.05)
    cfg["cry_secs"] = st.slider("Crying must last (sec)", 2.0, 20.0, float(cfg["cry_secs"]), 1.0)
    cfg["cry_cooldown"] = st.slider("Cry alert cooldown (sec)", 30, 600, int(cfg["cry_cooldown"]), 30)
    custom = os.path.exists("runs/detect/baby_hazard/weights/best.pt")
    st.caption("Model: custom-trained" if custom else "Model: pretrained COCO")
    if st.button("Send test alert"):
        st.info(send_sos("", cfg["guardian"], "test alert - ignore this", 0.0))

with open(SETTINGS, "w") as f:
    json.dump(cfg, f)


@st.fragment(run_every=1)
def live_view():
    col_feed, col_side = st.columns([3, 2])
    try:
        with open(STATUS) as f:
            s = json.load(f)
    except Exception:
        s = {}
    stale = time.time() - s.get("updated", 0) > 6
    state = s.get("state", "")

    if stale:
        text = "Monitor not running. Start it with: python monitor.py"
        danger = True
    elif state == "paused":
        text = "Camera monitoring is paused"
        danger = False
    elif state == "camera_error":
        text = "Cannot read camera. Retrying..."
        danger = True
    elif state in ("holding", "alert_sent"):
        hazard = str(s.get("hazard", "")).replace("_", " ")
        held = s.get("held_for", 0)
        text = "Holding " + hazard + " (" + str(held) + "s)"
        if state == "alert_sent":
            text = text + " - SOS SENT"
        danger = True
    else:
        text = "All clear. Watching..."
        danger = False

    last_alert = s.get("alert_time")
    if not last_alert:
        last_alert = "none yet"
    css = "card danger" if danger else "card"
    html = "<div class='" + css + "'><h3>" + text + "</h3>"
    html = html + "<p>Last alert: " + str(last_alert) + "</p></div>"

    cry_status = str(s.get("cry_status", "not started"))
    cry_score = float(s.get("cry_score", 0.0))
    cry_thr = float(cfg["cry_thr"])
    if stale:
        cry_text, cry_danger = "Cry detection offline", False
    elif cry_status.startswith(("unavailable", "microphone error")):
        cry_text, cry_danger = "Cry detection: " + cry_status[:120], True
    elif cry_status == "off":
        cry_text, cry_danger = "Cry detection is off", False
    elif cry_status.startswith("starting"):
        cry_text, cry_danger = "Cry detection loading the audio model...", False
    elif cry_score >= cry_thr:
        cry_text, cry_danger = "Crying sound detected", True
    else:
        cry_text, cry_danger = "Listening. No crying", False
    cry_css = "card danger" if cry_danger else "card"
    cry_html = "<div class='" + cry_css + "'><h3>" + cry_text + "</h3>"
    cry_html = cry_html + "<p>Cry level: " + format(cry_score, ".2f") + " (alert from " + format(cry_thr, ".2f") + ")</p></div>"

    with col_feed:
        if os.path.exists(LIVE) and not stale:
            with open(LIVE, "rb") as f:
                st.image(f.read(), caption=str(s.get("ms", 0)) + " ms/frame")
    with col_side:
        st.markdown(html, unsafe_allow_html=True)
        st.markdown(cry_html, unsafe_allow_html=True)
        st.subheader("Alert history")
        try:
            df = pd.read_csv(LOG).iloc[::-1].head(10)
        except FileNotFoundError:
            df = None
        if df is None:
            st.caption("No alerts yet")
        else:
            show_table(df)


live_view()