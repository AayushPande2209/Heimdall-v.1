# Heimdall

Heimdall is a shoulder-mounted thermal person-detection prototype for search and rescue. Its Raspberry Pi pipeline runs a hot-spot detector, tracks candidates over time, and optionally scores tracked crops with a compact CNN.

## Layout

- `heimdall/`: Raspberry Pi runtime code
- `sim/`: synthetic thermal footage and demo
- `training/`: laptop-only CNN training, evaluation, cutoff selection, and ONNX export
- `data_prep/`: ForestPersonsIR crop-generation and resplitting scripts
- `models/`: current model plus archived older models
- `data/`: generated full and partial datasets (Git-ignored)
- `results/`: demos, evaluation images, and reports (Git-ignored)
- `learning/`: learning exercises
- `archive/`: superseded files retained for reference

## Main commands

Run commands from the repository root:

```sh
python3 -m sim.demo --seed 1
python3 -m sim.demo --seed 1 --cnn models/heimdall_cnn_full.onnx --cutoff 0.5
python3 -m training.evaluate models/heimdall_cnn_full.pt
python3 -m training.choose_cutoff
python3 -m training.export_onnx
python3 -m training.train_fp
```

The current Raspberry Pi model is `models/heimdall_cnn_full.onnx` with cutoff `0.5`. Raw full-resolution source data remains outside this repository at `~/ForestPersonsIR_full`.

ForestPersonsIR is licensed under CC BY-NC-SA 4.0 (non-commercial). Models trained on it are for research and prototyping only.
