import os
import json
import time
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import httpx
from supabase_auth.errors import AuthApiError
from streamlit.errors import StreamlitSecretNotFoundError
from auth import (
    build_password_reset_url,
    create_password_reset_token,
    discard_password_reset_token,
    password_reset_token_valid,
    reset_password,
    send_password_reset_email,
)
from alerts import send_sos, LOG
from src.supabase_client import create_supabase_client

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
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "Sign in"
if "auth_notice" not in st.session_state:
    st.session_state.auth_notice = ""
if "auth_email" not in st.session_state:
    st.session_state.auth_email = ""
if "supabase_client" not in st.session_state:
    st.session_state.supabase_client = create_supabase_client()
supabase = st.session_state.supabase_client

session_error = None
try:
    supabase_session = supabase.auth.get_session()
except AuthApiError as error:
    supabase_session = None
    session_error = "Could not verify your Supabase session: " + error.message
except httpx.HTTPError:
    supabase_session = None
    session_error = "Could not connect to Supabase to verify your session."

google_authenticated = getattr(st.user, "is_logged_in", False)
if supabase_session:
    st.session_state.authenticated = True
    st.session_state.user_name = getattr(
        getattr(supabase_session, "user", None), "email", "Supabase user"
    )
elif google_authenticated:
    st.session_state.authenticated = True
    st.session_state.user_name = getattr(st.user, "name", "Google user")
else:
    st.session_state.authenticated = False
    st.session_state.pop("user_name", None)

reset_token = st.query_params.get("reset", "")
if reset_token:
    st.session_state.auth_mode = "Reset password"
    st.session_state.authenticated = False
    st.session_state.started = True


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
        If your baby picks up something harmful like a medicine strip or razor, or keeps crying,
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
              <text x="109" y="56" font-size="11" font-weight="700" fill="#FFFFFF" font-family="sans-serif">HOLDING razor 0.87</text>
            </svg>
            <p>SOS! Your baby is holding a razor at 14:32:10. Please check now.</p>
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


# --------------------------------------------------------------------- sign in
if not st.session_state.authenticated:
    st.markdown("""
    <style>
    [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display:none;}
    header[data-testid="stHeader"] {background:transparent;}
    .stApp {background:#f7f8f5; color:#242a24;}
    [data-testid="stMain"] > div {max-width:1120px; padding-top:2rem;}
    .auth-copy {padding:40px 32px 32px 8px; color:#354238;}
    .auth-copy .eyebrow {color:#63846b; font-size:12px; font-weight:700; letter-spacing:2px; text-transform:uppercase;}
    .auth-copy h1 {color:#1f2922; font-size:42px; line-height:1.15; margin:14px 0;}
    .auth-copy p {color:#68756b; font-size:16px; line-height:1.7; max-width:440px;}
    .auth-art {margin:28px 0 0; padding:24px; border-radius:28px; background:#edf2eb;
       border:1px solid #e1e9df; text-align:center;}
    .auth-art svg {width:100%; max-width:340px; height:auto;}
    .st-key-auth_panel {background:#fff; border:1px solid #e8ebe6; border-radius:24px;
       box-shadow:0 18px 55px rgba(37,54,39,.08); padding:32px 36px 26px;}
    .st-key-auth_panel h2 {text-align:center; color:#202720; font-size:32px; margin:0 0 4px;}
    .st-key-auth_panel > [data-testid="stMarkdownContainer"] > p {text-align:center; color:#7c847d; font-size:14px; margin:0 0 20px;}
    [data-testid="stTextInput"] label {display:none;}
    [data-testid="stTextInput"] input {background:#fff; border:1px solid #e2e6e1; border-radius:12px;
       min-height:46px; color:#000 !important; -webkit-text-fill-color:#000;}
    [data-testid="stTextInput"] input::placeholder {color:#000 !important; opacity:1;}
    [data-testid="stTextInput"] input:focus {border-color:#6f9476; box-shadow:0 0 0 1px #6f9476;}
    [data-testid="stFormSubmitButton"] button {background:#202720; color:#fff; border:0;
       border-radius:999px; min-height:44px; font-weight:700;}
    [data-testid="stFormSubmitButton"] button:hover {background:#354638; color:#fff;}
    .st-key-google_auth button {background:#fff; color:#000; border:1px solid #e2e6e1;
       border-radius:12px; min-height:44px;}
    .st-key-google_auth button:hover {background:#f7f8f5; color:#000; border-color:#cdd5cc;}
    .auth-divider {display:flex; align-items:center; gap:12px; color:#929991;
       font-size:12px; margin:18px 0;}
    .auth-divider:before, .auth-divider:after {content:""; height:1px; background:#e8ebe6; flex:1;}
    .auth-foot {text-align:center; color:#737c74; font-size:13px;}
    .st-key-auth_switch button {background:transparent; color:#000; border:0; padding:0;
       font-weight:700; min-height:0;}
    .st-key-auth_switch button:hover {background:transparent; color:#000; text-decoration:underline;}
    .st-key-forgot_password button {background:transparent; color:#000; border:0; padding:0;
       font-size:12px; min-height:0;}
    .st-key-forgot_password button:hover {background:transparent; color:#000; text-decoration:underline;}
    .st-key-back_to_login button {background:transparent; color:#000; border:0; padding:0;
       font-weight:700; min-height:0;}
    .st-key-back_to_login button:hover {background:transparent; color:#000; text-decoration:underline;}
    @media (max-width:760px) {
      [data-testid="stMain"] > div {padding:1rem 1rem 2rem;}
      .auth-copy {padding:4px 8px 8px;}
      .auth-copy h1 {font-size:32px;}
      .auth-art {display:none;}
      .st-key-auth_panel {padding:26px 20px 20px;}
    }
    </style>
    """, unsafe_allow_html=True)

    intro, form_col = st.columns([1.05, 0.95], gap="large", vertical_alignment="center")
    with intro:
        st.markdown("""
        <div class="auth-copy">
          <div class="eyebrow">Baby Safety SOS</div>
          <h1>A little more peace of mind.</h1>
          <p>Sign in to keep an eye on what matters most. Your camera and microphone are
          processed on your own computer, never uploaded.</p>
          <div class="auth-art">
            <svg viewBox="0 0 360 250" role="img" aria-label="Illustration of a protected baby">
              <circle cx="180" cy="126" r="104" fill="#dfeadd"/>
              <path d="M180 31l62 23v55c0 49-29 83-62 99-33-16-62-50-62-99V54z" fill="#709678"/>
              <path d="M180 176c-31-23-44-39-44-57 0-13 9-22 22-22 10 0 18 5 22 14 4-9 12-14 22-14 13 0 22 9 22 22 0 18-13 34-44 57z" fill="#f7f8f5"/>
              <circle cx="74" cy="65" r="8" fill="#d5aa72"/><circle cx="291" cy="179" r="11" fill="#d5aa72"/>
              <path d="M54 177c13-13 26-13 39 0M271 66c12-12 24-12 36 0" fill="none" stroke="#b3c9b2" stroke-width="5" stroke-linecap="round"/>
              <circle cx="91" cy="124" r="4" fill="#709678"/><circle cx="278" cy="112" r="4" fill="#709678"/>
            </svg>
          </div>
        </div>
        """, unsafe_allow_html=True)

    with form_col:
        with st.container(key="auth_panel"):
            mode = st.session_state.auth_mode
            heading = {
                "Sign in": "Welcome",
                "Sign up": "Create account",
                "Forgot password": "Forgot password?",
                "Reset password": "Choose a new password",
            }[mode]
            subtitle = {
                "Sign in": "Log in to your account or sign up",
                "Sign up": "Create an account to get started",
                "Forgot password": "We'll email you a secure link to reset it.",
                "Reset password": "Choose a new password for your account.",
            }[mode]
            st.markdown(
                "<h2>" + heading + "</h2><p>" + subtitle + "</p>",
                unsafe_allow_html=True,
            )
            if st.session_state.auth_notice:
                st.success(st.session_state.auth_notice)
                st.session_state.auth_notice = ""
            if session_error:
                st.error(session_error)

            if mode == "Reset password" and not password_reset_token_valid(reset_token):
                st.error("This reset link has expired or was already used. Request a new one.")
                if st.button("Request another reset link", key="back_to_login"):
                    st.session_state.auth_mode = "Forgot password"
                    st.query_params.clear()
                    st.rerun()
            else:
                form_key = "password_reset_form" if mode == "Reset password" else (
                    "forgot_password_form" if mode == "Forgot password" else "local_auth_form"
                )
                with st.form(form_key, clear_on_submit=False):
                    name = ""
                    email = ""
                    password = ""
                    confirm_password = ""
                    if mode == "Sign up":
                        name = st.text_input("Name", placeholder="Your name")
                    if mode in ("Sign in", "Sign up", "Forgot password"):
                        email = st.text_input(
                            "Email",
                            placeholder="Email",
                            key="auth_email" if mode in ("Sign in", "Sign up") else None,
                        )
                    if mode in ("Sign in", "Sign up", "Reset password"):
                        password = st.text_input("Password", placeholder="Password", type="password")
                    if mode in ("Sign up", "Reset password"):
                        confirm_password = st.text_input(
                            "Confirm password", placeholder="Confirm password", type="password"
                        )
                    button_text = "Send reset link" if mode == "Forgot password" else (
                        "Update password" if mode == "Reset password" else mode
                    )
                    submitted = st.form_submit_button(button_text, use_container_width=True)

                if submitted:
                    if mode == "Sign up":
                        if password != confirm_password:
                            st.error("Those passwords do not match.")
                        else:
                            try:
                                response = supabase.auth.sign_up({
                                    "email": email.strip(),
                                    "password": password,
                                    "options": {
                                        "data": {"name": name.strip()},
                                        "email_redirect_to": os.getenv(
                                            "SUPABASE_AUTH_REDIRECT_URL",
                                            os.getenv("APP_BASE_URL", "http://localhost:8501"),
                                        ),
                                    },
                                })
                            except AuthApiError as error:
                                st.error(error.message)
                            except httpx.HTTPError:
                                st.error("Could not connect to Supabase. Please try again.")
                            else:
                                if response.session:
                                    try:
                                        supabase.auth.sign_out()
                                    except AuthApiError as error:
                                        st.error(
                                            "Account created, but could not clear the sign-in "
                                            "session: " + error.message
                                        )
                                        st.stop()
                                    except httpx.HTTPError:
                                        st.error(
                                            "Account created, but could not clear the sign-in "
                                            "session. Please try signing out."
                                        )
                                        st.stop()
                                st.session_state.authenticated = False
                                st.session_state.started = True
                                st.session_state.auth_mode = "Sign in"
                                st.session_state.auth_notice = (
                                    "Your account has been created. Please check your email "
                                    "and verify your address before logging in."
                                )
                                st.rerun()
                    elif mode == "Sign in":
                        try:
                            response = supabase.auth.sign_in_with_password({
                                "email": email.strip(),
                                "password": password,
                            })
                        except AuthApiError as error:
                            st.error(error.message)
                        except httpx.HTTPError:
                            st.error("Could not connect to Supabase. Please try again.")
                        else:
                            if response.session:
                                st.session_state.authenticated = True
                                st.session_state.started = True
                                metadata = getattr(response.user, "user_metadata", {}) or {}
                                st.session_state.user_name = metadata.get(
                                    "name", response.user.email
                                )
                                st.rerun()
                            else:
                                st.error("Supabase did not return an active sign-in session.")
                    elif mode == "Forgot password":
                        token = create_password_reset_token(email)
                        if token:
                            try:
                                base_url = os.getenv("APP_BASE_URL", "http://localhost:8501")
                                reset_url = build_password_reset_url(base_url, token)
                                send_password_reset_email(email.strip().lower(), reset_url)
                            except (OSError, RuntimeError, ValueError) as error:
                                discard_password_reset_token(token)
                                st.error("Could not send the reset email. " + str(error))
                            else:
                                st.session_state.auth_notice = (
                                    "If an account exists for that email, a password reset link "
                                    "has been sent. Check your inbox."
                                )
                                st.rerun()
                        else:
                            st.session_state.auth_notice = (
                                "If an account exists for that email, a password reset link "
                                "has been sent. Check your inbox."
                            )
                            st.rerun()
                    elif mode == "Reset password":
                        if password != confirm_password:
                            st.error("Those passwords do not match.")
                        else:
                            success, message = reset_password(reset_token, password)
                            if success:
                                st.query_params.clear()
                                st.session_state.auth_mode = "Sign in"
                                st.session_state.auth_notice = message + " Please sign in."
                                st.rerun()
                            else:
                                st.error(message)

            if mode in ("Sign in", "Sign up"):
                if mode == "Sign in":
                    _, forgot_col = st.columns([2, 1])
                    with forgot_col:
                        with st.container(key="forgot_password"):
                            if st.button("Forgot password?", use_container_width=True):
                                st.session_state.auth_mode = "Forgot password"
                                st.rerun()
                st.markdown('<div class="auth-divider">or</div>', unsafe_allow_html=True)
                with st.container(key="google_auth"):
                    if st.button("Continue with Google", use_container_width=True):
                        try:
                            auth_settings = st.secrets["auth"]
                            required = ("redirect_uri", "cookie_secret", "client_id",
                                        "client_secret", "server_metadata_url")
                            if all(auth_settings.get(key) for key in required):
                                st.login()
                            else:
                                st.info("Google sign-in needs OIDC settings in .streamlit/secrets.toml.")
                        except (StreamlitSecretNotFoundError, KeyError):
                            st.info(
                                "Google sign-in is not configured yet. Add your Google OIDC settings "
                                "to .streamlit/secrets.toml to enable it."
                            )

            st.markdown('<div class="auth-divider"></div>', unsafe_allow_html=True)
            if mode != "Sign in" and mode != "Sign up":
                footer = "Back to sign in"
                destination = "Sign in"
            else:
                footer = "Don't have an account?" if mode == "Sign in" else "Already have an account?"
                destination = "Sign up" if mode == "Sign in" else "Sign in"
            left, right = st.columns([1.5, 1], vertical_alignment="center")
            with left:
                st.markdown('<div class="auth-foot">' + footer + "</div>", unsafe_allow_html=True)
            with right:
                with st.container(key="auth_switch"):
                    if st.button(destination, key="switch_auth_mode", use_container_width=True):
                        st.session_state.auth_mode = destination
                        st.query_params.clear()
                        st.rerun()
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
    st.caption("Signed in as " + st.session_state.get("user_name", "Google user"))
    if st.button("Sign out"):
        if supabase_session:
            try:
                supabase.auth.sign_out()
            except AuthApiError as error:
                st.error("Could not sign out: " + error.message)
                st.stop()
            except httpx.HTTPError:
                st.error("Could not connect to Supabase to sign out.")
                st.stop()
        st.session_state.authenticated = False
        st.session_state.pop("user_name", None)
        if getattr(st.user, "is_logged_in", False):
            st.logout()
        st.session_state.started = True
        st.rerun()
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
    st.caption(
        "Model: COCO + custom medicine/razor"
        if custom else "Model: pretrained COCO"
    )
    if st.button("Send test alert"):
        st.info(send_sos("", cfg["guardian"], "test alert - ignore this", 0.0))

with open(SETTINGS, "w") as f:
    json.dump(cfg, f)


@st.fragment(run_every=0.5)
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