"""Replay v1 order and replace negatives while matching edge rates.

Run with: python3 -m data_prep.regenerate_edge_negatives
"""
import json
import shutil
import zipfile
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

from . import prepare_full as prep

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'fpir_full'
SPLITS = ('train', 'val')
legacy = np.random.default_rng(0)
new = np.random.default_rng(0)


def old_crops(split):
    path = DATA / 'backup_v1' / f'crops_{split}_v1.npz'
    temp = DATA / f'.{split}_v1_crops.npy'
    if temp.exists():
        raise RuntimeError(f'Unexpected temporary file {temp}')
    with zipfile.ZipFile(path) as archive, archive.open('crops.npy') as source, temp.open('wb') as target:
        shutil.copyfileobj(source, target)
    return temp, np.load(temp, mmap_mode='r')


def replay_old_negatives(im, boxes, sizes, old_kinds, index, seq):
    spots = prep.candidates(im)
    cursor = 0
    hard = rand = 0
    for _ in range(2):
        w, h = sizes[int(legacy.integers(len(sizes)))]
        for _attempt in range(20):
            if cursor >= len(spots):
                break
            cx, cy = spots[cursor]
            cursor += 1
            box = (cx - w / 2, cy - h / 2, w, h)
            g = old_geometry(box)
            if not prep.intersects(box, boxes) and prep.inside(g, im.shape[1], im.shape[0]):
                if old_kinds[index + hard] != 'hard_neg':
                    raise RuntimeError(f'Old hard-negative order mismatch in {seq}')
                hard += 1
                break
    index += hard
    for _ in range(2):
        w, h = sizes[int(legacy.integers(len(sizes)))]
        for _attempt in range(20):
            side = max(h, 2 * w) * float(legacy.uniform(1.2, 1.5))
            dx = float(legacy.normal(0, .08 * w))
            dy = float(legacy.normal(0, .08 * h))
            if side / 2 > im.shape[1] or side > im.shape[0]:
                continue
            cx = float(legacy.uniform(side / 4, im.shape[1] - side / 4))
            cy = float(legacy.uniform(side / 2, im.shape[0] - side / 2))
            box = (cx - dx - w / 2, cy - dy - h / 2, w, h)
            if not prep.intersects(box, boxes) and prep.inside((side, cx, cy), im.shape[1], im.shape[0]):
                if old_kinds[index + rand] != 'rand_neg':
                    raise RuntimeError(f'Old random-negative order mismatch in {seq}')
                rand += 1
                break
    return hard, rand


def old_geometry(box):
    x, y, w, h = box
    side = max(h, 2 * w) * float(legacy.uniform(1.2, 1.5))
    cx = x + w / 2 + float(legacy.normal(0, .08 * w))
    cy = y + h / 2 + float(legacy.normal(0, .08 * h))
    return side, cx, cy


def edge_condition(g, width, height, want_edge):
    _, cx, cy = g
    if not (0 <= cx < width and 0 <= cy < height):
        return False
    return prep.inside(g, width, height) != want_edge


def hard_crop(im, boxes, sizes, spots, used, want_edge):
    height, width = im.shape
    # Strongest eligible bright spots first; each attempt uses a new real-person box size.
    attempts = 0
    for spot_index, (cx, cy) in enumerate(spots):
        if spot_index in used:
            continue
        for _ in range(2):
            w, h = sizes[int(new.integers(len(sizes)))]
            box = (cx - w / 2, cy - h / 2, w, h)
            if prep.intersects(box, boxes):
                continue
            side = max(h, 2 * w) * float(new.uniform(1.2, 1.5))
            if want_edge:
                # A spot can only produce an edge window if it is close enough to an edge.
                if cx > side * .375 and cx < width - side * .375 and cy > side * .75 and cy < height - side * .75:
                    continue
            else:
                if cx < side * .15 or cx > width - side * .15 or cy < side * .3 or cy > height - side * .3:
                    continue
            g = (side, cx + float(new.normal(0, .08 * w)), cy + float(new.normal(0, .08 * h)))
            attempts += 1
            if edge_condition(g, width, height, want_edge):
                used.add(spot_index)
                return prep.crop(im, g), max(w, h)
            if attempts >= 20:
                return None
    return None


def random_crop(im, boxes, sizes, want_edge):
    height, width = im.shape
    for _ in range(20):
        w, h = sizes[int(new.integers(len(sizes)))]
        side = max(h, 2 * w) * float(new.uniform(1.2, 1.5))
        dx = float(new.normal(0, .08 * w))
        dy = float(new.normal(0, .08 * h))
        if not want_edge and (side / 2 > width or side > height):
            continue
        if want_edge:
            edge = int(new.integers(4))
            cx = float(new.uniform(0, min(width, side / 4))) if edge == 0 else (
                 float(new.uniform(max(0, width - side / 4), width)) if edge == 1 else float(new.uniform(0, width)))
            cy = float(new.uniform(0, min(height, side / 2))) if edge == 2 else (
                 float(new.uniform(max(0, height - side / 2), height)) if edge == 3 else float(new.uniform(0, height)))
        else:
            cx = float(new.uniform(side / 4, width - side / 4))
            cy = float(new.uniform(side / 2, height - side / 2))
        box = (cx - dx - w / 2, cy - dy - h / 2, w, h)
        g = (side, cx, cy)
        if not prep.intersects(box, boxes) and edge_condition(g, width, height, want_edge):
            return prep.crop(im, g), max(w, h)
    return None


def main():
    summary = {}
    for split in SPLITS:
        original = DATA / 'backup_v1' / f'crops_{split}_v1.npz'
        with np.load(original, allow_pickle=False) as archive:
            metadata = {k: archive[k] for k in prep.KEYS if k != 'crops'}
        old_temp, old = old_crops(split)
        out_temp = DATA / f'.{split}_edge_crops.npy'
        target = DATA / f'crops_{split}_step1.npz'
        if out_temp.exists() or target.exists():
            raise RuntimeError(f'Unexpected existing Step 1 output for {split}')
        out = np.lib.format.open_memmap(out_temp, mode='w+', dtype=np.float32, shape=old.shape)
        coco = json.loads((DATA / 'annotations' / f'{split}.json').read_text())
        by_image = defaultdict(list)
        for ann in coco['annotations']:
            by_image[ann['image_id']].append(ann)
        by_seq = defaultdict(list)
        for image in coco['images']:
            by_seq[Path(image['file_name']).parts[2]].append(image)
        categories = prep.category_map(coco['categories'])
        p = prep_report[split]['person_edge_windows'] / prep_report[split]['person_crops']
        sizes, cursor, new_edge, new_neg = [], 0, 0, 0
        for seq in sorted(by_seq):
            for record in sorted(by_seq[seq], key=lambda e: e['file_name'])[::3]:
                im = cv2.imread(str(DATA / record['file_name']), cv2.IMREAD_GRAYSCALE)
                if im is None:
                    raise RuntimeError(f'Missing PNG {record["file_name"]}')
                boxes, people = [], []
                for ann in by_image[record['id']]:
                    box = tuple(ann['bbox'])
                    boxes.append(box)
                    detail = categories.get(ann['category_id'])
                    if detail is not None:
                        sizes.append((box[2], box[3]))
                        people.append((box, detail))
                for box, (pose, visibility) in people:
                    if max(box[2:]) < 8:
                        continue
                    old_geometry(box)
                    if metadata['kinds'][cursor] != 'person' or metadata['pose'][cursor] != pose or metadata['visibility'][cursor] != visibility or metadata['seq'][cursor] != seq:
                        raise RuntimeError(f'Person order mismatch: {split} {record["file_name"]}')
                    out[cursor] = old[cursor]
                    cursor += 1
                if not sizes:
                    continue
                hard_count, rand_count = replay_old_negatives(im, boxes, sizes, metadata['kinds'], cursor, seq)
                spots = prep.candidates(im)
                used = set()
                for kind, count in (('hard_neg', hard_count), ('rand_neg', rand_count)):
                    for _ in range(count):
                        want_edge = bool(new.random() < p)
                        result = (hard_crop(im, boxes, sizes, spots, used, want_edge) if kind == 'hard_neg'
                                  else random_crop(im, boxes, sizes, want_edge))
                        if result is None:
                            raise RuntimeError(f'Cannot preserve {kind} count in {split} {record["file_name"]} (edge={want_edge})')
                        image, size = result
                        if metadata['kinds'][cursor] != kind or metadata['seq'][cursor] != seq:
                            raise RuntimeError(f'Negative order mismatch: {split} {record["file_name"]}')
                        out[cursor] = image
                        metadata['size_px'][cursor] = size
                        cursor += 1
                        new_neg += 1
                        new_edge += want_edge
        if cursor != len(old):
            raise RuntimeError(f'Unreplayed crops in {split}: {cursor}/{len(old)}')
        rate = new_edge / new_neg
        if abs(rate - p) > .02:
            raise RuntimeError(f'Edge rate mismatch in {split}: {p:.4f} vs {rate:.4f}')
        out.flush()
        np.savez_compressed(target, crops=out, **metadata)
        del out, old
        out_temp.unlink()
        old_temp.unlink()
        with np.load(target, allow_pickle=False) as check:
            if set(check.files) != set(prep.KEYS) or check['crops'].shape[0] != cursor:
                raise RuntimeError(f'Step 1 NPZ check failed in {split}')
        summary[split] = dict(person_edge_rate=p, negative_edge_rate=rate, negative_edge_count=new_edge,
                              negative_count=new_neg, crops=cursor)
        print(split, summary[split], flush=True)
    (DATA / 'edge_report.json').write_text(json.dumps(summary, indent=2))


prep_report = json.loads((DATA / 'prep_report.json').read_text())['splits']
if __name__ == '__main__':
    main()
