# Thermal ingest

No standalone thermal recording decoder existed when the repository was
restructured. Raspberry Pi Lepton capture is implemented in `rig/recorder/`.
Place reusable frame-format decoders in this package when they are introduced.
