import argparse
import math
import time
import glob
from pathlib import Path


CLASS_NAMES = ("medicine_strip", "razor")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
RUN_DIR = Path("runs") / "detect"


def validate_dataset():
    dataset_root = Path("datasets") / "baby_hazards"
    errors = []
    split_classes = {split: set() for split in ("train", "valid", "test")}

    for split in ("train", "valid", "test"):
        image_dir = dataset_root / split / "images"
        label_dir = dataset_root / split / "labels"
        images = sorted(
            path for path in image_dir.glob("*")
            if path.is_file() and path.suffix.casefold() in IMAGE_EXTENSIONS
        )
        if not images:
            errors.append(f"{split}: no images found in {image_dir}")
            continue

        for image in images:
            label = label_dir / image.with_suffix(".txt").name
            if not label.is_file():
                errors.append(f"{split}: missing label file for {image.name}")
                continue
            for line_number, line in enumerate(
                label.read_text(encoding="utf-8").splitlines(), start=1
            ):
                fields = line.split()
                if len(fields) != 5:
                    errors.append(
                        f"{split}: {label.name}:{line_number} must have "
                        "class_id center_x center_y width height"
                    )
                    continue
                try:
                    class_id = int(fields[0])
                    coordinates = [float(value) for value in fields[1:]]
                except ValueError:
                    errors.append(
                        f"{split}: {label.name}:{line_number} has non-numeric values"
                    )
                    continue
                if not 0 <= class_id < len(CLASS_NAMES):
                    errors.append(
                        f"{split}: {label.name}:{line_number} has unknown "
                        f"class ID {class_id}"
                    )
                    continue
                center_x, center_y, width, height = coordinates
                if (
                    not all(math.isfinite(value) for value in coordinates)
                    or not 0 <= center_x <= 1
                    or not 0 <= center_y <= 1
                    or not 0 < width <= 1
                    or not 0 < height <= 1
                    or center_x - width / 2 < 0
                    or center_x + width / 2 > 1
                    or center_y - height / 2 < 0
                    or center_y + height / 2 > 1
                ):
                    errors.append(
                        f"{split}: {label.name}:{line_number} has invalid "
                        "normalized box coordinates"
                    )
                    continue
                split_classes[split].add(class_id)

    for split, classes in split_classes.items():
        missing_classes = [
            name for class_id, name in enumerate(CLASS_NAMES)
            if class_id not in classes
        ]
        if missing_classes:
            errors.append(
                f"{split}: no labeled examples for classes: "
                + ", ".join(missing_classes)
            )

    if errors:
        raise SystemExit(
            "Dataset validation failed:\n- "
            + "\n- ".join(errors)
            + "\nSee datasets/baby_hazards/README.md for the two-class dataset layout."
        )

p = argparse.ArgumentParser()
p.add_argument("--epochs", type=int, default=50)
p.add_argument("--imgsz", type=int, default=640)
p.add_argument("--batch", type=int, default=16)
a = p.parse_args()

validate_dataset()

from ultralytics import YOLO

model = YOLO("yolov8n.pt")  # start from COCO weights (transfer learning)
model.train(data="data.yaml", epochs=a.epochs, imgsz=a.imgsz, batch=a.batch,
            project=str(RUN_DIR.resolve()), name="baby_hazard", exist_ok=True,
            hsv_h=0.02, hsv_s=0.6, hsv_v=0.4, degrees=15, fliplr=0.5, mosaic=1.0)  # augmentation

best = YOLO(RUN_DIR / "baby_hazard" / "weights" / "best.pt")
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
