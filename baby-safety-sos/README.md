# Baby Safety SOS

An AI/ML safety assistant for babies who are left alone. A camera watches the baby, and if the baby picks up a medicine strip or razor, or cries for a sustained time, the guardian gets an alert on their phone automatically. No button needs to be pressed.

This is a safety assist, not a replacement for adult supervision. It will sometimes miss things and sometimes raise false alarms.

## Features

- **Always-on camera monitoring.** Runs continuously in the background, with no browser needed.
- **Hazard detection.** YOLOv8 detects scissors, knives and forks using COCO weights, plus medicine strips and razors using the custom-trained model when available.
- **"Holding" logic.** YOLOv8-pose finds the wrists, and an alert is raised only when a hand is close to a hazard. An object lying on a table does not trigger it.
- **Sustained-hold rule.** The hazard must stay in hand for a set time (default 1.5 s) before an alert is sent, which reduces false alarms.
- **Cry detection.** A pretrained audio model (AST, trained on AudioSet) listens through the microphone and alerts when crying lasts for several seconds.
- **Instant alerts.** A Telegram message with a snapshot photo, plus an optional Telegram voice call and an optional ntfy push notification.
- **Live dashboard.** A pastel pink Streamlit page with the live feed, status cards, alert history and adjustable settings.
- **Local sign-in.** Create an account with an email and password, or sign in with an existing local account. Passwords are stored as salted hashes in a local SQLite database. Google sign-in can be enabled with Streamlit OIDC settings.
- **Alert cooldowns.** Prevents the guardian from being flooded with repeated alerts.
- **Custom training pipeline.** `train.py` fine-tunes YOLOv8 on your own hazard dataset and reports precision, recall, mAP and latency.

## How it works

```
Camera --> YOLOv8 object detector --> hazard boxes
       --> YOLOv8-pose (only when a hazard is seen) --> wrist positions
       --> "wrist near hazard" rule --> must persist for N seconds
       --> alert (Telegram photo + optional call/push)

Microphone --> AST audio classifier --> cry score
           --> must stay above threshold for N seconds --> alert
```

The system has two programs that run separately:

- `monitor.py` is the always-on watcher. It reads the camera and microphone and sends alerts. It keeps working even if the dashboard is closed.
- `app.py` is the dashboard. It only shows the live view and changes settings. Settings are saved to `settings.json`, and the monitor picks up changes within a couple of seconds.

## Project structure

```
baby-safety-sos/
  monitor.py          Always-on monitor (camera + cry detection + alerts)
  app.py              Streamlit dashboard (pastel pink theme)
  detector.py         Hazard detection + "holding" logic (YOLOv8 + YOLOv8-pose)
  cry_detector.py     Cry detection from the microphone (AST audio model)
  alerts.py           Telegram / Telegram call / ntfy alerts + alert history log
  train.py            Fine-tune YOLOv8 on your own dataset and evaluate it
  data.yaml           Dataset configuration for training
  start_monitor.bat   Windows helper that restarts the monitor if it crashes
  requirements.txt    Python dependencies
  .env                Your private keys (never share or commit this file)
  .streamlit/         Theme configuration
  alerts/             Generated: live frame, status, alert log, snapshots
  settings.json       Generated: dashboard settings
```

## WORKING 

https://github.com/user-attachments/assets/def24c4a-6465-4ee7-a881-c90ed1ed0c00

<img width="776" height="329" alt="Screenshot 2026-10-26 202120" src="https://github.com/user-attachments/assets/ff634308-5a04-4964-b87c-55f1334bb597" />
<img width="533" height="328" alt="Screenshot 2026-10-26 202143" src="https://github.com/user-attachments/assets/21481de9-e599-48fe-90cb-ead005b0946b" />





## Setup

Requires Python 3.10 or newer and a webcam. A microphone is needed for cry detection.

```
pip install -r requirements.txt
pip install sounddevice transformers
```

The first run downloads the YOLO weights and the audio model (a few hundred MB), so it needs internet and takes a few minutes once.

### Configure alerts (`.env`)

Create a file named `.env` in the project folder:

```
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
CALLMEBOT_USER=@your_telegram_username
NTFY_TOPIC=
```

**Telegram message (main alert, free):**
1. In Telegram, message **@BotFather**, send `/newbot` and follow the steps. Copy the token.
2. Open your new bot, press Start and send "hi".
3. Open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser and copy the number after `"chat":{"id":`. That is your chat ID.

**Telegram voice call (optional, free):**
1. In Telegram, send `/start` to **@CallMeBot_txtbot** to authorize it.
2. Set `CALLMEBOT_USER` to your username with exactly one `@`, or to your phone number with the country code.
3. This is a Telegram call, not a SIM call, so it only rings the Telegram app. The service is free and best-effort, and it can skip calls when it is busy, so treat it as a bonus on top of the Telegram message.

**ntfy push (optional, free):** install the ntfy app, subscribe to a long random topic name, and put the same name in `NTFY_TOPIC`.

Keep your bot token private. If it is ever exposed, revoke it with **@BotFather** using `/revoke` and put the new token in `.env`.

### Configure password-reset email

Forgot-password links are sent by SMTP and expire after 30 minutes. Add your email provider's SMTP settings to `.env`:

```
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=your-sender@example.com
SMTP_PASSWORD=your-email-app-password
SMTP_FROM=Baby Safety SOS <your-sender@example.com>
APP_BASE_URL=http://localhost:8501
```

Use an app password if your provider requires one. For a deployed app, set `APP_BASE_URL` to its public HTTPS URL so links open the right site. Email credentials and `.env` must remain private.

### Configure Google sign-in (optional)

Local email and password accounts work without any additional setup. To enable the Google button, configure Streamlit OIDC in `.streamlit/secrets.toml` with your Google OAuth client:

```
[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "a-long-random-secret"
client_id = "your-google-client-id"
client_secret = "your-google-client-secret"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

Keep the secrets file private and add the matching redirect URI to your Google OAuth client.

### Supabase Python client

The Supabase client is initialized in `src/supabase_client.py`. Replace `SUPABASE_URL` and `SUPABASE_PUBLIC_KEY` there with your project's URL and publishable key, then import it in Python with:

```
from src.supabase_client import supabase
```

The `supabase` Python package is included in `requirements.txt`.

For signup confirmation emails, set the redirect URL in `.env` to the URL where this Streamlit app is running:

```
SUPABASE_AUTH_REDIRECT_URL=http://localhost:8501
```

In the Supabase dashboard, open **Authentication → URL Configuration** and add that exact URL to **Redirect URLs**. For deployment, use the app's public URL for both the environment variable and the allowed redirect URL. Request a fresh confirmation email after changing the redirect; old or already-used links may have expired.

## Run

Open two terminals in the project folder.

```
python monitor.py                    # always-on monitor
python -m streamlit run app.py       # dashboard (optional)
```

On Windows, you can run `start_monitor.bat` instead of `python monitor.py`. It restarts the monitor automatically if it crashes. To start it when the computer turns on, press Win+R, type `shell:startup`, and put a shortcut to `start_monitor.bat` in that folder.

Both programs read `.env` only at startup, so restart them after changing it.

For continuous use, keep the computer plugged in, turn off sleep, and point the camera at the baby's area.

## Dashboard settings

| Setting | Default | Meaning |
|---|---|---|
| Camera index | 0 | Which camera to use. Try 1 if 0 does not work |
| Confidence threshold | 0.30 | Minimum certainty for an object detection |
| Hand-to-object distance | 80 px | How close a wrist must be to count as holding |
| Hold time before alert | 1.5 s | How long the hazard must stay in hand |
| Cooldown between alerts | 60 s | Minimum gap between hazard alerts |
| Listen for crying | on | Turns cry detection on or off |
| Cry sensitivity threshold | 0.35 | Cry score needed to count as crying |
| Crying must last | 6 s | How long crying must continue before an alert |
| Cry alert cooldown | 120 s | Minimum gap between cry alerts |

## Testing

**Hazard detection:** use a medicine-strip prop or blunt razor lookalike in front of the camera with your wrist visible. The box should turn coral and say HOLDING, and an alert arrives after the hold time. Put the object on a table and confirm that no alert is sent. Never put medicine or a real razor near a child.

Reading the video overlay: a green box with a name means a hazard is seen but nobody is holding it. "(no hand seen)" means the object is detected but no wrist is visible. Thin gray boxes show other objects the model sees and are only there for debugging.

**Cry detection:** play a baby crying sound effect on a phone near the laptop microphone. The cry level on the dashboard should rise, and after the set duration an alert is sent. If the level stays low, lower the sensitivity threshold.

**Alerts:** the "Send test alert" button sends a test message through the configured channels.

## Training your own model

The custom detector is trained to recognize medicine strips and razors:

1. Collect varied views of medicine strips and razors, both near hands and not being held.
2. For the supplied `datasets/baby_hazards/train/images/Images.zip`, run `python annotate_dataset.py`. It extracts the images and opens a local labeling window. Drag a box around the hazard itself (not the hand), then press **S** to save. Press **N** if the object is not visible, **R** to redraw, or **Q** to stop and resume later. The medicine-strip and razor folders map to class IDs 0 and 1. To reopen empty label files (for example, if **N** was pressed by mistake), run `python annotate_dataset.py --redo-empty`.
3. Keep the 39 supplied frames in the training split; they come from only two short recordings, so randomly splitting them into train/validation/test would leak near-duplicate frames. Add new, separately recorded images of both classes to `valid` and `test`, then label them with `python annotate_dataset.py --split valid` and `python annotate_dataset.py --split test`. In the labeling window, press **0** for a medicine strip or **1** for a razor, draw its box, and press **S** to save. The trainer checks for both classes and complete labels in every split before training.
4. Run `python train.py --epochs 50`. A free Google Colab GPU works well if your computer has no GPU.
5. Restart `monitor.py`. When `runs/detect/baby_hazard/weights/best.pt` exists, the monitor combines it with the original COCO model: COCO detects scissors, knives and forks, while the custom model detects medicine strips and razors.

`train.py` prints precision, recall, mAP50, mAP50-95, per-class AP and average latency. It also saves the confusion matrix and the PR curves in `runs/detect/baby_hazard/`.

## Evaluation checklist for the report

- Dataset size, classes, and the train/validation/test split
- Augmentation used during training
- Precision, recall and mAP (overall and per class), and the confusion matrix
- Latency per frame on your hardware
- False-alarm tests: objects on a table, an adult holding objects, poor lighting
- Cry detection tests: real crying, talking, music, TV and silence, with the cry level for each
- Honest failure cases and what you would improve

## Limitations

- Small or partly hidden objects, unusual angles and poor lighting can be missed.
- The "holding" rule needs a visible wrist. A baby's hands are small and often out of frame.
- The pretrained cry model is general-purpose, so TV, other babies and loud noise can cause false alarms, and soft whimpering can be missed.
- Running on a CPU limits the frame rate. A GPU makes it much faster.
- The free Telegram voice call depends on a third-party service and is not guaranteed to go through. A real product would use a paid telephony provider.
- It is not a substitute for supervision.

## Privacy

Video and audio are processed on your own computer and are never uploaded. The only data saved is the alert snapshot photo and a CSV log of alerts in the `alerts/` folder, and the snapshot is sent to your own Telegram chat when an alert fires.

## Troubleshooting

| Problem | Fix |
|---|---|
| Dashboard says "Monitor not running" | Start `python monitor.py` in a separate terminal, from the same project folder |
| "Cannot read camera" | Set the camera index to 0, and close other programs using the camera |
| `requirements.txt` not found | Move into the project folder (`cd baby-safety-sos`). The files may be one folder deeper after extracting a zip |
| Video lags | Lower the number of programs using the CPU, and keep the object-detection image size small |
| No Telegram message | Check the token and chat ID, and make sure you pressed Start on the bot. Restart after editing `.env` |
| Call does not ring | Check that you authorized @CallMeBot_txtbot and that your username has one `@`. "FLOOD" errors come from the service being busy, so try again later |
| Cry card shows "unavailable" | Run `pip install sounddevice transformers`, and allow microphone access in Windows privacy settings |

## Tech stack

Python, Ultralytics YOLOv8 (detection and pose), OpenCV, PyTorch, Hugging Face Transformers (AST audio classifier), sounddevice, Streamlit, Telegram Bot API, CallMeBot, ntfy.
