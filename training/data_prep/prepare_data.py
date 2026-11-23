#!/usr/bin/env python3
"""Prepare the partial ForestPersonsIR crop dataset.

Run with: python3 -m data_prep.prepare_data
"""

from __future__ import annotations

import copy
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np


SOURCE = Path("/Users/aayush/ForestPersonsIR")
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "fpir_partial"
SPLITS = ("train", "val", "test")
EXPECTED_KEYS = {
    "crops",
    "labels",
    "kinds",
    "pose",
    "visibility",
    "seq",
    "size_px",
}
VALID_POSES = ("standing", "sitting", "lying")
VALID_VISIBILITIES = (100, 70, 40, 20)


def read_gray_or_colour(path: Path) -> tuple[np.ndarray | None, float | None]:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise RuntimeError(f"OpenCV could not read {path}")
    if image.dtype != np.uint8:
        raise RuntimeError(f"Expected 8-bit JPEG, got {image.dtype} for {path}")
    if image.ndim == 2:
        return image, None
    if image.ndim == 3 and image.shape[2] == 1:
        return image[:, :, 0], None
    if image.ndim == 3 and image.shape[2] == 3:
        b, g, r = cv2.split(image)
        pairwise_mad = float(
            (
                np.mean(cv2.absdiff(b, g), dtype=np.float64)
                + np.mean(cv2.absdiff(b, r), dtype=np.float64)
                + np.mean(cv2.absdiff(g, r), dtype=np.float64)
            )
            / 3.0
        )
        if pairwise_mad < 8.0:
            return b, pairwise_mad
        return None, pairwise_mad
    raise RuntimeError(f"Unexpected image shape {image.shape} for {path}")


def category_details(categories: list[dict]) -> dict[int, tuple[str, int] | None]:
    result: dict[int, tuple[str, int] | None] = {}
    for category in categories:
        cid = int(category["id"])
        name = str(category["name"])
        if name == "unknown_0":
            result[cid] = None
            continue
        try:
            pose, visibility_text = name.rsplit("_", 1)
            visibility = int(visibility_text)
        except Exception as exc:
            raise RuntimeError(f"Invalid category name: {name}") from exc
        if pose not in VALID_POSES or visibility not in VALID_VISIBILITIES:
            raise RuntimeError(f"Unexpected category name: {name}")
        result[cid] = (pose, visibility)
    return result


def expanded_person_boxes(boxes: list[list[float]]) -> list[tuple[float, float, float, float]]:
    expanded = []
    for x, y, w, h in boxes:
        expanded.append((x - 0.25 * w, y - 0.25 * h, x + 1.25 * w, y + 1.25 * h))
    return expanded


def overlaps_expanded(box: tuple[float, float, float, float], expanded: list[tuple[float, float, float, float]]) -> bool:
    x, y, w, h = box
    x2, y2 = x + w, y + h
    for px1, py1, px2, py2 in expanded:
        if x < px2 and x2 > px1 and y < py2 and y2 > py1:
            return True
    return False


def crop_from_box(image: np.ndarray, box: tuple[float, float, float, float], rng: np.random.Generator) -> np.ndarray:
    x, y, w, h = box
    side = max(h, 2.0 * w) * float(rng.uniform(1.2, 1.5))
    center_x = x + w / 2.0 + float(rng.normal(0.0, 0.08 * w))
    center_y = y + h / 2.0 + float(rng.normal(0.0, 0.08 * h))
    patch_w = max(1, int(round(side / 2.0)))
    patch_h = max(1, int(round(side)))
    patch = cv2.getRectSubPix(image, (patch_w, patch_h), (center_x, center_y))
    resized = cv2.resize(patch, (32, 64), interpolation=cv2.INTER_LINEAR)
    return resized.astype(np.float32, copy=False)


def hard_candidates(image: np.ndarray) -> list[tuple[float, float]]:
    blurred = cv2.GaussianBlur(image.astype(np.float32), (3, 3), 0.8)
    median = cv2.medianBlur(image, 15).astype(np.float32)
    response = blurred - median
    maxima = response == cv2.dilate(response, np.ones((7, 7), np.uint8))
    ys, xs = np.nonzero(maxima & (response > 3.0))
    if len(xs) == 0:
        return []
    order = np.argsort(response[ys, xs], kind="stable")[::-1]
    return [(float(xs[i]), float(ys[i])) for i in order]


def add_record(
    records: dict[str, list],
    crop: np.ndarray,
    label: float,
    kind: str,
    pose: str,
    visibility: int,
    seq: str,
    size_px: float,
) -> None:
    records["crops"].append(crop)
    records["labels"].append(label)
    records["kinds"].append(kind)
    records["pose"].append(pose)
    records["visibility"].append(visibility)
    records["seq"].append(seq)
    records["size_px"].append(size_px)


def make_arrays(records: dict[str, list]) -> dict[str, np.ndarray]:
    count = len(records["crops"])
    crops = np.stack(records["crops"]).astype(np.float32) if count else np.empty((0, 64, 32), np.float32)
    max_seq = max((len(value) for value in records["seq"]), default=1)
    return {
        "crops": crops,
        "labels": np.asarray(records["labels"], dtype=np.float32),
        "kinds": np.asarray(records["kinds"], dtype="<U8"),
        "pose": np.asarray(records["pose"], dtype="<U8"),
        "visibility": np.asarray(records["visibility"], dtype=np.int32),
        "seq": np.asarray(records["seq"], dtype=f"<U{max_seq}"),
        "size_px": np.asarray(records["size_px"], dtype=np.float32),
    }


def validate_npz(path: Path) -> dict:
    with np.load(path, allow_pickle=False) as loaded:
        if set(loaded.files) != EXPECTED_KEYS:
            raise RuntimeError(f"Wrong arrays in {path}: {loaded.files}")
        arrays = {key: loaded[key] for key in loaded.files}
    n = arrays["crops"].shape[0]
    expected_shapes = {
        "crops": (n, 64, 32),
        "labels": (n,),
        "kinds": (n,),
        "pose": (n,),
        "visibility": (n,),
        "seq": (n,),
        "size_px": (n,),
    }
    for key, shape in expected_shapes.items():
        if arrays[key].shape != shape:
            raise RuntimeError(f"Wrong shape for {path}:{key}: {arrays[key].shape}")
    if arrays["crops"].dtype != np.float32 or arrays["labels"].dtype != np.float32:
        raise RuntimeError(f"Wrong float dtype in {path}")
    if arrays["visibility"].dtype != np.int32 or arrays["size_px"].dtype != np.float32:
        raise RuntimeError(f"Wrong numeric dtype in {path}")
    for key in ("kinds", "pose", "seq"):
        if arrays[key].dtype.kind != "U":
            raise RuntimeError(f"{path}:{key} is not fixed-width unicode")
    if not np.isfinite(arrays["crops"]).all() or not np.isfinite(arrays["labels"]).all() or not np.isfinite(arrays["size_px"]).all():
        raise RuntimeError(f"NaN or inf found in {path}")
    if not set(np.unique(arrays["labels"]).tolist()) <= {0.0, 1.0}:
        raise RuntimeError(f"Invalid labels in {path}")
    if not set(np.unique(arrays["kinds"]).tolist()) <= {"person", "hard_neg", "rand_neg"}:
        raise RuntimeError(f"Invalid kinds in {path}")
    if not set(np.unique(arrays["pose"]).tolist()) <= {"", *VALID_POSES}:
        raise RuntimeError(f"Invalid poses in {path}")
    if not set(np.unique(arrays["visibility"]).tolist()) <= {0, *VALID_VISIBILITIES}:
        raise RuntimeError(f"Invalid visibility in {path}")
    return {
        "loaded_allow_pickle_false": True,
        "array_names_exact": True,
        "shapes_and_dtypes_valid": True,
        "finite": True,
        "labels_binary": True,
        "count": n,
        "dtypes": {key: str(value.dtype) for key, value in arrays.items()},
    }


def contrast_stretch(crop: np.ndarray) -> np.ndarray:
    low = float(np.min(crop))
    high = float(np.max(crop))
    if high <= low:
        return np.zeros(crop.shape, dtype=np.uint8)
    return np.clip((crop - low) * (255.0 / (high - low)), 0, 255).astype(np.uint8)


def create_preview(npz_paths: list[Path]) -> dict[str, list[dict]]:
    available = {kind: [] for kind in ("person", "hard_neg", "rand_neg")}
    for path in npz_paths:
        with np.load(path, allow_pickle=False) as data:
            for kind in available:
                indices = np.flatnonzero(data["kinds"] == kind)
                for index in indices:
                    available[kind].append((path, path.stem.removeprefix("crops_"), int(index)))
    rng = np.random.default_rng(0)
    tile_h, tile_w = 64 * 3, 32 * 3
    label_w = 110
    canvas = np.zeros((tile_h * 3, label_w + tile_w * 12), dtype=np.uint8)
    manifest: dict[str, list[dict]] = {}
    for row, kind in enumerate(("person", "hard_neg", "rand_neg")):
        if len(available[kind]) < 12:
            raise RuntimeError(f"Need 12 {kind} crops for preview, only have {len(available[kind])}")
        selected = rng.choice(len(available[kind]), size=12, replace=False)
        manifest[kind] = []
        cv2.putText(canvas, kind, (4, row * tile_h + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, 255, 1, cv2.LINE_AA)
        for column, selected_index in enumerate(selected):
            path, split, array_index = available[kind][int(selected_index)]
            with np.load(path, allow_pickle=False) as data:
                crop = data["crops"][array_index]
            tile = cv2.resize(contrast_stretch(crop), (tile_w, tile_h), interpolation=cv2.INTER_NEAREST)
            x0 = label_w + column * tile_w
            y0 = row * tile_h
            canvas[y0 : y0 + tile_h, x0 : x0 + tile_w] = tile
            manifest[kind].append({"split": split, "index": array_index})
    preview_path = DATA / "preview.png"
    if not cv2.imwrite(str(preview_path), canvas):
        raise RuntimeError(f"Failed to write {preview_path}")
    return manifest


def main() -> None:
    output_images = DATA / "images_lepton"
    output_annotations = DATA / "annotations"
    if output_images.exists() or output_annotations.exists() or any((DATA / f"crops_{s}.npz").exists() for s in SPLITS):
        raise RuntimeError("Refusing to overwrite existing generated outputs")
    output_images.mkdir()
    output_annotations.mkdir()

    source_data: dict[str, dict] = {}
    sequences: dict[str, set[str]] = {}
    for split in SPLITS:
        annotation_path = SOURCE / "filtered" / f"{split}.json"
        data = json.loads(annotation_path.read_text())
        if not all(key in data for key in ("images", "annotations", "categories")):
            raise RuntimeError(f"Missing COCO keys in {annotation_path}")
        source_data[split] = data
        sequences[split] = {Path(image["file_name"]).parts[0] for image in data["images"]}
    for index, left in enumerate(SPLITS):
        for right in SPLITS[index + 1 :]:
            overlap = sequences[left] & sequences[right]
            if overlap:
                raise RuntimeError(f"Sequences overlap between {left} and {right}: {sorted(overlap)}")

    report = {
        "data_folder": str(DATA),
        "seed": 0,
        "sequence_overlap_check": True,
        "splits": {},
    }
    small_images: dict[str, dict[int, tuple[Path, str]]] = {}

    for split in SPLITS:
        data = source_data[split]
        written_images = []
        valid_image_ids: set[int] = set()
        small_images[split] = {}
        colour_skipped = 0
        for image_record in data["images"]:
            image_id = int(image_record["id"])
            rel = Path(image_record["file_name"])
            if len(rel.parts) < 2:
                raise RuntimeError(f"Image is not in a sequence folder: {rel}")
            source_path = SOURCE / "images" / rel
            if not source_path.is_file():
                raise RuntimeError(f"Missing listed image: {source_path}")
            gray, channel_mad = read_gray_or_colour(source_path)
            if gray is None:
                colour_skipped += 1
                continue
            old_h, old_w = gray.shape
            if old_w % 4 != 0 or old_h % 4 != 0:
                raise RuntimeError(f"Image dimensions not divisible by four: {source_path} is {old_w}x{old_h}")
            new_w, new_h = old_w // 4, old_h // 4
            small = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_AREA)
            new_rel = Path("images_lepton") / split / rel.parent / f"{rel.stem}.png"
            output_path = DATA / new_rel
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if not cv2.imwrite(str(output_path), small):
                raise RuntimeError(f"Failed to write {output_path}")
            updated = copy.deepcopy(image_record)
            updated["file_name"] = new_rel.as_posix()
            updated["width"] = new_w
            updated["height"] = new_h
            written_images.append(updated)
            valid_image_ids.add(image_id)
            small_images[split][image_id] = (output_path, rel.parts[0])

        written_annotations = []
        for annotation in data["annotations"]:
            if int(annotation["image_id"]) not in valid_image_ids:
                continue
            updated = copy.deepcopy(annotation)
            if "bbox" not in updated or len(updated["bbox"]) != 4:
                raise RuntimeError(f"Invalid bbox in annotation {updated.get('id')}")
            updated["bbox"] = [float(value) / 4.0 for value in updated["bbox"]]
            updated["area"] = float(updated["area"]) / 16.0
            written_annotations.append(updated)
        output_coco = copy.deepcopy(data)
        output_coco["images"] = written_images
        output_coco["annotations"] = written_annotations
        (output_annotations / f"{split}.json").write_text(json.dumps(output_coco, separators=(",", ":")))
        report["splits"][split] = {
            "images_listed": len(data["images"]),
            "pngs_written": len(written_images),
            "images_skipped_colour": colour_skipped,
        }

    npz_paths: list[Path] = []
    for split in SPLITS:
        data = source_data[split]
        categories = category_details(data["categories"])
        annotations_by_image: dict[int, list[dict]] = defaultdict(list)
        for annotation in data["annotations"]:
            annotations_by_image[int(annotation["image_id"])].append(annotation)
        images_by_sequence: dict[str, list[dict]] = defaultdict(list)
        for image_record in data["images"]:
            image_id = int(image_record["id"])
            if image_id in small_images[split]:
                seq = Path(image_record["file_name"]).parts[0]
                images_by_sequence[seq].append(image_record)

        rng = np.random.default_rng(0)
        records = {key: [] for key in EXPECTED_KEYS}
        seen_real_sizes: list[tuple[float, float]] = []
        skipped_small = 0
        skipped_unknown = 0
        crop_counts = Counter()
        pose_visibility = {pose: {str(vis): 0 for vis in VALID_VISIBILITIES} for pose in VALID_POSES}

        for seq in sorted(images_by_sequence):
            ordered = sorted(images_by_sequence[seq], key=lambda item: str(item["file_name"]))
            for frame_index, image_record in enumerate(ordered):
                if frame_index % 3 != 0:
                    continue
                image_id = int(image_record["id"])
                downscaled_path, _ = small_images[split][image_id]
                image = cv2.imread(str(downscaled_path), cv2.IMREAD_GRAYSCALE)
                if image is None:
                    raise RuntimeError(f"Could not re-read downscaled image: {downscaled_path}")
                all_annotations = annotations_by_image.get(image_id, [])
                person_boxes_for_overlap: list[list[float]] = []
                known_people: list[tuple[dict, tuple[str, int], tuple[float, float, float, float]]] = []
                for annotation in all_annotations:
                    x, y, w, h = (float(value) / 4.0 for value in annotation["bbox"])
                    box = (x, y, w, h)
                    person_boxes_for_overlap.append([x, y, w, h])
                    details = categories.get(int(annotation["category_id"]))
                    if details is None:
                        skipped_unknown += 1
                    else:
                        known_people.append((annotation, details, box))
                        seen_real_sizes.append((w, h))

                for _, (pose, visibility), box in known_people:
                    x, y, w, h = box
                    size_px = max(w, h)
                    if size_px < 8.0:
                        skipped_small += 1
                        continue
                    crop = crop_from_box(image, box, rng)
                    add_record(records, crop, 1.0, "person", pose, visibility, seq, size_px)
                    crop_counts["person"] += 1
                    pose_visibility[pose][str(visibility)] += 1

                if not seen_real_sizes:
                    continue
                expanded = expanded_person_boxes(person_boxes_for_overlap)
                candidates = hard_candidates(image)
                candidate_cursor = 0
                for _ in range(2):
                    size_index = int(rng.integers(0, len(seen_real_sizes)))
                    w, h = seen_real_sizes[size_index]
                    chosen = None
                    attempts = 0
                    while attempts < 20 and candidate_cursor < len(candidates):
                        cx, cy = candidates[candidate_cursor]
                        candidate_cursor += 1
                        attempts += 1
                        candidate_box = (cx - w / 2.0, cy - h / 2.0, w, h)
                        if not overlaps_expanded(candidate_box, expanded):
                            chosen = candidate_box
                            break
                    if chosen is not None:
                        crop = crop_from_box(image, chosen, rng)
                        add_record(records, crop, 0.0, "hard_neg", "", 0, seq, max(w, h))
                        crop_counts["hard_neg"] += 1

                image_h, image_w = image.shape
                for _ in range(2):
                    size_index = int(rng.integers(0, len(seen_real_sizes)))
                    w, h = seen_real_sizes[size_index]
                    chosen = None
                    for _attempt in range(20):
                        cx = float(rng.uniform(0.0, image_w))
                        cy = float(rng.uniform(0.0, image_h))
                        candidate_box = (cx - w / 2.0, cy - h / 2.0, w, h)
                        if not overlaps_expanded(candidate_box, expanded):
                            chosen = candidate_box
                            break
                    if chosen is not None:
                        crop = crop_from_box(image, chosen, rng)
                        add_record(records, crop, 0.0, "rand_neg", "", 0, seq, max(w, h))
                        crop_counts["rand_neg"] += 1

        arrays = make_arrays(records)
        npz_path = DATA / f"crops_{split}.npz"
        np.savez_compressed(npz_path, **arrays)
        npz_paths.append(npz_path)
        report["splits"][split].update(
            {
                "crops_total": int(len(arrays["labels"])),
                "person_crops": int(crop_counts["person"]),
                "hard_neg_crops": int(crop_counts["hard_neg"]),
                "rand_neg_crops": int(crop_counts["rand_neg"]),
                "people_skipped_too_small": skipped_small,
                "people_skipped_unknown": skipped_unknown,
                "person_counts_pose_visibility": pose_visibility,
            }
        )

    report["npz_checks"] = {split: validate_npz(DATA / f"crops_{split}.npz") for split in SPLITS}
    report["preview_manifest"] = create_preview(npz_paths)
    (DATA / "prep_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
