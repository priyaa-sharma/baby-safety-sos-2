# 🍼 Baby Safety SOS (AI/ML project)

Detects a baby holding a hazardous object (knife, scissors, lighter...) and sends an SOS call + SMS to the guardian.

**Pipeline:** camera -> YOLOv8 hazard detector + YOLOv8-pose (wrists) -> "holding" rule (wrist near hazard box)
-> must persist N seconds -> Twilio call/SMS + snapshot -> alert history.

## Run
```
pip install -r requirements.txt
cp .env.example .env     # add Twilio keys (optional; demo mode works without)
streamlit run app.py
```
Works immediately with pretrained COCO weights (knife, scissors, fork).

## Train on your own data
1. Download a YOLOv8-format dataset from Roboflow Universe (search: knife, scissors, lighter, battery, medicine strip, razor), or label your own images with Roboflow/LabelImg. Include **baby/toddler hand-holding** images and **negatives** (objects lying on a table).
2. Put it in `datasets/baby_hazards/{train,valid,test}/{images,labels}` and match class names in `data.yaml`.
3. `python train.py --epochs 50` (use Google Colab GPU if no GPU).
4. Restart the app: it auto-loads `runs/detect/baby_hazard/weights/best.pt`.

## Report checklist
Dataset size/split, augmentation, precision/recall/mAP per class (printed by train.py), confusion matrix, latency,
false-alarm test (objects on table, adults holding objects), and limits (occlusion, lighting, small hands).
Use toy/blunt lookalikes for testing, never real sharp objects near a child.

## Privacy & safety
Video is processed locally and never uploaded; only the alert snapshot is saved on your machine. This is a safety assist, not a substitute for supervision.
