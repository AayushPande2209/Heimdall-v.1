# Heimdall

Heimdall is an early-stage shoulder-mounted thermal person-detection rig for
search-and-rescue prototyping. A FLIR Lepton 3.5 feeds a Raspberry Pi 4 pipeline
that detects thermal hot spots, tracks them over time, and can classify tracked
crops with a small CNN.

The repository openly develops the baseline pipeline, Raspberry Pi recording
software, synthetic simulator, training/data-preparation code, and available
hardware notes. It does **not** contain production model weights, datasets,
recordings, or a hosted application. No production-readiness or field-performance
claim is made.

## Repository layout

- `src/heimdall/`: installable detector, tracker, pipeline, and classifier
- `rig/recorder/`: Lepton capture, field recorder, controller, and service files
- `training/`: crop-CNN training, evaluation, export, and data preparation
- `sim/`: synthetic thermal frames and pipeline demo
- `hardware/`: R3 shoulder-mount CAD/STLs, fit notes, and future BOM
- `models/`: policy and instructions; local weights live in ignored `_local/`
- `tests/`: hardware-independent pipeline tests
- `docs/`: data policy, decisions, inventory, and maintenance guidance
- `archive/`: retained superseded code and learning experiments

## Quickstart

Python 3.11 or newer is required.

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .

python3 -m unittest discover -s rig/recorder -v
python3 -m pytest -q

# Hardware-free recorder smoke test
heimdall-recorder --fake --frames 8 --session-dir sessions/demo

# Synthetic detector/tracker demo (no model required)
heimdall-demo --seed 1
```

Training tools require `python3 -m pip install -e '.[train]'`. Raspberry Pi
hardware dependencies are grouped under the `rig` extra; on Raspberry Pi OS,
some are normally installed through `apt` rather than PyPI.

Local ForestPersonsIR-trained weights belong under `models/_local/`. For example:

```sh
python3 -m training.evaluate models/_local/heimdall_cnn_full.pt
python3 -m training.choose_cutoff
```

See [the docs](docs/) and the [field-rig notes](rig/recorder/README.md) for more.

## Hardware

Current wiring notes are documented in `rig/recorder/README.md`. The editable R3
dual-camera shoulder-mount design, its printable STL set, and fit notes are under
`hardware/`. CAD and STL files are licensed under CERN-OHL-W-2.0; hardware
documentation is licensed under CC BY 4.0. A complete BOM has not been added yet.

## Data and models

ForestPersonsIR is CC BY-NC-SA 4.0 and non-commercial. It must be obtained by the
user. Derived data, recordings, and trained weights are intentionally excluded
from this public repository; see [docs/data.md](docs/data.md) and
[models/README.md](models/README.md).
