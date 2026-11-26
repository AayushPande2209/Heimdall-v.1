# Heimdall pre-flight checklist

1. Charge and connect the rig battery/power supply. Check the button and camera connections visually without changing live wiring.
2. With the Pi in READY, run `bash ~/rig/verify.sh` when a laptop is available; all checks should say PASS. Check `df -h ~/rec` for at least 1 GB free. Recordings are not deleted automatically.
3. Confirm `~/rig.conf` has `auto_record_on_boot=false`, `detection=on`, and the intended `record_rgb` setting. Restart the service after any edit.
4. Power on. Wait for the slow double-blink READY pattern if the optional LED is connected. Press once briefly; wait for solid LED or confirm `START` in `~/rig.log` during bench testing.
5. Make one short test press while recording to write a marker. Confirm a `session_NNNN.markers.txt` file during bench testing.
6. For the field run, press briefly to add markers. At the end, hold the button for 2 seconds; wait for shutdown before removing power.
7. After the run, use `rig/tools/fetch_session.sh --latest` from the Mac and inspect the review MP4 and session metadata.
