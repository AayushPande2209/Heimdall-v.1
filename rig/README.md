# Heimdall field package

Heimdall runs on a Raspberry Pi 4 with a FLIR Lepton 3.5 and an Arducam imx708_wide camera. It works without a network or laptop once installed. **Power on; wait for the slow double-blink READY pattern; press the button briefly to start; press briefly again to mark an event; hold for 2 seconds to stop cleanly and power off.** The status LED is optional and may be absent.

## Wiring and status

| Part | BCM GPIO | Pi pin | Connection |
|---|---:|---:|---|
| Momentary switch | 26 | 37 | Switch to GND pin 39; internal pull-up |
| Optional LED | 16 | 36 | Anode to GPIO16, cathode through 220 Ω to GND pin 34 |
| Lepton VSYNC | 22 | 15 | GroupGets breakout pin 9 |
| Lepton EN | 27 | 13 | Existing connection; do not change |

SPI0 and I2C1 (GPIO2/3) are occupied by the Lepton. Never use GPIO3 for a button. Slow double blink means READY; solid means recording; fast 5 Hz means error; three quick blinks then off means shutdown. The controller debounces the button and ignores presses for one second after a start or stop.

## Install and update

A fresh Pi needs a Raspberry Pi OS Debian 13 (trixie) image, this complete `rig/` package, key-based SSH for Mac deployment, an attached Lepton/CSI camera, and network access during initial package installation. The Pi-side one-command install is `bash rig/install.sh` from a copy of this folder. Check proposed changes first with `bash rig/install.sh --dry-run`. On the Mac, run `rig/tools/deploy.sh heimdall` from the repository. This copies the package and runs the installer and verifier. The installer copies validated capture and detector code only when absent or byte-identical; it stops on a mismatch. It backs up changed files with `.bak-TIMESTAMP`, adds only missing SPI/I2C/core-clock/cmdline settings, installs the narrow poweroff sudoers rule, and enables the governor and rig units. It does not remove `/etc/sudoers.d/90-codex`. The boot/button path uses only `/etc/sudoers.d/heimdall-rig-poweroff` for `/usr/bin/systemctl poweroff` and does not depend on the broad rule.

The installer expects the final model at `rig/model/heimdall_cnn_full.onnx`, SHA-256
`f0a0cfd913530cd78ce6f83251ee81bef091c0d7e2268bf20feed61bf5c103cd`.
That local model artifact is intentionally excluded from this public Git repository;
copy the approved model into that path before deploying. The hotspot cutoff 0.55,
CNN cutoff 0.5, and alert rule are unchanged. Dependency and Pi configuration
snapshots are under `rig/dependencies/` and `rig/pi-config/`. A blank-Pi installation
has not been tested; do not replace `config.txt` or `cmdline.txt` wholesale with
reference copies because they contain Pi-specific settings.

## Config and controls

Edit `~/rig.conf` on the Pi, then `sudo systemctl restart heimdall-rig.service`. `auto_record_on_boot=false` is the field default: boot enters READY and waits for a press. Set it to `true` to start automatically after the Lepton and performance governor are ready. `detection`, `record_rgb`, hold seconds, GPIO pins, minimum free GB, RGB width/height/fps/bitrate, and session directory are configurable. RGB defaults to 1536×864, 30 fps, 4 Mbps after passing the combined capture test. Below 1 GB free, no new session starts. Recordings are never deleted automatically.

- `sudo systemctl status heimdall-rig.service` checks the controller.
- `sudo systemctl stop heimdall-rig.service` cleanly stops any active session.
- `sudo systemctl disable --now heimdall-rig.service` disables field operation for bench work.
- `sudo systemctl enable --now heimdall-rig.service` restores field operation.
- `bash ~/rig/verify.sh` runs the read-only self-check while READY.
- `journalctl -u heimdall-rig.service -f` and `~/rig.log` show events.

## Session files and shared clock

Files live in `~/rec/session_NNNN.*` and are owned by the Pi user. `.raw` is a sequence of 120×160 little-endian uint16 Lepton frames (38,400 bytes each, centikelvin); `.txt` has one elapsed-seconds timestamp per frame. `.markers.txt` records wall time and frame index; frame index is the reliable locator because this Pi has no RTC. `.meta.json` records boot count, capture stats, stop reason, and monotonic clock origins. `.detections/detections.jsonl` contains detector alerts. `.rgb.h264` is a raw H.264 bitstream, `.rgb.pts` is `rpicam-vid` timecode v2 in milliseconds relative to the first RGB frame, `.rgb.camera.json` contains per-frame `SensorTimestamp` nanoseconds, `.rgb.status.json` is controller status, and `.rgb.log` is camera diagnostics. Raw H.264 remains decodable without a finalized MP4 container.

Both cameras share the Pi's monotonic clock. For Lepton frame *i*, absolute monotonic seconds = `meta.thermal_timestamp_origin_monotonic_ns / 1e9 + txt[i]`. For RGB frame *j*, absolute monotonic seconds = `rgb.camera[j].SensorTimestamp / 1e9`; equivalently `meta.rgb.first_sensor_monotonic_ns / 1e9 + rgb.pts[j] / 1000`. Match frames by the nearest absolute time. The monotonic origin resets each boot; compare streams only within one session. Wall-clock metadata is informative only after network time sync.

On the Mac, `rig/tools/fetch_session.sh session_0011` or `rig/tools/fetch_session.sh --latest` copies a session to `~/Desktop/heimdall-sessions/` and renders a review MP4. `rig/tools/review_session.py /path/to/session --rgb` renders thermal colormap, markers, detector boxes (green CNN-confirmed, gray hotspot-only), and optional synchronized RGB side by side. `ffprobe -count_frames -show_entries stream=nb_read_frames` checks raw H.264 frame count.

## Troubleshooting

If READY never appears, check `systemctl status heimdall-rig.service` and `~/rig.log`. If a press does not start capture, check `bash ~/rig/verify.sh`, `i2cdetect -y 1`, `vcgencmd measure_clock core`, governor, and `/dev/spidev0.0`. A fast LED blink indicates Lepton, disk, RGB, or stalled-capture error; the log gives the specific reason. Check free space with `df -h ~/rec`. If RGB fails, thermal keeps recording; inspect `session_NNNN.rgb.status.json` and `.rgb.log`. A short press during recording adds a marker and never stops capture. Do not power-cut during a normal stop; hold the button for two seconds to flush both streams first.
