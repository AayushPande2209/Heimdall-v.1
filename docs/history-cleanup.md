# History cleanup guidance

Do **not** run the rewrite commands in this document in the working checkout.
History cleanup is a coordinated, destructive maintenance operation. Start from
a fresh mirror clone, keep a backup, review the rewritten repository, and agree
on a migration window with every contributor.

## 1. Scan the full history for secrets

Install and run one or both scanners against all reachable history. Redact
scanner output before sharing it.

```sh
# From a normal local checkout; --all asks git log to include every ref.
gitleaks git --redact --log-opts="--all" .

# TruffleHog clones and scans all refs from the local repository URL.
trufflehog git "file://$(pwd)" --results=verified,unknown --fail
```

These forms follow the current official [Gitleaks git scanner documentation](https://github.com/gitleaks/gitleaks)
and [TruffleHog Git source documentation](https://github.com/trufflesecurity/trufflehog/blob/main/pkg/sources/git/README.md).
If a real credential is found, revoke or rotate it immediately. Removing it from
Git history does not make the credential safe again.

## 2. List the largest blobs across all commits

```sh
git rev-list --objects --all |
  git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' |
  awk '$1 == "blob" {print $3, $2, substr($0, index($0,$4))}' |
  sort -nr |
  head -100
```

This reports blob size in bytes, object ID, and the historical path when Git can
provide one. Confirm candidate paths with `git log --all --name-status -- PATH`.

## 3. Remove unwanted paths with git-filter-repo

Install [`git-filter-repo`](https://github.com/newren/git-filter-repo), then work
in a disposable mirror clone. The example paths below are the exact weight paths
found during the pre-restructure inspection:

```sh
git clone --mirror https://github.com/BoreasLabs/heimdall.git heimdall-clean.git
cd heimdall-clean.git

git filter-repo --invert-paths \
  --path models/heimdall_cnn_full.onnx \
  --path models/heimdall_cnn_full.pt \
  --path models/archive/heimdall_cnn_fp.pt \
  --path models/archive/heimdall_cnn_fp_v2.pt \
  --path models/archive/heimdall_cnn_v2.onnx \
  --path data/ \
  --path results/ \
  --path sessions/
```

Renames are not followed automatically, so add every old historical path shown
by `git log --all --name-status`. Inspect the rewritten mirror before replacing
any remote refs. Rewriting published history changes commit IDs and ultimately
requires a coordinated forced update; do not do that casually or from this
branch.

## 4. Paths found during Phase 0

Weights:

- `models/heimdall_cnn_full.onnx`
- `models/heimdall_cnn_full.pt`
- `models/archive/heimdall_cnn_fp.pt`
- `models/archive/heimdall_cnn_fp_v2.pt`
- `models/archive/heimdall_cnn_v2.onnx`

Dataset directories and exact crop/report paths:

- `data/fpir_full/images_lepton/`
- `data/fpir_full/annotations/`
- `data/fpir_full/backup_v1/crops_test_v1.npz`
- `data/fpir_full/backup_v1/crops_train_v1.npz`
- `data/fpir_full/backup_v1/crops_val_v1.npz`
- `data/fpir_full/crops_test.npz`
- `data/fpir_full/crops_train.npz`
- `data/fpir_full/crops_train_step1.npz`
- `data/fpir_full/crops_val.npz`
- `data/fpir_full/crops_val_step1.npz`
- `data/fpir_full/edge_report.json`
- `data/fpir_full/prep_report.json`
- `data/fpir_full/preview.png`
- `data/fpir_full/resplit_report.json`
- `data/fpir_partial/images_lepton/`
- `data/fpir_partial/annotations/`
- `data/fpir_partial/crops_test.npz`
- `data/fpir_partial/crops_train.npz`
- `data/fpir_partial/crops_train_old.npz`
- `data/fpir_partial/crops_val.npz`
- `data/fpir_partial/crops_val_old.npz`
- `data/fpir_partial/prep_report.json`
- `data/fpir_partial/preview.png`
- `results/` (generated demos, evaluation montages, reports, and diffs)

No secret-like file or credential value was found in Phase 0. Operational files
`rig/recorder/heimdall-rig.service` and `rig/recorder/rig.conf.example` contain a
Pi username and local paths, but no authentication secret.

## 5. Clones, forks, and caches retain old objects

Even after a successful rewrite, forks, developer clones, cached CI repositories,
release archives, and hosting-provider retention may preserve the old objects.
Every collaborator must re-clone or carefully migrate. A leaked credential must
always be revoked; a history rewrite is only cleanup, not revocation.
