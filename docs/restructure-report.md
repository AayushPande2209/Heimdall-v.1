# Pre-restructure report

Date: 2026-11-23

This report records the repository before restructuring. The checkout began on
`main` at commit `11d87ab` with an untracked `rig/` directory. Its configured
origin is `https://github.com/AayushPande2209/Heimdall-v.1.git`, not the expected
`BoreasLabs/heimdall`; the remote was not changed or contacted.

## Tree and tracked-file inventory

The full tree (excluding `.git`) contained 80,710 entries and occupied about
1.5 GB. Most entries were ignored ForestPersonsIR data: 80,412 PNG files plus
13 NPZ archives. The complete tree was enumerated with:

```sh
find . -path './.git' -prune -o -print | sort
```

Condensed top-level tree:

```text
.
├── .gitignore
├── .vscode/settings.json
├── README.md
├── archive/                 superseded demo and pipeline
├── data/                    ignored full and partial ForestPersonsIR derivatives
├── data_prep/               dataset preparation scripts
├── heimdall/                detector, tracker, classifier and pipeline
├── learning/                learning exercises
├── models/                  tracked and local weights
├── requirements.txt
├── results/                 ignored demos, reports and evaluation images
├── rig/                     untracked field-rig implementation
├── sim/                     synthetic data and demo
└── training/                CNN training and evaluation
```

There were 33 tracked files. No tracked file exceeded 1 MiB. This was checked by
combining `git ls-files -z` with `stat -f '%z'`.

## How code was imported and run

- The README used repository-root module commands such as `python3 -m sim.demo`
  and `python3 -m training.evaluate`.
- `sim.demo` imported `heimdall.hotspot`, `heimdall.pipeline`, and
  `heimdall.crop_classifier` from the repository root.
- `heimdall.pipeline` already used package-relative imports.
- Training and data-preparation scripts derived paths from `__file__` and the
  repository root.
- `rig/rig_controller.py`, `rig/rig_record.py`, and `rig/run_live.py` modified
  `sys.path` to import files deployed directly under a Pi user's home directory.
- There was no `pyproject.toml`, installed-package entry point, or existing test
  package.
- The requested `heimdall_recorder/` directory (`recorder.py`, `sources.py`,
  `lepton_grab.py`, `test_recorder.py`) was not present anywhere under Desktop or
  Documents. The untracked `rig/` directory instead contained the active field
  recorder, GPIO supervisor, capture code, installer, service file, and notes.

## Model weight files

Tracked at inspection time:

- `models/heimdall_cnn_full.onnx`
- `models/archive/heimdall_cnn_fp.pt`
- `models/archive/heimdall_cnn_fp_v2.pt`
- `models/archive/heimdall_cnn_v2.onnx`

Present on disk but already ignored:

- `models/heimdall_cnn_full.pt`

All are ForestPersonsIR-trained crop-classifier artifacts and therefore subject
to the dataset's CC BY-NC-SA 4.0 non-commercial restriction.

## Data and generated result files

- `data/fpir_full/`: full derived dataset, including PNG frames, annotations,
  crop NPZ files, previews, and preparation reports.
- `data/fpir_partial/`: earlier partial derived dataset with the same general
  categories of files.
- `results/`: GIF/PNG demos, evaluation montages, baseline/after text output,
  diffs, and inventory reports.
- No data or result file was tracked at inspection time; both directories were
  ignored.
- No raw dataset outside the repository was opened or changed.

## Secret scan

No `.env`, private-key, credential, secret, or token files were found. A
case-insensitive text scan found no private-key headers, AWS keys, GitHub tokens,
OpenAI-style keys, or values assigned to common API-key, token, password, or
secret names. `rig/rig.conf.example` contains only non-secret sample settings.
The hard-coded Pi username and home paths are operational configuration, not
authentication material.

## `learning/`

- `learning/cnn.py`: a 63-line NumPy single-neuron/logistic-regression exercise.
- `learning/pytorch.py`: empty placeholder.

These are educational experiments rather than package or production code.

## `archive/`

- `archive/demo_old.py`: superseded standalone synthetic demo using flat imports.
- `archive/pipeline_old.py`: superseded pipeline without the current classifier
  integration.
- Ignored bytecode caches are also present.

These files are retained for reference but should remain outside packaging and
test discovery.

## Items requiring care during restructuring

- Preserve the untracked field-rig work and its two timestamped controller backup
  files; do not silently discard them.
- Replace rig `sys.path` manipulation with installed-package imports.
- Move every ForestPersonsIR-derived weight into ignored local model storage.
- The repository currently has no CAD/hardware content and no recorder tests.
- Hardware licensing remains undecided.
