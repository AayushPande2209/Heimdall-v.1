# Heimdall field rig

Run `scripts/install_rig.zsh heimdall` from the repository. The installer copies the recorder package to `~/rig` on the Pi, preserves existing detector files, installs the narrow poweroff sudo rule, and enables the boot service. It backs up existing system files before editing.

For a hardware-free local smoke test:

```sh
heimdall-recorder --fake --frames 8 --session-dir sessions/demo
```

On the Pi:

- `sudo systemctl status heimdall-rig.service` checks status.
- `sudo systemctl stop heimdall-rig.service` stops and flushes the current recording.
- `sudo systemctl start heimdall-rig.service` starts it.
- `sudo systemctl disable --now heimdall-rig.service` turns off boot recording for bench work.
- `sudo systemctl enable --now heimdall-rig.service` restores boot recording.
- Edit `~/rig.conf` to set auto recording, detection, hold duration, pins, free-space threshold, or session directory. Restart the service after editing.
- `journalctl -u heimdall-rig.service -f` and `~/rig.log` show events.

Recordings are `~/rec/session_NNNN.raw` (120×160 uint16 frames), `.txt` (one elapsed-time stamp per frame), `.meta.json`, and `.markers.txt`. Detector logs are in `~/det/output/session_NNNN/`. The boot counter is `~/rig_boot_count`; wall time in metadata is informative because the Pi has no RTC. New sessions do not start below 1 GB free. Recordings are never deleted automatically.

| Component | Pi BCM | Physical pin | Connection |
|---|---:|---:|---|
| Button | 26 | 37 | Normally open to GND pin 39; internal pull-up |
| Status LED | 16 | 36 | Anode from GPIO16; cathode through 330 Ω to GND pin 34 |
| VSYNC (existing) | 22 | 15 | GroupGets breakout VSYNC |
| Lepton EN (existing) | 27 | 13 | Existing connection |

LED: slow 1 Hz blink = boot/wait; solid = recording; fast 5 Hz blink = error; three quick blinks then off = shutdown. A short button press while recording writes a marker and briefly blinks the LED. A 2-second hold requests clean shutdown. The disconnected button is held high by the Pi's internal pull-up.

For logic testing without hardware, send `SIGUSR1` to the service's main PID for a short press. `SIGUSR2` exercises the hold and requests actual poweroff; use only in a controlled test. A manually launched controller with `RIG_TEST_POWEROFF_LOG=/tmp/rig-poweroff-test` exercises that path without shutting down.
