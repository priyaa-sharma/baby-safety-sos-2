import argparse
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

import cv2


DATASET_ROOT = Path("datasets") / "baby_hazards"
DEFAULT_ARCHIVE = DATASET_ROOT / "train" / "images" / "Images.zip"
CLASS_IDS = {"razor": 1, "medicines_strip": 0}
CLASS_NAMES = {0: "medicine_strip", 1: "razor"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
WINDOW_NAME = "Baby Safety SOS - draw object box"
MAX_PREVIEW_SIZE = (1280, 720)


def class_id_from_archive_path(filename):
    parts = PurePosixPath(filename).parts
    matches = []
    for part in parts[:-1]:
        normalized = part.casefold().replace(" ", "")
        if normalized in CLASS_IDS:
            matches.append(CLASS_IDS[normalized])
    if len(matches) != 1:
        raise ValueError(
            f"Expected one Razor or Medicines_Strip folder in {filename!r}"
        )
    return matches[0]


def extract_images(archive_path, image_dir):
    image_dir.mkdir(parents=True, exist_ok=True)
    extracted = []
    seen_names = set()

    try:
        with ZipFile(archive_path) as archive:
            for entry in archive.infolist():
                if entry.is_dir():
                    continue
                member_path = PurePosixPath(entry.filename)
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise ValueError(f"Unsafe ZIP entry path: {entry.filename}")
                if Path(member_path.name).suffix.casefold() not in IMAGE_EXTENSIONS:
                    continue

                class_id = class_id_from_archive_path(entry.filename)
                image_name = Path(member_path.name).name
                if image_name.casefold() in seen_names:
                    raise ValueError(
                        f"Duplicate image filename in ZIP: {image_name}"
                    )
                seen_names.add(image_name.casefold())

                image_path = image_dir / image_name
                content = archive.read(entry)
                if image_path.exists():
                    if image_path.read_bytes() != content:
                        raise FileExistsError(
                            f"Refusing to overwrite a different image: {image_path}"
                        )
                else:
                    image_path.write_bytes(content)
                extracted.append((image_path, class_id))
    except BadZipFile as exc:
        raise ValueError(f"Not a valid ZIP archive: {archive_path}") from exc

    if not extracted:
        raise ValueError(f"No supported images found in {archive_path}")
    return sorted(extracted, key=lambda item: item[0].name.casefold())


def yolo_label(class_id, box, image_width, image_height):
    x1, y1, x2, y2 = box
    center_x = ((x1 + x2) / 2) / image_width
    center_y = ((y1 + y2) / 2) / image_height
    width = (x2 - x1) / image_width
    height = (y2 - y1) / image_height
    return (
        f"{class_id} {center_x:.6f} {center_y:.6f} "
        f"{width:.6f} {height:.6f}\n"
    )


def pending_images(images, labels_dir, redo_empty=False):
    pending = []
    for item in images:
        label_path = labels_dir / item[0].with_suffix(".txt").name
        if not label_path.exists() or (
            redo_empty and not label_path.read_text(encoding="utf-8").strip()
        ):
            pending.append(item)
    return pending


def annotate_images(images, labels_dir, redo_empty=False):
    labels_dir.mkdir(parents=True, exist_ok=True)
    pending = pending_images(images, labels_dir, redo_empty)
    if not pending:
        print("All extracted images already have label files.")
        return

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_AUTOSIZE)

    for index, (image_path, class_id) in enumerate(pending, start=1):
        image = cv2.imread(str(image_path))
        if image is None:
            cv2.destroyAllWindows()
            raise ValueError(f"Could not read image: {image_path}")
        image_height, image_width = image.shape[:2]
        scale = min(
            MAX_PREVIEW_SIZE[0] / image_width,
            MAX_PREVIEW_SIZE[1] / image_height,
            1.0,
        )
        preview_width = round(image_width * scale)
        preview_height = round(image_height * scale)
        state = {
            "start": None, "box": None, "drawing": False,
            "class_id": class_id,
        }

        def on_mouse(event, x, y, flags, _parameter):
            if event == cv2.EVENT_LBUTTONDOWN:
                if 0 <= x < preview_width and 0 <= y < preview_height:
                    state["start"] = (x, y)
                    state["drawing"] = True
                    state["box"] = None
            elif event == cv2.EVENT_MOUSEMOVE and state["drawing"]:
                x = min(max(x, 0), preview_width - 1)
                y = min(max(y, 0), preview_height - 1)
                sx, sy = state["start"]
                state["box"] = (
                    min(sx, x), min(sy, y), max(sx, x), max(sy, y)
                )
            elif event == cv2.EVENT_LBUTTONUP and state["drawing"]:
                x = min(max(x, 0), preview_width - 1)
                y = min(max(y, 0), preview_height - 1)
                sx, sy = state["start"]
                state["box"] = (
                    min(sx, x), min(sy, y), max(sx, x), max(sy, y)
                )
                state["drawing"] = False

        cv2.setMouseCallback(WINDOW_NAME, on_mouse)
        while True:
            preview = cv2.resize(
                image, (preview_width, preview_height),
                interpolation=cv2.INTER_AREA,
            )
            if state["box"] is not None:
                x1, y1, x2, y2 = state["box"]
                cv2.rectangle(preview, (x1, y1), (x2, y2), (0, 220, 0), 2)

            canvas = cv2.copyMakeBorder(
                preview, 0, 58, 0, 0, cv2.BORDER_CONSTANT,
                value=(32, 32, 32),
            )
            cv2.putText(
                canvas,
                f"{index}/{len(pending)}  {image_path.name}  "
                f"class {CLASS_NAMES.get(state['class_id'], 'select 0 or 1')}",
                (12, preview_height + 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1,
            )
            cv2.putText(
                canvas,
                "0 medicine strip | 1 razor | drag object | S save | "
                "N no object | "
                "R redraw | Q quit",
                (12, preview_height + 47),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (210, 210, 210), 1,
            )
            cv2.imshow(WINDOW_NAME, canvas)
            key = cv2.waitKey(20) & 0xFF

            if class_id is None and key in (ord("0"), ord("1")):
                state["class_id"] = int(chr(key))
            elif key in (ord("r"), ord("R")):
                state["box"] = None
                state["start"] = None
            elif key in (ord("n"), ord("N")):
                label_path = labels_dir / image_path.with_suffix(".txt").name
                label_path.write_text("", encoding="utf-8")
                break
            elif key in (ord("s"), ord("S")):
                box = state["box"]
                if state["class_id"] is None:
                    print("Choose class 0 (medicine strip) or 1 (razor).")
                    continue
                if box is None or box[2] - box[0] < 2 or box[3] - box[1] < 2:
                    print(f"Draw a box before saving {image_path.name}.")
                    continue
                factor_x = image_width / preview_width
                factor_y = image_height / preview_height
                original_box = (
                    round(box[0] * factor_x),
                    round(box[1] * factor_y),
                    round(box[2] * factor_x),
                    round(box[3] * factor_y),
                )
                label_path = labels_dir / image_path.with_suffix(".txt").name
                label_path.write_text(
                    yolo_label(
                        state["class_id"], original_box,
                        image_width, image_height,
                    ),
                    encoding="utf-8",
                )
                break
            elif key in (ord("q"), ord("Q"), 27):
                cv2.destroyAllWindows()
                print("Stopped. Run the command again to resume.")
                return

    cv2.destroyAllWindows()
    print(f"Created or confirmed {len(images)} label files in {labels_dir}.")


def main():
    parser = argparse.ArgumentParser(
        description="Extract and draw YOLO boxes for the medicine-strip and razor ZIP."
    )
    parser.add_argument(
        "--archive", type=Path, default=DEFAULT_ARCHIVE,
        help=f"Image ZIP (default: {DEFAULT_ARCHIVE})",
    )
    parser.add_argument(
        "--redo-empty", action="store_true",
        help="Reopen existing empty label files as well as unlabeled images",
    )
    parser.add_argument(
        "--split", choices=("train", "valid", "test"), default="train",
        help="Dataset split to annotate (train extracts the supplied ZIP)",
    )
    args = parser.parse_args()

    if not args.archive.is_file():
        parser.error(f"Image ZIP not found: {args.archive}")

    image_dir = DATASET_ROOT / args.split / "images"
    labels_dir = DATASET_ROOT / args.split / "labels"
    try:
        if args.split == "train":
            images = extract_images(args.archive, image_dir)
        else:
            images = sorted(
                (path, None)
                for path in image_dir.iterdir()
                if path.is_file()
                and path.suffix.casefold() in IMAGE_EXTENSIONS
            ) if image_dir.is_dir() else []
            if not images:
                parser.error(
                    f"No images found in {image_dir}. Add images before labeling."
                )
        print(
            f"Found {len(images)} images in {args.split}. "
            "Draw one box around each visible object."
        )
        annotate_images(images, labels_dir, redo_empty=args.redo_empty)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Dataset annotation failed: {exc}\n")


if __name__ == "__main__":
    main()
