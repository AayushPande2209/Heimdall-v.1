#!/usr/bin/env python3
"""Prepare the full ForestPersonsIR crop dataset.

Run with: python3 -m data_prep.prepare_full
"""
import copy
import json
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np

SRC = Path('/Users/aayush/ForestPersonsIR_full')
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'fpir_full'
SPLITS = ('train', 'val', 'test')
POSES = ('standing', 'sitting', 'lying')
VIS = (100, 70, 40, 20)
KEYS = ('crops', 'labels', 'kinds', 'pose', 'visibility', 'seq', 'size_px')
crop_rng = np.random.default_rng(0)
preview_rng = np.random.default_rng(0)
preview = {kind: [] for kind in ('person', 'hard_neg', 'rand_neg')}
preview_seen = Counter()


def gray(path):
    im = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if im is None or im.dtype != np.uint8:
        raise RuntimeError(f'Cannot read 8-bit image: {path}')
    if im.ndim == 2:
        return im
    if im.ndim == 3 and im.shape[2] == 3:
        a, b, c = cv2.split(im)
        mad = sum(float(np.mean(cv2.absdiff(x, y), dtype=np.float64))
                  for x, y in ((a, b), (a, c), (b, c))) / 3
        return a if mad < 8 else None
    raise RuntimeError(f'Unexpected image shape {im.shape}: {path}')


def category_map(categories):
    result = {}
    for item in categories:
        name = item['name']
        if name == 'unknown_0':
            result[item['id']] = None
        else:
            pose, vis = name.rsplit('_', 1)
            if pose not in POSES or int(vis) not in VIS:
                raise RuntimeError(f'Unexpected category {name}')
            result[item['id']] = (pose, int(vis))
    return result


def geometry(box):
    x, y, w, h = box
    side = max(h, 2 * w) * float(crop_rng.uniform(1.2, 1.5))
    cx = x + w / 2 + float(crop_rng.normal(0, .08 * w))
    cy = y + h / 2 + float(crop_rng.normal(0, .08 * h))
    return side, cx, cy


def inside(g, width, height):
    side, cx, cy = g
    return cx - side / 4 >= 0 and cx + side / 4 <= width and cy - side / 2 >= 0 and cy + side / 2 <= height


def crop(im, g):
    side, cx, cy = g
    patch = cv2.getRectSubPix(im, (max(1, round(side / 2)), max(1, round(side))), (cx, cy))
    return cv2.resize(patch, (32, 64), interpolation=cv2.INTER_LINEAR).astype(np.float32)


def intersects(box, people):
    x, y, w, h = box
    for px, py, pw, ph in people:
        if x < px + 1.25 * pw and x + w > px - .25 * pw and y < py + 1.25 * ph and y + h > py - .25 * ph:
            return True
    return False


def candidates(im):
    blurred = cv2.GaussianBlur(im.astype(np.float32), (3, 3), .8)
    response = blurred - cv2.medianBlur(im, 15).astype(np.float32)
    peak = response == cv2.dilate(response, np.ones((7, 7), np.uint8))
    ys, xs = np.nonzero(peak & (response > 3))
    order = np.argsort(response[ys, xs], kind='stable')[::-1]
    return [(float(xs[i]), float(ys[i])) for i in order]


def take_preview(kind, image):
    preview_seen[kind] += 1
    n = preview_seen[kind]
    if len(preview[kind]) < 12:
        preview[kind].append(image.copy())
    else:
        j = int(preview_rng.integers(n))
        if j < 12:
            preview[kind][j] = image.copy()


def write_preview():
    tile_h, tile_w, label_w = 192, 96, 110
    canvas = np.zeros((tile_h * 3, label_w + tile_w * 12), np.uint8)
    for row, kind in enumerate(('person', 'hard_neg', 'rand_neg')):
        if len(preview[kind]) != 12:
            raise RuntimeError(f'Not enough preview crops: {kind}')
        cv2.putText(canvas, kind, (3, row * tile_h + 28), cv2.FONT_HERSHEY_SIMPLEX, .55, 255, 1)
        for col, sample in enumerate(preview[kind]):
            lo, hi = float(sample.min()), float(sample.max())
            stretched = np.zeros_like(sample, np.uint8) if hi <= lo else np.clip((sample - lo) * 255 / (hi - lo), 0, 255).astype(np.uint8)
            canvas[row * tile_h:(row + 1) * tile_h, label_w + col * tile_w:label_w + (col + 1) * tile_w] = cv2.resize(stretched, (tile_w, tile_h), interpolation=cv2.INTER_NEAREST)
    if not cv2.imwrite(str(OUT / 'preview.png'), canvas):
        raise RuntimeError('Preview write failed')


def main():
    if any((OUT / f'crops_{s}.npz').exists() for s in SPLITS):
        raise RuntimeError('Refusing to overwrite completed crop files')
    if any((OUT / 'annotations' / f'{s}.json').exists() or (OUT / 'images_lepton' / s).exists()
           for s in ('val', 'test')):
        raise RuntimeError('Unexpected existing val/test outputs')
    source = {s: json.loads((SRC / 'annotations' / f'{s}.json').read_text()) for s in SPLITS}
    seqs = {s: {Path(im['file_name']).parts[0] for im in source[s]['images']} for s in SPLITS}
    if any(seqs[a] & seqs[b] for a, b in (('train', 'val'), ('train', 'test'), ('val', 'test'))):
        raise RuntimeError('Split sequence overlap')
    report = {'source': str(SRC), 'sequence_overlap': False, 'splits': {}}
    (OUT / 'images_lepton').mkdir(exist_ok=True)
    (OUT / 'annotations').mkdir(exist_ok=True)

    for split in SPLITS:
        data = source[split]
        image_records = []
        accepted = set()
        by_seq = defaultdict(list)
        missing, colour = [], 0
        reuse_train = split == 'train' and (OUT / 'annotations' / 'train.json').exists()
        if reuse_train:
            existing = json.loads((OUT / 'annotations' / 'train.json').read_text())
            image_records = existing['images']
            accepted = {record['id'] for record in image_records}
            missing = [record['file_name'] for record in data['images']
                       if record['id'] not in accepted and not (SRC / 'images' / record['file_name']).is_file()]
            if len(accepted) != len(image_records) or len(accepted) + len(missing) != len(data['images']):
                raise RuntimeError('Existing train annotations do not match available source images')
            for record in data['images']:
                if record['id'] in accepted:
                    rel = Path(record['file_name'])
                    destination = OUT / 'images_lepton' / split / rel.parent / (rel.stem + '.png')
                    if not destination.is_file():
                        raise RuntimeError(f'Missing existing train PNG: {destination}')
                    by_seq[rel.parts[0]].append((record, destination))
            print(f'reusing {len(image_records)} train PNGs and transformed annotations', flush=True)
        for i, record in enumerate(() if reuse_train else data['images'], 1):
            rel = Path(record['file_name'])
            path = SRC / 'images' / rel
            if not path.is_file():
                missing.append(str(rel))
                continue
            im = gray(path)
            if im is None:
                colour += 1
                continue
            h, w = im.shape
            if w % 4 or h % 4:
                raise RuntimeError(f'Image dimensions not divisible by 4: {path}')
            small = cv2.resize(im, (w // 4, h // 4), interpolation=cv2.INTER_AREA)
            new_rel = Path('images_lepton') / split / rel.parent / (rel.stem + '.png')
            destination = OUT / new_rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not cv2.imwrite(str(destination), small):
                raise RuntimeError(f'PNG write failed: {destination}')
            updated = copy.deepcopy(record)
            updated.update(file_name=new_rel.as_posix(), width=w // 4, height=h // 4)
            image_records.append(updated)
            accepted.add(record['id'])
            by_seq[rel.parts[0]].append((record, destination))
            if i % 5000 == 0:
                print(f'{split} downscaled {i}/{len(data["images"])} listed images', flush=True)

        annotations = existing['annotations'] if reuse_train else []
        by_image = defaultdict(list)
        if not reuse_train:
            for item in data['annotations']:
                if item['image_id'] not in accepted:
                    continue
                updated = copy.deepcopy(item)
                updated['bbox'] = [float(v) / 4 for v in item['bbox']]
                updated['area'] = float(item['area']) / 16
                annotations.append(updated)
            output_coco = copy.deepcopy(data)
            output_coco.update(images=image_records, annotations=annotations)
            (OUT / 'annotations' / f'{split}.json').write_text(json.dumps(output_coco, separators=(',', ':')))
        for item in annotations:
            by_image[item['image_id']].append(item)

        selected = [entry for seq in sorted(by_seq) for entry in sorted(by_seq[seq], key=lambda e: e[0]['file_name'])[::3]]
        capacity = sum(len(by_image[record['id']]) + 4 for record, _ in selected)
        temp = OUT / f'.{split}_crops_work.npy'
        crops = np.lib.format.open_memmap(temp, mode='w+', dtype=np.float32, shape=(capacity, 64, 32))
        fields = {key: [] for key in KEYS if key != 'crops'}
        counts = Counter()
        cross = {pose: {str(v): 0 for v in VIS} for pose in POSES}
        sizes = []
        n = 0
        categories = category_map(data['categories'])
        names_by_id = {record['id']: record['file_name'] for record in data['images']}
        nonstandard = [item for item in data['annotations'] if item['category_id'] not in categories]
        nonstandard_images = Counter(names_by_id[item['image_id']] for item in nonstandard)
        edge_count = 0

        def append(image, label, kind, pose, visibility, seq, size_px):
            nonlocal n
            crops[n] = image
            n += 1
            for key, value in zip(fields, (label, kind, pose, visibility, seq, size_px)):
                fields[key].append(value)
            counts[kind] += 1
            take_preview(kind, image)

        for i, (record, path) in enumerate(selected, 1):
            im = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if im is None:
                raise RuntimeError(f'Cannot reread PNG {path}')
            height, width = im.shape
            person_boxes, people = [], []
            for ann in by_image[record['id']]:
                box = tuple(ann['bbox'])
                person_boxes.append(box)
                detail = categories.get(ann['category_id'])
                if ann['category_id'] not in categories:
                    counts['nonstandard_skipped'] += 1
                elif detail is None:
                    counts['unknown_skipped'] += 1
                else:
                    sizes.append((box[2], box[3]))
                    people.append((box, detail))
            seq = Path(record['file_name']).parts[0]
            for box, (pose, visibility) in people:
                size_px = max(box[2:])
                if size_px < 8:
                    counts['small_skipped'] += 1
                    continue
                g = geometry(box)
                edge_count += not inside(g, width, height)
                append(crop(im, g), 1., 'person', pose, visibility, seq, size_px)
                cross[pose][str(visibility)] += 1
            if not sizes:
                continue
            spots = candidates(im)
            cursor = 0
            for _ in range(2):
                w, h = sizes[int(crop_rng.integers(len(sizes)))]
                for _attempt in range(20):
                    if cursor >= len(spots):
                        break
                    cx, cy = spots[cursor]
                    cursor += 1
                    box = (cx - w / 2, cy - h / 2, w, h)
                    g = geometry(box)
                    if not intersects(box, person_boxes) and inside(g, width, height):
                        append(crop(im, g), 0., 'hard_neg', '', 0, seq, max(w, h))
                        break
            for _ in range(2):
                w, h = sizes[int(crop_rng.integers(len(sizes)))]
                for _attempt in range(20):
                    side = max(h, 2 * w) * float(crop_rng.uniform(1.2, 1.5))
                    dx = float(crop_rng.normal(0, .08 * w))
                    dy = float(crop_rng.normal(0, .08 * h))
                    if side / 2 > width or side > height:
                        continue
                    cx = float(crop_rng.uniform(side / 4, width - side / 4))
                    cy = float(crop_rng.uniform(side / 2, height - side / 2))
                    box = (cx - dx - w / 2, cy - dy - h / 2, w, h)
                    g = (side, cx, cy)
                    if not intersects(box, person_boxes) and inside(g, width, height):
                        append(crop(im, g), 0., 'rand_neg', '', 0, seq, max(w, h))
                        break
            if i % 5000 == 0:
                print(f'{split} cropped {i}/{len(selected)} frames', flush=True)

        crops.flush()
        arrays = dict(crops=crops[:n], labels=np.asarray(fields['labels'], np.float32),
                      kinds=np.asarray(fields['kinds'], dtype='<U8'), pose=np.asarray(fields['pose'], dtype='<U8'),
                      visibility=np.asarray(fields['visibility'], np.int32),
                      seq=np.asarray(fields['seq'], dtype=f'<U{max(map(len, fields["seq"]), default=1)}'),
                      size_px=np.asarray(fields['size_px'], np.float32))
        target = OUT / f'crops_{split}.npz'
        np.savez_compressed(target, **arrays)
        del arrays, crops
        temp.unlink()
        with np.load(target, allow_pickle=False) as check:
            if set(check.files) != set(KEYS) or check['crops'].shape != (n, 64, 32):
                raise RuntimeError(f'NPZ shape/keys check failed: {split}')
            if any(check[k].shape != (n,) for k in KEYS if k != 'crops'):
                raise RuntimeError(f'NPZ vector shape check failed: {split}')
            if any(check[k].dtype.kind != 'U' for k in ('kinds', 'pose', 'seq')):
                raise RuntimeError(f'NPZ string dtype check failed: {split}')
            if not (check['crops'].dtype == np.float32 and check['labels'].dtype == np.float32
                    and check['visibility'].dtype == np.int32 and check['size_px'].dtype == np.float32):
                raise RuntimeError(f'NPZ numeric dtype check failed: {split}')
            if not all(np.isfinite(check[k]).all() for k in ('crops', 'labels', 'size_px')):
                raise RuntimeError(f'Nonfinite value: {split}')
            if not set(np.unique(check['labels'])) <= {0., 1.}:
                raise RuntimeError(f'Nonbinary labels: {split}')
        report['splits'][split] = dict(images_listed=len(data['images']), images_missing=len(missing),
                                     missing_names=missing, pngs_written=len(image_records), images_skipped_colour=colour,
                                     sequences=len(by_seq), person_crops=counts['person'], hard_neg_crops=counts['hard_neg'],
                                     rand_neg_crops=counts['rand_neg'], people_skipped_small=counts['small_skipped'],
                                     people_skipped_unknown=counts['unknown_skipped'], person_edge_windows=edge_count,
                                     nonstandard_annotations=len(nonstandard),
                                     nonstandard_images=dict(sorted(nonstandard_images.items())),
                                     nonstandard_crop_skipped=counts['nonstandard_skipped'],
                                     person_edge_percent=100 * edge_count / counts['person'],
                                     pose_visibility=cross, npz_checks='PASS')
        print(f'{split} complete: {report["splits"][split]}', flush=True)
    write_preview()
    (OUT / 'prep_report.json').write_text(json.dumps(report, indent=2))
    print('ALL CHECKS PASSED', flush=True)


if __name__ == '__main__':
    main()
