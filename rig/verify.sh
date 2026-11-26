#!/usr/bin/env bash
# Read-only Pi self-check. Run while controller is READY, not during capture.
set -u
fails=0
pass() { printf 'PASS %-22s %s\n' "$1" "$2"; }
fail() { printf 'FAIL %-22s %s\n' "$1" "$2"; fails=$((fails+1)); }
rig_home=${RIG_HOME:-$HOME}
clock=$(vcgencmd measure_clock core 2>/dev/null | sed -n 's/.*=//p')
if [[ $clock =~ ^[0-9]+$ ]] && (( clock >= 490000000 && clock <= 510000000 )); then pass core_clock "$clock Hz"; else fail core_clock "$clock"; fi
governors=$(cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor 2>/dev/null | sort -u | tr '\n' ' ')
[[ $governors == 'performance ' ]] && pass governor "$governors" || fail governor "$governors"
[[ -c /dev/spidev0.0 ]] && pass spidev /dev/spidev0.0 || fail spidev absent
bufsiz=$(cat /sys/module/spidev/parameters/bufsiz 2>/dev/null || echo missing)
[[ $bufsiz == 131072 ]] && pass spi_bufsiz "$bufsiz" || fail spi_bufsiz "$bufsiz"
cci=$(/usr/bin/python3 - "$rig_home" <<'PY' 2>&1
import sys
sys.path.insert(0, sys.argv[1])
from lepton_gpio import read_words
status=read_words(0x0002)[0]
print(f'0x{status:04x}')
sys.exit(0 if not (status & 0xff01) else 1)
PY
)
[[ $? == 0 ]] && pass lepton_cci "$cci" || fail lepton_cci "$cci"
edges=$(gpiomon -c gpiochip0 -e rising -n 2 --idle-timeout 3s 22 2>&1)
edge_count=$(printf '%s\n' "$edges" | grep -c 'rising' || true)
(( edge_count >= 2 )) && pass vsync_edges "$edge_count rising edges" || fail vsync_edges "$edges"
camera=$(rpicam-hello --list-cameras 2>&1)
grep -q 'imx708_wide' <<<"$camera" && pass camera imx708_wide || fail camera 'not detected'
expected=f0a0cfd913530cd78ce6f83251ee81bef091c0d7e2268bf20feed61bf5c103cd
actual=$(sha256sum "$rig_home/det/heimdall_cnn_full.onnx" 2>/dev/null | cut -d' ' -f1)
[[ $actual == "$expected" ]] && pass model_hash "$actual" || fail model_hash "$actual"
for unit in heimdall-cpu-performance.service heimdall-rig.service; do
  active=$(systemctl is-active "$unit" 2>/dev/null)
  enabled=$(systemctl is-enabled "$unit" 2>/dev/null)
  [[ $active == active && $enabled == enabled ]] && pass "service:$unit" 'active enabled' || fail "service:$unit" "$active $enabled"
done
free=$(df -B1 --output=avail "$rig_home/rec" 2>/dev/null | tail -1 | tr -d ' ')
[[ $free =~ ^[0-9]+$ ]] && (( free >= 1000000000 )) && pass disk_free "$free bytes" || fail disk_free "$free"
throttle=$(vcgencmd get_throttled 2>/dev/null)
[[ $throttle == 'throttled=0x0' ]] && pass throttled "$throttle" || fail throttled "$throttle"
printf 'RESULT %s failures=%d\n' "$([[ $fails == 0 ]] && echo PASS || echo FAIL)" "$fails"
(( fails == 0 ))
