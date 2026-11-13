#!/usr/bin/env python3
"""Regenerate partial crop NPZs with in-bounds negative windows.

Run with: python3 -m data_prep.regenerate_crops_inbounds
"""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np

from .prepare_data import (
    DATA,
    SOURCE,
    SPLITS,
    add_record,
    category_details,
    create_preview,
    expanded_person_boxes,
    hard_candidates,
    make_arrays,
    overlaps_expanded,
    validate_npz,
)


def sample_geometry(box, rng):
    x, y, w, h = box
    side = max(h, 2.0 * w) * float(rng.uniform(1.2, 1.5))
    dx = float(rng.normal(0.0, 0.08 * w))
    dy = float(rng.normal(0.0, 0.08 * h))
    cx = x + w / 2.0 + dx
    cy = y + h / 2.0 + dy
    return side, cx, cy, dx, dy


def extract_geometry(image, geometry):
    side, cx, cy, _dx, _dy = geometry
    patch_w = max(1, int(round(side / 2.0)))
    patch_h = max(1, int(round(side)))
    patch = cv2.getRectSubPix(image, (patch_w, patch_h), (cx, cy))
    return cv2.resize(patch, (32, 64), interpolation=cv2.INTER_LINEAR).astype(np.float32, copy=False)


def window_is_inside(geometry, image_w, image_h):
    side, cx, cy, _dx, _dy = geometry
    return cx - side / 4.0 >= 0.0 and cx + side / 4.0 <= image_w and cy - side / 2.0 >= 0.0 and cy + side / 2.0 <= image_h


def consume_legacy_negatives(image, expanded, seen_sizes, rng):
    """Advance the original RNG exactly, preserving all later person crops."""
    candidates = hard_candidates(image)
    candidate_cursor = 0
    for _ in range(2):
        w, h = seen_sizes[int(rng.integers(0, len(seen_sizes)))]
        chosen = None
        attempts = 0
        while attempts < 20 and candidate_cursor < len(candidates):
            cx, cy = candidates[candidate_cursor]
            candidate_cursor += 1
            attempts += 1
            box = (cx - w / 2.0, cy - h / 2.0, w, h)
            if not overlaps_expanded(box, expanded):
                chosen = box
                break
        if chosen is not None:
            extract_geometry(image, sample_geometry(chosen, rng))

    image_h, image_w = image.shape
    for _ in range(2):
        w, h = seen_sizes[int(rng.integers(0, len(seen_sizes)))]
        chosen = None
        for _attempt in range(20):
            cx = float(rng.uniform(0.0, image_w))
            cy = float(rng.uniform(0.0, image_h))
            box = (cx - w / 2.0, cy - h / 2.0, w, h)
            if not overlaps_expanded(box, expanded):
                chosen = box
                break
        if chosen is not None:
            extract_geometry(image, sample_geometry(chosen, rng))


def add_new_negatives(image, expanded, seen_sizes, seq, rng, records, counts):
    image_h, image_w = image.shape
    candidates = hard_candidates(image)
    candidate_cursor = 0
    for _ in range(2):
        w, h = seen_sizes[int(rng.integers(0, len(seen_sizes)))]
        chosen_geometry = None
        attempts = 0
        while attempts < 20 and candidate_cursor < len(candidates):
            cx, cy = candidates[candidate_cursor]
            candidate_cursor += 1
            attempts += 1
            box = (cx - w / 2.0, cy - h / 2.0, w, h)
            geometry = sample_geometry(box, rng)
            if overlaps_expanded(box, expanded) or not window_is_inside(geometry, image_w, image_h):
                continue
            chosen_geometry = geometry
            break
        if chosen_geometry is not None:
            add_record(records, extract_geometry(image, chosen_geometry), 0.0, "hard_neg", "", 0, seq, max(w, h))
            counts["hard_neg"] += 1

    for _ in range(2):
        w, h = seen_sizes[int(rng.integers(0, len(seen_sizes)))]
        chosen_geometry = None
        for _attempt in range(20):
            side = max(h, 2.0 * w) * float(rng.uniform(1.2, 1.5))
            dx = float(rng.normal(0.0, 0.08 * w))
            dy = float(rng.normal(0.0, 0.08 * h))
            half_window_w = side / 4.0
            half_window_h = side / 2.0
            if 2.0 * half_window_w > image_w or 2.0 * half_window_h > image_h:
                continue
            final_cx = float(rng.uniform(half_window_w, image_w - half_window_w))
            final_cy = float(rng.uniform(half_window_h, image_h - half_window_h))
            nominal_cx = final_cx - dx
            nominal_cy = final_cy - dy
            box = (nominal_cx - w / 2.0, nominal_cy - h / 2.0, w, h)
            geometry = (side, final_cx, final_cy, dx, dy)
            if overlaps_expanded(box, expanded):
                continue
            if not window_is_inside(geometry, image_w, image_h):
                raise RuntimeError("Internal error: constrained random window is out of bounds")
            chosen_geometry = geometry
            break
        if chosen_geometry is not None:
            add_record(records, extract_geometry(image, chosen_geometry), 0.0, "rand_neg", "", 0, seq, max(w, h))
            counts["rand_neg"] += 1


def assert_people_unchanged(old_path, new_arrays):
    with np.load(old_path, allow_pickle=False) as old:
        old_indices = np.flatnonzero(old["kinds"] == "person")
        old_people = {key: old[key][old_indices] for key in old.files}
    new_indices = np.flatnonzero(new_arrays["kinds"] == "person")
    if len(old_indices) != len(new_indices):
        raise RuntimeError(f"Person count changed for {old_path.name}")
    for key, old_values in old_people.items():
        new_values = new_arrays[key][new_indices]
        if not np.array_equal(old_values, new_values):
            raise RuntimeError(f"Person data changed in {old_path.name}:{key}")


def main():
    report_path = DATA / "prep_report.json"
    report = json.loads(report_path.read_text())
    temp_paths = []
    new_stats = {}

    for split in SPLITS:
        source = json.loads((SOURCE / "filtered" / f"{split}.json").read_text())
        categories = category_details(source["categories"])
        annotations_by_image = defaultdict(list)
        for annotation in source["annotations"]:
            annotations_by_image[int(annotation["image_id"])].append(annotation)
        images_by_sequence = defaultdict(list)
        for image_record in source["images"]:
            images_by_sequence[Path(image_record["file_name"]).parts[0]].append(image_record)

        legacy_rng = np.random.default_rng(0)
        negative_rng = np.random.default_rng(0)
        records = {key: [] for key in ("crops", "labels", "kinds", "pose", "visibility", "seq", "size_px")}
        seen_real_sizes = []
        counts = Counter()
        person_windows_total = 0
        person_windows_past_edge = 0

        for seq in sorted(images_by_sequence):
            ordered = sorted(images_by_sequence[seq], key=lambda item: str(item["file_name"]))
            for frame_index, image_record in enumerate(ordered):
                if frame_index % 3 != 0:
                    continue
                image_id = int(image_record["id"])
                rel = Path(image_record["file_name"])
                downscaled = DATA / "images_lepton" / split / rel.parent / f"{rel.stem}.png"
                image = cv2.imread(str(downscaled), cv2.IMREAD_GRAYSCALE)
                if image is None:
                    raise RuntimeError(f"Could not read {downscaled}")
                image_h, image_w = image.shape
                person_boxes = []
                known_people = []
                for annotation in annotations_by_image.get(image_id, []):
                    x, y, w, h = (float(value) / 4.0 for value in annotation["bbox"])
                    box = (x, y, w, h)
                    person_boxes.append([x, y, w, h])
                    details = categories.get(int(annotation["category_id"]))
                    if details is not None:
                        known_people.append((details, box))
                        seen_real_sizes.append((w, h))

                for (pose, visibility), box in known_people:
                    x, y, w, h = box
                    if max(w, h) < 8.0:
                        continue
                    geometry = sample_geometry(box, legacy_rng)
                    person_windows_total += 1
                    if not window_is_inside(geometry, image_w, image_h):
                        person_windows_past_edge += 1
                    add_record(records, extract_geometry(image, geometry), 1.0, "person", pose, visibility, seq, max(w, h))
                    counts["person"] += 1

                if not seen_real_sizes:
                    continue
                expanded = expanded_person_boxes(person_boxes)
                consume_legacy_negatives(image, expanded, seen_real_sizes, legacy_rng)
                add_new_negatives(image, expanded, seen_real_sizes, seq, negative_rng, records, counts)

        arrays = make_arrays(records)
        old_path = DATA / f"crops_{split}.npz"
        assert_people_unchanged(old_path, arrays)
        temp_path = DATA / f"crops_{split}.new.npz"
        np.savez_compressed(temp_path, **arrays)
        validate_npz(temp_path)
        temp_paths.append((temp_path, old_path))
        new_stats[split] = {
            "crops_total": int(len(arrays["labels"])),
            "person_crops": int(counts["person"]),
            "hard_neg_crops": int(counts["hard_neg"]),
            "rand_neg_crops": int(counts["rand_neg"]),
            "person_windows_total": person_windows_total,
            "person_windows_past_edge": person_windows_past_edge,
            "person_windows_past_edge_percent": 100.0 * person_windows_past_edge / person_windows_total,
            "person_crops_verified_unchanged": True,
        }

    for temp_path, final_path in temp_paths:
        os.replace(temp_path, final_path)

    report["negative_window_rule"] = "hard_neg and rand_neg crop windows lie completely inside the image"
    for split, stats in new_stats.items():
        report["splits"][split].update(stats)
        report["npz_checks"][split] = validate_npz(DATA / f"crops_{split}.npz")
    report["preview_manifest"] = create_preview([DATA / f"crops_{split}.npz" for split in SPLITS])
    report_path.write_text(json.dumps(report, indent=2))
    print(json.dumps(new_stats, indent=2))


if __name__ == "__main__":
    main()
