"""
Run the Heimdall pipeline on a recorded or synthetic sequence and score it.

python demo.py                      # generates synthetic data, runs, scores
python demo.py --input sample.npz   # use a saved sequence
python demo.py --gif out.gif --sheet out.png

Scoring (synthetic ground truth only):
- Frame recall: of the frames where a person is visible, how often did a
    single-frame candidate blob land on them? (stage 1-4 quality)
  - Alert recall: how often a *confirmed alert* was on them (stage 5 quality)
- Time to first alert after the person enters view
- False alerts: confirmed alerts not on any person, split into
    "real non-person object" (deer, rock) and "nothing there" (flicker/clutter)
"""
import argparse
import json
from collections import defaultdict

import cv2
import numpy as np

from hotspot import raw_to_celsius
from pipeline import HeimdallPipeline


def ironbow(temp_c, lo=None, hi=None):
    lo = np.percentile(temp_c, 1) if lo is None else lo
    hi = np.percentile(temp_c, 99.5) if hi is None else hi
    g = np.clip((temp_c - lo) / max(hi - lo, 1e-3) * 255, 0, 255).astype(np.uint8)
    return cv2.applyColorMap(g, cv2.COLORMAP_INFERNO)


def hit(box, x, y, pad=2.0):
    bx, by, bw, bh = box
    return bx - pad <= x <= bx + bw + pad and by - pad <= y <= by + bh + pad


def draw(frame_raw, out, gt, scale=4):
    img = ironbow(raw_to_celsius(frame_raw))
    img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    for g in gt:
        bx, by, bw, bh = [v * scale for v in g["box"]]
        col = (255, 0, 255) if g["kind"] == "person" else (180, 180, 180)
        cv2.rectangle(img, (int(bx), int(by)), (int(bx + bw), int(by + bh)), col, 1)
    for b in out.get("blobs", []):
        x, y, w, h = [v * scale for v in b.bbox]
        cv2.rectangle(img, (int(x), int(y)), (int(x + w), int(y + h)), (0, 220, 255), 1)
    for a in out.get("alerts", []):
        x, y, w, h = [v * scale for v in a["bbox"]]
        cv2.rectangle(img, (int(x) - 2, int(y) - 2), (int(x + w) + 2, int(y + h) + 2), (0, 255, 0), 2)
        cv2.putText(img, f"{a['score']:.2f} {a['bearing_deg']:+.0f}deg", (int(x), max(10, int(y) - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1, cv2.LINE_AA)
    if out.get("skipped"):
        cv2.putText(img, "FFC", (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    return img


def evaluate(frames, ffc, gt_frames, pipe):
    stats = defaultdict(lambda: dict(visible=0, cand=0, alert=0, first_seen=None, first_alert=None,
                                    distance=None, pose=None, occluded=False))
    false_alerts = dict(object=0, nothing=0)
    false_track_ids = dict(object=set(), nothing=set())
    times, outs = [], []
    for t in range(len(frames)):
        out = pipe.process(frames[t], bool(ffc[t]))
        outs.append(out)
        if out["skipped"]:
            continue
        times.append(out["ms"])
        gts = gt_frames[t]
        for g in gts:
            if g["kind"] != "person":
                continue
            bx, by, bw, bh = g["box"]
            # count only if most of the person is inside the frame
            if bx < 0 or by < 0 or bx + bw > 160 or by + bh > 120:
                continue
            s = stats[g["id"]]
            s.update(distance=g["distance_m"], pose=g["pose"], occluded=g["occluded"])
            s["visible"] += 1
            if s["first_seen"] is None:
                s["first_seen"] = t
            if any(hit(g["box"], b.x, b.y) for b in out["blobs"]):
                s["cand"] += 1
            if any(hit(g["box"], a["x"], a["y"]) for a in out["alerts"]):
                s["alert"] += 1
                if s["first_alert"] is None:
                    s["first_alert"] = t
        for a in out["alerts"]:
            if any(g["kind"] == "person" and hit(g["box"], a["x"], a["y"]) for g in gts):
                continue
            key = "object" if any(hit(g["box"], a["x"], a["y"]) for g in gts) else "nothing"
            false_alerts[key] += 1
            false_track_ids[key].add(a["track_id"])
    return stats, false_alerts, false_track_ids, times, outs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help=".npz from synth_frames.py (default: generate)")
    ap.add_argument("--frames", type=int, default=300)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--gif", default="heimdall_demo.gif")
    ap.add_argument("--sheet", default="heimdall_frames.png")
    args = ap.parse_args()

    if args.input:
        d = np.load(args.input)
        frames, ffc, gt = d["frames"], d["ffc"], json.loads(str(d["gt"]))
    else:
        from synth_frames import generate
        frames, ffc, gt = generate(args.frames, args.seed)

    pipe = HeimdallPipeline()
    stats, false_alerts, false_ids, times, outs = evaluate(frames, ffc, gt, pipe)

    fps = 8.7
    print(f"\nFrames: {len(frames)}  (FFC-skipped: {int(ffc.sum())})")
    print(f"Per-frame time: median {np.median(times):.1f} ms, p95 {np.percentile(times, 95):.1f} ms "
        f"(budget at 8.7 Hz: 115 ms)\n")
    print(f"{'person':<26}{'frames':>7}{'cand%':>8}{'alert%':>8}{'1st alert':>11}")
    for pid, s in sorted(stats.items(), key=lambda kv: kv[1]["distance"]):
        label = f"{s['distance']:>4.0f} m {s['pose']}{' (occluded)' if s['occluded'] else ''}"
        delay = "never" if s["first_alert"] is None else f"{(s['first_alert'] - s['first_seen']) / fps:.1f} s"
        print(f"{label:<26}{s['visible']:>7}{100 * s['cand'] / max(1, s['visible']):>7.0f}%"
              f"{100 * s['alert'] / max(1, s['visible']):>7.0f}%{delay:>11}")
    print(f"\nFalse alerts (alert-frames): on a non-person object {false_alerts['object']} "
        f"[{len(false_ids['object'])} tracks], on nothing {false_alerts['nothing']} "
        f"[{len(false_ids['nothing'])} tracks]")
    dur_min = len(frames) / fps / 60
    print(f"False-alert tracks on nothing per minute: {len(false_ids['nothing']) / dur_min:.2f}")

    # visuals
    rendered = [draw(frames[t], outs[t], gt[t]) for t in range(len(frames))]
    picks = np.linspace(20, len(frames) - 1, 6).astype(int)
    rows = [np.hstack([rendered[i] for i in picks[:3]]), np.hstack([rendered[i] for i in picks[3:]])]
    cv2.imwrite(args.sheet, np.vstack(rows))
    try:
        from PIL import Image
        imgs = [Image.fromarray(cv2.cvtColor(cv2.resize(r, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA),
                                            cv2.COLOR_BGR2RGB)).convert("P", palette=Image.ADAPTIVE)
                for r in rendered[::2]]
        imgs[0].save(args.gif, save_all=True, append_images=imgs[1:], duration=int(2000 / fps), loop=0)
        print(f"wrote {args.gif}")
    except ImportError:
        pass
    print(f"wrote {args.sheet}")


if __name__ == "__main__":
    main()