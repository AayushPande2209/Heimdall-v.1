# Hardware

The current prototype uses a FLIR Lepton 3.5, Raspberry Pi Camera Module 3,
and Raspberry Pi 4. Wiring details for VSYNC, Lepton enable, the status LED,
and the recording/shutdown button are recorded in `rig/recorder/README.md`.

## R3 dual-camera shoulder mount

The current printable design is the R3 dual-camera shoulder mount:

- Editable OpenSCAD source: `cad/heimdall_r3_dual.scad`
- Printable meshes: `stl/r3_dual/`
- Design and fit notes: `docs/HEIMDALL_R3_DUAL_CAMERA_NOTES.md`
- Assembly preview: `docs/heimdall_r3_preview.png`

The export set contains the base, camera enclosure and saddle, Raspberry Pi
lid, fan cap, cable covers and clamps, four pitch wedges, and two fit coupons.
All 15 released STL files were checked as single watertight meshes before this
release. This remains a fit prototype: confirm the measurements and physical-fit
checks listed in the design notes before field use.

## Licensing

The CAD source and generated STL files are licensed under
[CERN-OHL-W-2.0](LICENSES/CERN-OHL-W-2.0.txt). Design and assembly documentation
under `hardware/docs/` is licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

The repository does not yet contain a complete BOM. Add it as
`hardware/bom.csv` when the parts list is finalized.
