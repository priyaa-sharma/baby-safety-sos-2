"""Hazard + 'holding' detection: object detector (YOLO) + pose estimator (YOLO-pose)."""
import os
import cv2
import numpy as np
import torch
from ultralytics import YOLO

HAZARDS = {"knife", "scissors", "fork", "lighter", "battery", "medicine_strip", "razor"}
COCO_HAZARDS = {"knife", "scissors", "fork"}
CUSTOM_WEIGHTS = "runs/detect/baby_hazard/weights/best.pt"  # produced by train.py
LEFT_WRIST, RIGHT_WRIST = 9, 10
HOLD, SAFE, GRAY, DOT = (12, 89, 232), (23, 187, 76), (170, 170, 170), (110, 227, 166)  # BGR


def point_to_box_distance(p, box):
    x1, y1, x2, y2 = box
    dx = max(x1 - p[0], 0, p[0] - x2)
    dy = max(y1 - p[1], 0, p[1] - y2)
    return float(np.hypot(dx, dy))


class HazardDetector:
    def __init__(self, weights=None, conf=0.30, near_px=60, imgsz=256):
        torch.set_num_threads(1)
        cv2.setNumThreads(1)
        path = weights or (CUSTOM_WEIGHTS if os.path.exists(CUSTOM_WEIGHTS) else "yolov8n.pt")
        self.using_custom = os.path.abspath(path) == os.path.abspath(CUSTOM_WEIGHTS)
        self.obj = YOLO(path)
        self.coco = YOLO("yolov8n.pt") if self.using_custom else None
        self.coco_hazard_ids = (
            [
                class_id for class_id, name in self.coco.names.items()
                if name in COCO_HAZARDS
            ]
            if self.coco is not None else []
        )
        self.pose = YOLO("yolov8n-pose.pt")
        self.conf, self.near_px, self.imgsz = conf, near_px, imgsz
        blank = np.zeros((480, 640, 3), dtype=np.uint8)  # warm-up so the first frame isn't slow
        self.obj(blank, imgsz=self.imgsz, verbose=False)
        if self.coco is not None:
            self.coco(blank, imgsz=self.imgsz, classes=self.coco_hazard_ids, verbose=False)
        self.pose(blank, imgsz=256, verbose=False)
        # Ultralytics may set a larger CPU thread pool while warming up predictors.
        torch.set_num_threads(1)

    def _wrists(self, frame):
        wrists = []
        pr = self.pose(frame, imgsz=256, conf=0.25, verbose=False)[0]
        if pr.keypoints is not None and len(pr.keypoints.xy):
            xy = pr.keypoints.xy.cpu().numpy()
            cf = pr.keypoints.conf.cpu().numpy() if pr.keypoints.conf is not None else np.ones(xy.shape[:2])
            for kp, kc in zip(xy, cf):
                for i in (LEFT_WRIST, RIGHT_WRIST):
                    if kc[i] > 0.25:
                        wrists.append(kp[i])
        return wrists

    def process(self, frame):
        """Returns (annotated_frame, holding_list). holding_list = [(name, conf)]."""
        results = [
            self.obj(frame, conf=self.conf, imgsz=self.imgsz, verbose=False)[0]
        ]
        if self.coco is not None:
            results.append(
                self.coco(
                    frame, conf=self.conf, imgsz=self.imgsz,
                    classes=self.coco_hazard_ids, verbose=False,
                )[0]
            )
        out = frame.copy()
        hazards = []
        for model, result in zip(
            (self.obj, self.coco) if self.coco is not None else (self.obj,),
            results,
        ):
            for b in result.boxes:
                name = model.names[int(b.cls)]
                x1, y1, x2, y2 = map(int, b.xyxy[0].tolist())
                if name in HAZARDS:
                    hazards.append((name, float(b.conf), [x1, y1, x2, y2]))
                else:  # show everything else the AI sees, thin and gray (for debugging)
                    cv2.rectangle(out, (x1, y1), (x2, y2), GRAY, 1)
                    cv2.putText(out, name, (x1, max(y1 - 5, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, GRAY, 1)

        wrists = self._wrists(frame) if hazards else []  # pose only when needed (saves CPU)

        holding = []
        for name, c, box in hazards:
            held = any(point_to_box_distance(w, box) <= self.near_px for w in wrists)
            if held:
                holding.append((name, c))
            color = HOLD if held else SAFE
            x1, y1, x2, y2 = box
            tag = "HOLDING " if held else ("(no hand seen) " if not wrists else "")
            cv2.rectangle(out, (x1, y1), (x2, y2), color, 3)
            cv2.putText(out, f"{tag}{name} {c:.2f}", (x1, max(y1 - 8, 15)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        for w in wrists:
            cv2.circle(out, (int(w[0]), int(w[1])), 6, DOT, -1)
        return out, holding