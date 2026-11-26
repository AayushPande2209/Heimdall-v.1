"""ONNX crop classification for radiometric thermal frames."""
import cv2
import numpy as np
import onnxruntime as ort


def normalize(crops):
    med = np.median(crops, axis=(1, 2), keepdims=True)
    std = crops.std(axis=(1, 2), keepdims=True)
    return (crops - med) / (std + 1e-6)


class CropClassifier:
    def __init__(self, onnx_path, cutoff, min_px=8):
        self.session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        self.cutoff = float(cutoff)
        self.min_px = float(min_px)

    def cut(self, temp_c, bbox):
        x, y, w, h = map(float, bbox)
        if max(w, h) < self.min_px:
            return None
        side = max(h, 2 * w) * 1.35
        center = (x + w / 2, y + h / 2)
        image = np.asarray(temp_c, dtype=np.float32)
        patch = cv2.getRectSubPix(image, (max(2, round(side / 2)), max(2, round(side))), center)
        return cv2.resize(patch, (32, 64), interpolation=cv2.INTER_LINEAR).astype(np.float32)

    def score(self, temp_c, bboxes):
        result = [None] * len(bboxes)
        indices, crops = [], []
        for index, bbox in enumerate(bboxes):
            crop = self.cut(temp_c, bbox)
            if crop is not None:
                indices.append(index)
                crops.append(crop)
        if crops:
            x = normalize(np.stack(crops)).astype(np.float32)[:, None]
            logits = self.session.run(["logit"], {"crop": x})[0].reshape(-1)
            probs = 1 / (1 + np.exp(-np.clip(logits, -80, 80)))
            for index, probability in zip(indices, probs):
                result[index] = float(probability)
        return result
