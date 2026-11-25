# Architecture decisions

## 2026-11-24 — Apache-2.0 for code

- **Status:** accepted
- **Decision:** Code in this repository is licensed under Apache-2.0.
- **Consequences:** The code has permissive reuse terms and a patent grant. ADIAT
  and other GPL implementation code must not be copied into this repository.

## 2026-11-24 — Hardware and assembly licensing

- **Status:** accepted and applied
- **Decision:** Use CERN-OHL-W-2.0 for editable hardware design files and generated
  meshes, and CC BY 4.0
  for assembly documentation and instructions.
- **Consequences:** The official CERN-OHL-W-2.0 text is committed under
  `hardware/LICENSES/`; each released hardware source carries an SPDX notice.

## 2026-11-24 — Temporary archive retention

- **Status:** accepted
- **Decision:** Keep learning exercises and superseded code in `archive/` until
  benchmark dependencies are confirmed, then tag a recoverable state such as
  `archive-2026` before removing the archive from `main`.
- **Consequences:** The archive remains excluded from packages and tests. A static
  dependency audit found no active import of archived code; the synthetic generator
  is `sim/synthframes.py`, not an archived file.

## 2026-11-24 — Public baseline weights

- **Status:** accepted
- **Decision:** Keep ForestPersonsIR-trained weights excluded. Train a future
  public baseline on Boreas-owned Lepton recordings.
- **Consequences:** Publishing footage or derived weights requires contributor
  consent and a model card documenting data, consent, limits, and intended use.

## 2026-11-24 — Recorder integration strategy

- **Status:** pending source delivery
- **Decision:** Keep the proven Pi Lepton capture implementation and integrate the
  incoming button, LED, marker, session rotation, disk-check, and controller layer
  into it rather than maintaining two recorders.
- **Consequences:** `_incoming_recorder/` is not present yet. Integration and test
  review will begin only after that folder is copied into the repository root.

## Decision template

- **Date and title:**
- **Status:** proposed | accepted | superseded
- **Context:**
- **Decision:**
- **Consequences:**
