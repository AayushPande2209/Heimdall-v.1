# Data

No datasets, recordings, frames, or generated crops are distributed in this
repository. Local data belongs under the ignored `data/` directory, and field
recordings belong under the ignored `sessions/` directory.

The crop-training scripts expect derived ForestPersonsIR data under
`data/fpir_full/` or `data/fpir_partial/`. Obtain ForestPersonsIR separately,
observe its CC BY-NC-SA 4.0 non-commercial license, and use the scripts in
`training/data_prep/` to build local crops. Raw source datasets should remain
outside the repository.

Generated demo images and reports belong in `results/`, which is also ignored.
