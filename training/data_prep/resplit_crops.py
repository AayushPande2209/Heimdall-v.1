#!/usr/bin/env python3
"""Reassign partial crop records by whole sequence.

Run with: python3 -m training.data_prep.resplit_crops
"""

from pathlib import Path
import hashlib
import os

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "fpir_partial"
NEW_VAL = {
    "001_FPV_Person_summer_forest",
    "016_FPV_Person_summer_forest",
    "040_FPV_Person_summer_forest",
    "046_FPV_Person_summer_forest",
    "052_FPV_Person_summer_forest",
    "059_FPV_Person_summer_forest",
    "060_FPV_Person_summer_forest",
    "068_FPV_Person_summer_forest",
}
KEYS = ("crops", "labels", "kinds", "pose", "visibility", "seq", "size_px")


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    with np.load(path, allow_pickle=False) as archive:
        if set(archive.files) != set(KEYS):
            raise ValueError(f"Unexpected arrays in {path}")
        result = {key: archive[key] for key in KEYS}
    n = len(result["labels"])
    if result["crops"].shape != (n, 64, 32) or any(result[key].shape != (n,) for key in KEYS if key != "crops"):
        raise ValueError(f"Unexpected shapes in {path}")
    if any(result[key].dtype.kind == "O" for key in KEYS):
        raise ValueError(f"Object dtype in {path}")
    return result


def main():
    old_train = DATA / "crops_train_old.npz"
    old_val = DATA / "crops_val_old.npz"
    test_path = DATA / "crops_test.npz"
    originals = [(DATA / "crops_train.npz", old_train), (DATA / "crops_val.npz", old_val)]
    for current, backup in originals:
        if not current.is_file() or not backup.is_file():
            raise FileNotFoundError(f"Expected {current} and {backup}")
    test_hash = checksum(test_path)
    old = [load(old_train), load(old_val)]
    test = load(test_path)
    old_seqs = set(old[0]["seq"]) | set(old[1]["seq"])
    if not NEW_VAL <= old_seqs or old_seqs & set(test["seq"]):
        raise ValueError("Validation sequence missing or test sequence overlap")
    all_records = {key: np.concatenate([d[key] for d in old], axis=0) for key in KEYS}
    val_mask = np.isin(all_records["seq"], list(NEW_VAL))
    masks = {"train": ~val_mask, "val": val_mask}
    total_people = int(np.sum(all_records["labels"] == 1))
    val_people = int(np.sum(val_mask & (all_records["labels"] == 1)))
    if not (0.15 <= val_people / total_people <= 0.25):
        raise ValueError("Validation person share outside 15–25%")
    people = all_records["labels"] == 1
    for pose in ("standing", "sitting", "lying"):
        for visibility in (100, 70, 40, 20):
            cell = people & (all_records["pose"] == pose) & (all_records["visibility"] == visibility)
            if int(np.sum(cell & val_mask)) > int(np.sum(cell & ~val_mask)):
                raise ValueError(f"Training starved in {pose}_{visibility}")

    temp_files = {}
    for split, mask in masks.items():
        path = DATA / f"crops_{split}.resplit_tmp.npz"
        if path.exists():
            raise FileExistsError(path)
        selected = {key: all_records[key][mask] for key in KEYS}
        np.savez_compressed(path, **selected)
        check = load(path)
        for key in KEYS:
            if check[key].dtype != selected[key].dtype or not np.array_equal(check[key], selected[key]):
                raise ValueError(f"Round-trip mismatch in {split}:{key}")
        temp_files[split] = path

    if int(sum(np.sum(m) for m in masks.values())) != len(all_records["labels"]):
        raise ValueError("Crops not conserved")
    for label in (0, 1):
        before = int(np.sum(all_records["labels"] == label))
        after = sum(int(np.sum(all_records["labels"][mask] == label)) for mask in masks.values())
        if before != after:
            raise ValueError(f"Label count mismatch for {label}")
    train_seqs = set(all_records["seq"][masks["train"]])
    val_seqs = set(all_records["seq"][masks["val"]])
    test_seqs = set(test["seq"])
    if train_seqs & val_seqs or train_seqs & test_seqs or val_seqs & test_seqs:
        raise ValueError("Sequence overlap")
    if checksum(test_path) != test_hash:
        raise ValueError("Test checksum changed")

    for split in ("train", "val"):
        os.replace(temp_files[split], DATA / f"crops_{split}.npz")
    if checksum(test_path) != test_hash:
        raise ValueError("Test checksum changed after replacement")
    print("test SHA-256:", test_hash)
    print("pooled crops:", len(all_records["labels"]), "people:", total_people, "nonpeople:", int(np.sum(~people)))
    for split, mask in masks.items():
        print(split, "crops:", int(np.sum(mask)), "people:", int(np.sum(mask & people)), "nonpeople:", int(np.sum(mask & ~people)), "sequences:", len(set(all_records["seq"][mask])))
    print("validation person share:", 100 * val_people / total_people)
    print("round-trip, conservation, balance, sequence separation, test checksum: PASS")


if __name__ == "__main__":
    main()
