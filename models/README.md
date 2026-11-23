# Model files

Heimdall's model architecture, training, evaluation, and ONNX export code are
public. Trained weights are not distributed in this repository.

The current classifiers were trained on ForestPersonsIR, which is licensed
CC BY-NC-SA 4.0 for non-commercial use. Download the dataset separately under
its terms and run the training/export workflow locally. Keep resulting `.pt`
and `.onnx` files in `models/_local/`; that directory is intentionally ignored.

Expected crop-classifier preprocessing is per-crop median subtraction followed
by division by the crop standard deviation. Inputs are 32 pixels wide by 64
pixels high.
