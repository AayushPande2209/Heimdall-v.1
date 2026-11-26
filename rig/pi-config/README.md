# Pi boot configuration reference

`config.txt.reference` and `cmdline.txt.reference` are exact copies captured from the validated Pi on 2026-11-25. The installer does not replace either complete file.

Required edits on a fresh Pi:
- In `config.txt`, enable `dtparam=spi=on` and `dtparam=i2c_arm=on` and set `core_freq=500` and `core_freq_min=500` in a `[pi4]` section. The installer backs up the file before adding missing entries.
- In `cmdline.txt`, ensure `spidev.bufsiz=131072` appears once on its single line. The installer backs up the file before adding it.
- Do not add `dtoverlay=gpio-shutdown`; GPIO26 is the rig button and the controller needs its full press duration.

The reference contains machine-specific root PARTUUID and other settings. Do not copy it wholesale to another Pi.
