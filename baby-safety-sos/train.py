import argparse
import time
import glob
from ultralytics import YOLO

p = argparse.ArgumentParser()
p.add_argument("--epochs", type=int, default=50)
p.add_argument("--imgsz", type=int, default=640)
p.add_argument("--batch", type=int, default=16)
a = p.parse_args()

model = YOLO("yolov8n.pt")  # start from COCO weights (transfer learning)
model.train(data="data.yaml", epochs=a.epochs, imgsz=a.imgsz, batch=a.batch,
            project="runs/detect", name="baby_hazard", exist_ok=True,
            hsv_h=0.02, hsv_s=0.6, hsv_v=0.4, degrees=15, fliplr=0.5, mosaic=1.0)  # augmentation

best = YOLO("runs/detect/baby_hazard/weights/best.pt")
m = best.val(data="data.yaml", split="test")
print("\n=== TEST RESULTS (put these in your report) ===")
print(f"Precision: {m.box.mp:.3f} | Recall: {m.box.mr:.3f} | mAP50: {m.box.map50:.3f} | mAP50-95: {m.box.map:.3f}")
for i, c in enumerate(m.box.ap_class_index):
    print(f"  {best.names[int(c)]:15s} AP50={m.box.ap50[i]:.3f}")

imgs = glob.glob("datasets/baby_hazards/test/images/*.jpg")[:50]
if imgs:
    best(imgs[0], verbose=False)  # warm-up
    t = time.time()
    for im in imgs:
        best(im, verbose=False)
    print(f"Avg latency: {(time.time()-t)/len(imgs)*1000:.1f} ms/image")
print("Confusion matrix & PR curves: runs/detect/baby_hazard/")
