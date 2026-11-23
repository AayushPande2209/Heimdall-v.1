"""Move complete sequences between staged full-data crop files.

Run with: python3 -m training.data_prep.resplit_edge_crops
"""
import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'data' / 'fpir_full'
KEYS = ('crops', 'labels', 'kinds', 'pose', 'visibility', 'seq', 'size_px')
POSES = ('standing', 'sitting', 'lying')
VIS = (100, 70, 40, 20)
NEW_VAL = {
    f'{number:03d}_FPV_Person_summer_forest'
    for number in (2, 6, 7, 10, 16, 35, 37, 47, 49, 53, 62, 71, 83)
}


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def extract_crops(split):
    src = DATA / f'crops_{split}_step1.npz'
    dst = DATA / f'.{split}_step1_crops.npy'
    if dst.exists():
        raise RuntimeError(f'Unexpected temporary file: {dst}')
    with zipfile.ZipFile(src) as archive, archive.open('crops.npy') as inp, dst.open('wb') as out:
        shutil.copyfileobj(inp, out)
    return dst, np.load(dst, mmap_mode='r')


def make_preview(samples):
    tile_h, tile_w, label_w = 192, 96, 110
    canvas = np.zeros((tile_h * 3, label_w + tile_w * 12), np.uint8)
    for row, kind in enumerate(('person', 'hard_neg', 'rand_neg')):
        if len(samples[kind]) != 12:
            raise RuntimeError(f'Insufficient {kind} samples for preview')
        cv2.putText(canvas, kind, (3, row * tile_h + 28), cv2.FONT_HERSHEY_SIMPLEX, .55, 255, 1)
        for col, sample in enumerate(samples[kind]):
            lo, hi = float(sample.min()), float(sample.max())
            image = np.zeros_like(sample, np.uint8) if hi <= lo else np.clip((sample - lo) * 255 / (hi - lo), 0, 255).astype(np.uint8)
            canvas[row * tile_h:(row + 1) * tile_h, label_w + col * tile_w:label_w + (col + 1) * tile_w] = cv2.resize(image, (tile_w, tile_h), interpolation=cv2.INTER_NEAREST)
    if not cv2.imwrite(str(DATA / 'preview.png'), canvas):
        raise RuntimeError('Preview write failed')


def main():
    test_path = DATA / 'crops_test.npz'
    test_before = sha(test_path)
    if test_before != sha(DATA / 'backup_v1' / 'crops_test_v1.npz'):
        raise RuntimeError('Test file differs from backup before re-split')
    meta = {}
    for split in ('train', 'val'):
        with np.load(DATA / f'crops_{split}_step1.npz', allow_pickle=False) as data:
            if set(data.files) != set(KEYS):
                raise RuntimeError(f'Unexpected Step 1 keys in {split}')
            meta[split] = {k: data[k] for k in KEYS if k != 'crops'}
    old_counts = {s: len(meta[s]['labels']) for s in ('train', 'val')}
    all_seqs = set(meta['train']['seq']) | set(meta['val']['seq'])
    if not NEW_VAL <= all_seqs:
        raise RuntimeError('Chosen val sequence absent from pool')
    with np.load(test_path, allow_pickle=False) as test:
        test_seqs = set(test['seq'])
        test_cells = {
            pose: {str(v): int(np.sum((test['kinds'] == 'person') & (test['pose'] == pose) & (test['visibility'] == v))) for v in VIS}
            for pose in POSES
        }
    if all_seqs & test_seqs:
        raise RuntimeError('Pooled sequence overlaps test')

    masks = {split: np.isin(meta[split]['seq'], list(NEW_VAL)) for split in ('train', 'val')}
    person_pool = sum(int(np.sum(meta[s]['kinds'] == 'person')) for s in ('train', 'val'))
    person_val = sum(int(np.sum(masks[s] & (meta[s]['kinds'] == 'person'))) for s in ('train', 'val'))
    if not .15 <= person_val / person_pool <= .25:
        raise RuntimeError('Val person share outside 15–25%')
    cells = {}
    for dest in ('train', 'val'):
        cells[dest] = {pose: {} for pose in POSES}
        for pose in POSES:
            for v in VIS:
                count = 0
                for source in ('train', 'val'):
                    m = masks[source] if dest == 'val' else ~masks[source]
                    data = meta[source]
                    count += int(np.sum(m & (data['kinds'] == 'person') & (data['pose'] == pose) & (data['visibility'] == v)))
                cells[dest][pose][str(v)] = count
                if dest == 'val' and count > cells['train'][pose][str(v)]:
                    raise RuntimeError(f'Train starved in {pose}_{v}')
    if any(sum(cells['val'][pose].values()) < 100 for pose in POSES):
        raise RuntimeError('Val has under 100 people in a pose')
    if any(not count for pose in POSES for count in cells['val'][pose].values()):
        raise RuntimeError('Val lacks a pose/visibility cell')

    counts = {dest: sum(int(np.sum(masks[s] if dest == 'val' else ~masks[s])) for s in ('train', 'val'))
              for dest in ('train', 'val')}
    crops_temp = {}
    output = {}
    cursors = {'train': 0, 'val': 0}
    meta_parts = {dest: {key: [] for key in meta['train']} for dest in ('train', 'val')}
    rng = np.random.default_rng(0)
    samples = {k: [] for k in ('person', 'hard_neg', 'rand_neg')}
    seen = {k: 0 for k in samples}
    for dest in ('train', 'val'):
        tmp = DATA / f'.{dest}_resplit_crops.npy'
        if tmp.exists() or (DATA / f'crops_{dest}_new.npz').exists():
            raise RuntimeError(f'Unexpected staging file for {dest}')
        output[dest] = np.lib.format.open_memmap(tmp, mode='w+', dtype=np.float32, shape=(counts[dest], 64, 32))
        crops_temp[dest] = tmp
    source_temps = []
    for source in ('train', 'val'):
        temp, crops = extract_crops(source)
        source_temps.append(temp)
        if len(crops) != old_counts[source]:
            raise RuntimeError(f'Step 1 crop count mismatch for {source}')
        for dest in ('train', 'val'):
            mask = masks[source] if dest == 'val' else ~masks[source]
            indices = np.flatnonzero(mask)
            for key in meta[source]:
                meta_parts[dest][key].append(meta[source][key][indices])
            for start in range(0, len(indices), 1024):
                chunk = indices[start:start + 1024]
                end = cursors[dest] + len(chunk)
                output[dest][cursors[dest]:end] = crops[chunk]
                cursors[dest] = end
            # Reservoir samples from the resulting train/val pool, with fixed seed.
            for index in indices:
                kind = str(meta[source]['kinds'][index])
                seen[kind] += 1
                if len(samples[kind]) < 12:
                    samples[kind].append(crops[index].copy())
                else:
                    choice = int(rng.integers(seen[kind]))
                    if choice < 12:
                        samples[kind][choice] = crops[index].copy()
        del crops
        temp.unlink()
    for dest in ('train', 'val'):
        if cursors[dest] != counts[dest]:
            raise RuntimeError(f'Crop conservation failed in {dest}')
        output[dest].flush()
        arrays = {key: np.concatenate(meta_parts[dest][key]) for key in meta['train']}
        if len(arrays['labels']) != counts[dest] or any(arrays[k].dtype != meta['train'][k].dtype for k in arrays):
            raise RuntimeError(f'Metadata dtype/count mismatch in {dest}')
        target = DATA / f'crops_{dest}_new.npz'
        np.savez_compressed(target, crops=output[dest], **arrays)
        with np.load(target, allow_pickle=False) as check:
            if set(check.files) != set(KEYS) or check['crops'].shape != (counts[dest], 64, 32):
                raise RuntimeError(f'New NPZ shape/key mismatch in {dest}')
            if any(check[k].dtype != meta['train'][k].dtype for k in arrays):
                raise RuntimeError(f'New NPZ dtype mismatch in {dest}')
        del output[dest]
        crops_temp[dest].unlink()
    if sha(test_path) != test_before:
        raise RuntimeError('Test checksum changed')
    for dest in ('train', 'val'):
        os.replace(DATA / f'crops_{dest}_new.npz', DATA / f'crops_{dest}.npz')
    make_preview(samples)
    if sha(test_path) != test_before:
        raise RuntimeError('Test checksum changed after replacement')
    result = dict(test_sha256=test_before, pooled_crops=sum(old_counts.values()),
                  new_counts=counts, pooled_people=person_pool, val_people=person_val,
                  new_val_sequences=sorted(NEW_VAL), cells=cells, test_cells=test_cells,
                  sequence_overlap=False, crop_conservation=True)
    (DATA / 'resplit_report.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
