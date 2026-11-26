# Heimdall field controller

Install from the Mac repository with `rig/recorder/install.zsh heimdall`. The installer copies this package to `~/rig` on the Pi, preserves the Pi's validated capture and detector code, creates a narrow sudo rule for `systemctl poweroff`, and enables `heimdall-rig.service`. It backs up existing system files before editing. The only boot-config edit it may make is removing an existing `dtoverlay=gpio-shutdown` line after backing up `config.txt`.

## Operation

The default is **press to start**. Boot starts the controller and logs `READY`; it does not touch the Lepton or start capture. One short press starts a new numbered session after checking for at least 1 GB free and checking Lepton CCI. A second short press while recording writes a timestamped frame marker. A short press never stops capture. Hold for 2 seconds while idle or recording to stop and flush any active recording, blink the LED three times, and power off. The first second after a start or stop ignores presses. The switch uses a pull-up and 60 ms debounce. A failed start stays idle with an error indication; press again to retry. The LED is optional.

Set `auto_record_on_boot = true` in `~/rig.conf` to resume automatic boot recording. While waiting for the Lepton or performance governor, automatic mode retries for up to 60 seconds with the waiting pattern; after that it shows an error and retries every 10 seconds. Restart the service after changing the config.

- `sudo systemctl status heimdall-rig.service`: status
- `sudo systemctl stop heimdall-rig.service`: cleanly stop and flush
- `sudo systemctl start heimdall-rig.service`: start controller in READY state
- `sudo systemctl disable --now heimdall-rig.service`: disable boot controller for bench work
- `sudo systemctl enable --now heimdall-rig.service`: restore boot controller
- `journalctl -u heimdall-rig.service -f` and `~/rig.log`: logs

Recordings are in `~/rec/session_NNNN.raw` (120×160 uint16 frames), `.txt` (one elapsed timestamp per frame), `.meta.json` (including frame count, gaps, resyncs, stop reason, and press-to-first-frame latency), and `.markers.txt`. Detector output is in `~/rec/session_NNNN.detections/`. `~/rig_boot_count` counts controller starts. Wall time is recorded but cannot be trusted without a real-time clock or network sync. Recordings are never deleted by the controller.

| Part | BCM | Pi physical pin | Wiring |
|---|---:|---:|---|
| Momentary button | 26 | 37 | Switch to ground pin 39; internal pull-up |
| Optional status LED | 16 | 36 | Anode to GPIO16, cathode through 220 Ω to ground pin 34 |
| VSYNC (existing) | 22 | 15 | GroupGets breakout VSYNC |
| Lepton EN (existing) | 27 | 13 | Existing wire |

LED: slow double blink = READY; solid = recording; fast 5 Hz blink = error (Lepton, disk, or capture); three quick blinks then off = shutdown. The absent LED does not affect operation.

For software button tests, send `SIGUSR1` to the controller PID for a short press, or `SIGUSR2` for a hold. `SIGUSR2` requests real shutdown unless the controller was started manually with `RIG_TEST_POWEROFF_LOG=/tmp/rig-poweroff-test`, which records the shutdown request instead. Both signals use the same press handlers as the button.
