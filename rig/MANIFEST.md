# Heimdall package manifest

This manifest covers the production Pi files and the reference/debug inventory captured on 2026-11-25. The project folder is the source of truth for deployed code. The validated capture and detector algorithms are copied byte-for-byte; the installer refuses to overwrite a differing deployed copy. See `pi-config/pi-script-unit-inventory.txt` for every script/unit filename seen on the Pi, including older experiments. All project changes for this package are under `rig/`.

## Production files

| Project source | Purpose | Pi destination |
|---|---|---|
| `capture/lep_vsync.py` | validated VSYNC/SPI thermal frame reader | `~/lep_vsync.py` (reference); `recorder/lepton_grab.py` is its package-relative wrapper |
| `capture/lepton_gpio.py` | validated Lepton CCI/VSYNC setup | `~/lepton_gpio.py` (reference); `recorder/lepton_gpio.py` is package-relative |
| `capture/record.py` | validated older thermal-only batched writer | `~/record.py` (preserved) |
| `capture/lep.py` | legacy capture retained for recovery | `~/lep.py` (preserved) |
| `capture/gaps.py` | raw/timestamp gap checker | `~/gaps.py` |
| `detector/algorithms/{hotspot,tracker,pipeline,crop_classifier,__init__}.py` | unchanged detector and package imports | `~/det/` |
| `detector/{run_live,run_offline,review_recording}.py` | exact Pi detector runners | `~/det/` |
| `detector/gaps.py` | duplicate reference to the gap checker | `~/rig/detector/gaps.py` |
| `model/heimdall_cnn_full.onnx` (local, Git-ignored artifact) | final CNN, SHA-256 `f0a0cfd913530cd78ce6f83251ee81bef091c0d7e2268bf20feed61bf5c103cd` | `~/det/heimdall_cnn_full.onnx` |
| `recorder/{controller,recorder,rgb,sources,run_live,lepton_grab,lepton_gpio,__init__}.py` | field controller, thermal+RGB recording, capture adapter and detector worker | `~/rig/recorder/` |
| `recorder/{lep_vsync,lepton_gpio_original,record,run_live_original}.py` | original Pi source snapshots | `~/rig/recorder/` |
| `recorder/test_recorder.py`, `recorder/README.md` | hardware-free source test and detailed recorder operations | `~/rig/recorder/` |
| `recorder/{heimdall-rig,heimdall-cpu-performance}.service` | boot controller and CPU governor | `/etc/systemd/system/` |
| `recorder/rig.conf.example` | default field settings | `~/rig/recorder/rig.conf.example`; copied to `~/rig.conf` only if absent |
| `pi-config/{config.txt.reference,cmdline.txt.reference,rig.conf.reference,heimdall-rig-poweroff.sudoers.reference,pi-script-unit-inventory.txt,README.md}` | exact config/sudoers/inventory references and edit explanations | `~/rig/pi-config/` (installer edits live config only as needed) |
| `dependencies/{venv-pip-freeze,apt-packages,os-kernel}.txt` | tested dependency and platform versions | `~/rig/dependencies/` |
| `install.sh`, `verify.sh` | Pi install and read-only self-check | `~/heimdall-package/rig/` staging and `~/rig/` |
| `tools/{deploy.sh,fetch_session.sh,review_session.py}` | Mac deployment, transfer, and synced review | Mac `rig/tools/`; also staged on Pi as package reference |
| `archive/pi-debug/*.py` | 16 historical Pi experiments and diagnostics, retained but inactive | `~/rig/archive/pi-debug/` reference only |
| `README.md`, `FIELD_CHECKLIST.md`, `MANIFEST.md` | operation, pre-flight, and audit | Mac `rig/`; also staged on Pi |

The Pi also has a legacy duplicate `~/heimdall/{hotspot,tracker,pipeline,crop_classifier,__init__}.py`; all five hashes match the protected project source, but the field service imports `~/det/`. The installer also creates `~/rec/`, `~/det/.venv/`, and `/etc/sudoers.d/heimdall-rig-poweroff` (only `/usr/bin/systemctl poweroff`). It does not use or remove `/etc/sudoers.d/90-codex`.

## Pi configuration and dependency snapshot

- OS: Debian GNU/Linux 13.7 (trixie), aarch64; kernel `6.18.60+rpt-rpi-v8`.
- Boot config: SPI and I2C enabled; `[pi4] core_freq=500` and `core_freq_min=500`; no `gpio-shutdown` overlay.
- Kernel cmdline: `spidev.bufsiz=131072`.
- GPIO: VSYNC BCM22, EN BCM27, button BCM26 internal pull-up, optional LED BCM16. Arducam `imx708_wide` on CSI.
- Venv pip pins: see `dependencies/venv-pip-freeze.txt`; NumPy, spidev, gpiod, Picamera2 and rpicam tools come from apt/system site packages. Exact apt versions are in `dependencies/apt-packages.txt`.
- Service user: `aayushpande2009`; recordings and `~/rec` remain owned by this user. Boot controller waits for performance governor before capture.

## Runtime outputs

`~/rec/session_NNNN.raw`, `.txt`, `.meta.json`, `.markers.txt`, `.rgb.h264`, `.rgb.pts`, `.rgb.camera.json`, `.rgb.status.json`, `.rgb.log`, and `.detections/detections.jsonl`. `~/rig.log` is rotated at 5 MB with three backups; journald also receives the logs. `~/rig_boot_count` persists boot count. No RTC means wall time at boot is untrusted; shared stream timing uses monotonic values.

## Current parity and measurements

The deployed Pi detector algorithms, model, validated capture files, units, rig controller/recorder/RGB wrapper, and active config match the packaged source by SHA-256 or exact content. The staged package and installed `~/rig/` were reconciled by `deploy.sh`; a second `install.sh` run made no protected-code changes. `verify.sh` passed all 12 checks. The final combined session_0011 had 2,822 complete thermal frames at 8.68 fps, max gap 0.4938 s, zero resyncs/timeouts, and 9,615 decodable H.264 RGB frames matching PTS/metadata counts. The nearest thermal frames to the RGB first and last frames differ by 44.8 ms and 22.3 ms. The hour-sized storage estimate is 3.05 GB per hour including camera metadata and detector logs, based on the 325-second session; 49.26 GB free allows about 16.1 hours before reserve, or about 15.8 hours with 1 GB minimum free retained.

## Gaps and future work

- A blank-Pi installation cannot be tested without reflashing; dry-run and idempotency checks passed on the current Pi and are recorded in `PACKAGE_NOTES.md`.
- The optional status LED is not physically connected, so its light pattern is logic-tested only.
- The user-requested warm-object physical sync marker is still pending; software timeline alignment passed.
- GPIO22 VSYNC self-check requires the line to be free and the Lepton already configured for VSYNC; run `verify.sh` while READY after a capture session.
- Continuous stall recovery would require careful capture regression; the current controller reports stalls and preserves the session rather than automatically rebooting or deleting data.
- Battery monitoring, buzzer, and detection alerts are intentionally out of scope future work.
- Historical Pi debug scripts in `archive/pi-debug/` are retained as reference only; they are not installed or run by the field service.
