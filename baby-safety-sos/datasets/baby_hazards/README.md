# Baby hazard training dataset

The `train/images/Images.zip` archive contains 20 razor photos and 19
medicine-strip photos. To extract them and draw their YOLO bounding boxes, run
`python annotate_dataset.py` from the project root. To label photos already
placed in validation or test, run `python annotate_dataset.py --split valid`
or `python annotate_dataset.py --split test`. In those splits, press **0** for
a medicine strip or **1** for a razor, draw a box around the object itself
(not the hand), then press **S** to save. Press **N** if the object is not
visible, **R** to redraw, or **Q** to stop and resume.

The supplied images remain in the training split because they come from only
two short recordings and should not be randomly split across train/validation/test.

Put each image in the matching `images` folder and create a YOLO annotation
file with the same base name in the matching `labels` folder. For example:

```text
train/images/photo001.jpg
train/labels/photo001.txt
```

Each non-empty annotation line describes one object:

```text
class_id center_x center_y width height
```

Coordinates must be normalized to values from 0 to 1 relative to the image
width and height. Use these class IDs, matching `data.yaml`:

| ID | Class |
|---:|---|
| 0 | medicine_strip |
| 1 | razor |

Use the `train`, `valid`, and `test` splits for training, validation, and final
evaluation, respectively. Keep near-duplicate images and images from the same
photo/video session within one split to avoid leakage. Include varied views,
distances, lighting, and backgrounds. Include examples with objects held near
visible hands, as well as objects not being held and safe background images.

Collect images you own or are licensed to use. Do not stage real hazards near
a child; use safe props and adult supervision.

Once all splits contain correctly labeled examples, run from the project root:

```powershell
python train.py --epochs 50
```

This custom detector has two classes. Training requires labeled examples of
both in each split. Use new, separate recordings for validation and test to
avoid evaluating on near-duplicate frames.

Dataset image and label files are ignored by Git; the folder structure and
this guide are tracked instead.
