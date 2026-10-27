import os
import json
import time
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from alerts import send_sos, LOG

SETTINGS = "settings.json"
LIVE = "alerts/live.jpg"
STATUS = "alerts/status.json"

LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 72"><path d="M32 2 L58 12 V36 C58 54 46 66 32 70 C18 66 6 54 6 36 V12 Z" fill="#4CBB17"/><path d="M32 50 C20 41 17 34 17 29 C17 24 21 21 25 21 C28 21 31 23 32 26 C33 23 36 21 39 21 C43 21 47 24 47 29 C47 34 44 41 32 50 Z" fill="#293325"/></svg>"""


def show_logo():
    try:
        st.image(LOGO_SVG, width="stretch")
    except Exception:
        st.image(LOGO_SVG, use_container_width=True)


st.set_page_config(page_title="Baby Safety SOS", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;500;600;700&display=swap');

html, body, .stApp, .stMarkdown, h1, h2, h3, h4, p, label, button, input, textarea,
[data-testid="stWidgetLabel"], [data-testid="stCaptionContainer"], .card, .hero, .note {
    font-family: 'Quicksand', sans-serif;
}
h1 {font-weight:700;}
h2, h3 {font-weight:700;}

.stApp {background:#293325; color:#EAF3E4;}
[data-testid="stSidebar"] {background:#39542C;}
[data-testid="stSidebar"] [data-baseweb="input"] > div {background:#293325;}
h1 {color:#4CBB17;}
h2,h3 {color:#EAF3E4;}
.card {background:#39542C; border-radius:16px; padding:18px 22px; border:1px solid #48872B;
       border-left:8px solid #4CBB17; color:#EAF3E4; margin-bottom:12px;}
.card h3 {margin:0 0 6px 0; color:#EAF3E4;}
.card p {margin:0; color:#CFE3C4;}
.danger {background:#E8590C; border-color:#E8590C; border-left-color:#FFFFFF; color:#FFFFFF;}
.danger h3, .danger p {color:#FFFFFF;}
.stButton>button {background:#4CBB17; color:#1B2418; font-weight:700; border:none; border-radius:10px;}
.stButton>button:hover {background:#48872B; color:#FFFFFF;}

.hero {text-align:center; padding:10px 10px 20px 10px;}
.hero h1 {font-size:64px; margin:0; color:#4CBB17; font-weight:700;}
.hero .tag {font-size:22px; color:#EAF3E4; margin-top:10px;}
.hero .desc {max-width:760px; margin:18px auto 0 auto; font-size:17px; line-height:1.7; color:#CFE3C4;}
.note {text-align:center; max-width:760px; margin:30px auto 0 auto; color:#9DB890; font-size:14px;}
</style>""", unsafe_allow_html=True)

if "started" not in st.session_state:
    st.session_state.started = False


# ---------------------------------------------------------------- landing page
if not st.session_state.started:
    st.markdown("""
    <style>
    [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display:none;}
    </style>
    <div style="height:50px;"></div>
    """, unsafe_allow_html=True)

    _, logo_col, _ = st.columns([5, 1, 5])
    with logo_col:
        show_logo()

    st.markdown("""
    <div class="hero">
      <h1>Baby Safety SOS</h1>
      <div class="tag">An AI guardian that watches over your baby when you can't.</div>
      <div class="desc">
        When a baby is left alone for a little while, small things can turn dangerous quickly.
        Baby Safety SOS watches through the camera and listens through the microphone.
        If your baby picks up something harmful like scissors or a knife, or keeps crying,
        you get an alert with a photo on your phone automatically, so you can act right away.
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.write("")
    _, mid, _ = st.columns([2, 1, 2])
    with mid:
        if st.button("Start", use_container_width=True):
            st.session_state.started = True
            st.rerun()
    st.write("")

    # ---- flip cards
    components.html("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;500;600;700&display=swap');
    body {margin:0; background:transparent; font-family:'Quicksand',sans-serif;}
    .row {display:flex; gap:24px; padding:8px 4px;}
    .flip {flex:1; height:250px; perspective:1000px; cursor:pointer;}
    .inner {position:relative; width:100%; height:100%; transition:transform .6s; transform-style:preserve-3d;}
    .flip.on .inner {transform:rotateY(180deg);}
    .face {position:absolute; inset:0; box-sizing:border-box; border-radius:16px; padding:24px;
           display:flex; flex-direction:column; justify-content:center; align-items:center; text-align:center;
           backface-visibility:hidden; -webkit-backface-visibility:hidden;}
    .front {background:#39542C; border:1px solid #48872B; border-top:6px solid #4CBB17;}
    .front h3 {margin:0; font-size:28px; color:#EAF3E4; font-weight:700;}
    .back {background:#4CBB17; transform:rotateY(180deg);}
    .back p {margin:0; font-size:16px; line-height:1.6; font-weight:600; color:#1B2418;}
    </style>
    <div class="row">
      <div class="flip"><div class="inner">
        <div class="face front"><h3>Hazard detection</h3></div>
        <div class="face back"><p>Computer vision spots dangerous objects, and pose tracking checks whether your baby's hand is actually holding one. An object lying on a table does not trigger an alarm.</p></div>
      </div></div>
      <div class="flip"><div class="inner">
        <div class="face front"><h3>Cry detection</h3></div>
        <div class="face back"><p>An audio AI model listens for crying and alerts you when it continues for several seconds, so a short fuss doesn't wake your phone.</p></div>
      </div></div>
      <div class="flip"><div class="inner">
        <div class="face front"><h3>Instant alerts</h3></div>
        <div class="face back"><p>A Telegram message with a snapshot reaches you within seconds, with an optional voice call. No buttons to press, it all runs by itself.</p></div>
      </div></div>
    </div>
    <script>
    document.querySelectorAll('.flip').forEach(function (c) {
      c.addEventListener('click', function () { c.classList.toggle('on'); });
    });
    </script>
    """, height=290)

    st.write("")
    st.markdown("<h2 style='text-align:center;'>How it works</h2>", unsafe_allow_html=True)

    # ---- scroll-reveal steps + phone mockup
    components.html("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;500;600;700&display=swap');
    body {margin:0; background:transparent; font-family:'Quicksand',sans-serif; color:#EAF3E4;}
    .wrap {display:flex; flex-wrap:wrap; align-items:center; justify-content:center; gap:50px; padding:10px 10px 20px 10px;}
    .steps {flex:1; min-width:300px; max-width:520px;}
    .step {display:flex; gap:18px; position:relative; padding-bottom:34px;}
    .step:last-child {padding-bottom:0;}
    .step:not(:last-child)::before {content:""; position:absolute; left:21px; top:46px; bottom:2px;
        width:2px; background:#48872B;}
    .num {flex:none; width:44px; height:44px; line-height:44px; text-align:center; border-radius:50%;
        background:#4CBB17; color:#1B2418; font-weight:700; font-size:20px;}
    .step h4 {margin:2px 0 4px 0; font-size:20px; color:#EAF3E4; font-weight:700;}
    .step p {margin:0; color:#CFE3C4; line-height:1.6; font-size:16px;}

    .rv {opacity:0; transform:translateX(-36px); transition:opacity .7s ease, transform .7s ease;}
    .rv.right {transform:translateX(44px);}
    .rv.in {opacity:1; transform:none;}

    .phone {width:250px; height:460px; border:8px solid #1B2418; border-radius:38px; background:#293325;
        box-shadow:0 18px 40px rgba(0,0,0,.45); overflow:hidden; position:relative;}
    .notch {position:absolute; top:0; left:50%; transform:translateX(-50%); width:90px; height:18px;
        background:#1B2418; border-radius:0 0 14px 14px; z-index:2;}
    .bar {background:#39542C; padding:30px 14px 10px 14px; display:flex; align-items:center; gap:10px;
        border-bottom:1px solid #48872B;}
    .av {width:30px; height:30px; border-radius:50%; background:#4CBB17; color:#1B2418; font-weight:700;
        text-align:center; line-height:30px; font-size:14px;}
    .bar b {font-size:14px;}
    .bar small {display:block; color:#9DB890; font-size:11px;}
    .chat {padding:14px 12px;}
    .bubble {background:#39542C; border:1px solid #48872B; border-radius:14px 14px 14px 4px; padding:8px;
        opacity:0; transform:translateY(14px) scale(.96);}
    .phone.in .bubble {animation:pop .5s ease .9s forwards;}
    @keyframes pop {to {opacity:1; transform:none;}}
    .bubble svg {width:100%; border-radius:9px; display:block;}
    .bubble p {margin:8px 2px 2px 2px; font-size:13px; line-height:1.45; color:#EAF3E4; font-weight:600;}
    .bubble .t {text-align:right; color:#9DB890; font-size:11px; font-weight:500; margin-top:2px;}
    </style>

    <div class="wrap">
      <div class="steps">
        <div class="step rv"><div class="num">1</div><div>
          <h4>Set up the camera</h4>
          <p>Point the camera at the baby's play area and start the monitor.</p></div></div>
        <div class="step rv"><div class="num">2</div><div>
          <h4>The AI watches and listens</h4>
          <p>Every frame is checked for hazards and the microphone listens for crying, all on your own computer.</p></div></div>
        <div class="step rv"><div class="num">3</div><div>
          <h4>You get an alert</h4>
          <p>If something looks dangerous, your phone gets a message with a photo within seconds.</p></div></div>
      </div>

      <div class="phone rv right" id="phone">
        <div class="notch"></div>
        <div class="bar"><div class="av">B</div><div><b>Baby Safety SOS</b><small>bot</small></div></div>
        <div class="chat">
          <div class="bubble">
            <svg viewBox="0 0 220 135" xmlns="http://www.w3.org/2000/svg">
              <rect width="220" height="135" fill="#1F2A1C"/>
              <circle cx="75" cy="52" r="22" fill="#48872B"/>
              <rect x="45" y="76" width="60" height="50" rx="16" fill="#48872B"/>
              <rect x="104" y="60" width="62" height="36" fill="none" stroke="#E8590C" stroke-width="3"/>
              <rect x="104" y="44" width="86" height="16" fill="#E8590C"/>
              <text x="109" y="56" font-size="11" font-weight="700" fill="#FFFFFF" font-family="sans-serif">HOLDING scissors 0.87</text>
            </svg>
            <p>SOS! Your baby is holding a scissors at 14:32:10. Please check now.</p>
            <div class="t">14:32</div>
          </div>
        </div>
      </div>
    </div>

    <script>
    var els = document.querySelectorAll('.rv');
    els.forEach(function (e, i) { e.style.transitionDelay = (i * 0.2) + 's'; });
    if ('IntersectionObserver' in window) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); }
        });
      }, {threshold: 0.2});
      els.forEach(function (e) { io.observe(e); });
    } else {
      els.forEach(function (e) { e.classList.add('in'); });
    }
    </script>
    """, height=560)

    st.markdown("""<div class="note">Baby Safety SOS is a safety assistant and not a replacement for adult
        supervision. Video and audio are processed on your own device and are never uploaded.</div>""",
                unsafe_allow_html=True)
    st.markdown("<div style='text-align:center; margin:18px 0 40px 0; color:#4CBB17; font-weight:700; letter-spacing:3px; font-size:15px;'> — PRIYA SHARMA</div>", unsafe_allow_html=True)
    st.stop()


# ------------------------------------------------------------------- dashboard
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
head_logo, head_title = st.columns([1, 14], vertical_alignment="center")
with head_logo:
    show_logo()
with head_title:
    st.markdown('<h1 style="margin:0;">Baby Safety SOS</h1>', unsafe_allow_html=True)
st.caption("Live dashboard. Monitoring runs in monitor.py, so alerts keep working even if this page is closed.")

with st.sidebar:
    if st.button("Back to home"):
        st.session_state.started = False
        st.rerun()
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