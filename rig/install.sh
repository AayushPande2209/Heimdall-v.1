#!/usr/bin/env bash
# Idempotent Pi-side installer. Run from a staged copy of rig/ as the rig user.
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
rig_home=${RIG_HOME:-$HOME}
stamp=$(date +%Y%m%d-%H%M%S)
dry=0
if [[ ${1:-} == --dry-run ]]; then dry=1; fi
say() { printf '%s\n' "$*"; }
run() { if (( dry )); then printf 'WOULD RUN:'; printf ' %q' "$@"; echo; else "$@"; fi; }
backup() { local file=$1; if [[ -e $file ]]; then run sudo cp -a "$file" "$file.bak-$stamp"; fi; }
protected_copy() {
  local source=$1 target=$2
  if [[ -e $target ]]; then
    if cmp -s "$source" "$target"; then say "MATCH $target"; return; fi
    say "CONFLICT $target differs from packaged validated source; preserving it" >&2
    return 1
  fi
  say "INSTALL $target"
  run cp "$source" "$target"
}
unit_copy() {
  local source=$1 target=$2
  if [[ -e $target ]] && cmp -s "$source" "$target"; then say "MATCH $target"; return; fi
  backup "$target"
  say "INSTALL $target"
  run sudo cp "$source" "$target"
}

[[ $(id -u) -ne 0 ]] || { say 'Run as the normal Pi user, not root.' >&2; exit 1; }
[[ -f $root/model/heimdall_cnn_full.onnx ]] || { say 'Missing final model in package.' >&2; exit 1; }
expected=f0a0cfd913530cd78ce6f83251ee81bef091c0d7e2268bf20feed61bf5c103cd
actual=$(sha256sum "$root/model/heimdall_cnn_full.onnx" | cut -d' ' -f1)
[[ $actual == "$expected" ]] || { say "Model checksum mismatch: $actual" >&2; exit 1; }
run mkdir -p "$rig_home/rig" "$rig_home/det" "$rig_home/rec"
if (( dry )); then
  rsync -anv --exclude '*.bak-*' --exclude '._*' --exclude '.DS_Store' "$root/" "$rig_home/rig/" | sed -n '1,100p'
else
  rsync -a --backup --suffix=".bak-$stamp" --exclude '*.bak-*' --exclude '._*' --exclude '.DS_Store' "$root/" "$rig_home/rig/"
fi
for name in lep_vsync.py lepton_gpio.py record.py lep.py gaps.py; do
  protected_copy "$root/capture/$name" "$rig_home/$name"
done
for name in __init__.py hotspot.py tracker.py pipeline.py crop_classifier.py; do
  protected_copy "$root/detector/algorithms/$name" "$rig_home/det/$name"
done
for name in run_live.py run_offline.py review_recording.py; do
  protected_copy "$root/detector/$name" "$rig_home/det/$name"
done
protected_copy "$root/model/heimdall_cnn_full.onnx" "$rig_home/det/heimdall_cnn_full.onnx"
if [[ ! -e $rig_home/rig.conf ]]; then run cp "$root/recorder/rig.conf.example" "$rig_home/rig.conf"; fi

apt=(python3-venv python3-numpy python3-spidev python3-libgpiod i2c-tools gpiod rpicam-apps ffmpeg rsync)
missing=()
for package in "${apt[@]}"; do dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q 'install ok installed' || missing+=("$package"); done
if ((${#missing[@]})); then
  say "APT missing: ${missing[*]}"
  run sudo apt-get update
  run sudo apt-get install -y "${missing[@]}"
else say 'APT packages present'; fi
if [[ ! -x $rig_home/det/.venv/bin/python ]]; then
  run python3 -m venv --system-site-packages "$rig_home/det/.venv"
fi
if [[ -x $rig_home/det/.venv/bin/pip ]]; then
  if ! diff -q <("$rig_home/det/.venv/bin/pip" freeze --local | sort) <(sort "$root/dependencies/venv-pip-freeze.txt") >/dev/null; then
    run "$rig_home/det/.venv/bin/pip" install -r "$root/dependencies/venv-pip-freeze.txt"
  else say 'Venv pins match'; fi
else say 'Venv will be installed'; fi

config=/boot/firmware/config.txt
if [[ -e $config ]]; then
  missing_config=()
  for entry in 'dtparam=spi=on' 'dtparam=i2c_arm=on' 'core_freq=500' 'core_freq_min=500'; do
    grep -Fqx "$entry" "$config" || missing_config+=("$entry")
  done
  if ((${#missing_config[@]})); then
    backup "$config"
    say "CONFIG add: ${missing_config[*]}"
    if (( ! dry )); then
      { echo; echo '[all]'; for entry in "${missing_config[@]}"; do
          if [[ $entry == core_freq* ]]; then continue; fi
          echo "$entry"
        done
        echo '[pi4]'; for entry in "${missing_config[@]}"; do
          if [[ $entry == core_freq* ]]; then echo "$entry"; fi
        done
        echo '[all]'; } | sudo tee -a "$config" >/dev/null
    fi
  else say 'CONFIG required entries present'; fi
fi
cmdline=/boot/firmware/cmdline.txt
if [[ -e $cmdline ]] && ! grep -Eq '(^|[[:space:]])spidev\.bufsiz=131072([[:space:]]|$)' "$cmdline"; then
  backup "$cmdline"
  say 'CMDLINE append spidev.bufsiz=131072'
  if (( ! dry )); then sudo sed -i '1s/$/ spidev.bufsiz=131072/' "$cmdline"; fi
fi
if [[ -e $config ]] && grep -Eq '^dtoverlay=gpio-shutdown(,|$)' "$config"; then
  backup "$config"
  say 'CONFIG remove gpio-shutdown overlay (GPIO26 button)'
  if (( ! dry )); then sudo sed -i '/^dtoverlay=gpio-shutdown\(,.*\)\?$/d' "$config"; fi
fi
sudoers=/etc/sudoers.d/heimdall-rig-poweroff
rule='aayushpande2009 ALL=(root) NOPASSWD: /usr/bin/systemctl poweroff'
if [[ ! -e $sudoers ]] || [[ $(sudo cat "$sudoers") != "$rule" ]]; then
  backup "$sudoers"
  say "SUDOERS install narrow poweroff rule"
  if (( ! dry )); then printf '%s\n' "$rule" | sudo tee "$sudoers" >/dev/null; sudo chmod 440 "$sudoers"; fi
fi
unit_copy "$root/recorder/heimdall-cpu-performance.service" /etc/systemd/system/heimdall-cpu-performance.service
unit_copy "$root/recorder/heimdall-rig.service" /etc/systemd/system/heimdall-rig.service
if (( dry )); then say 'WOULD RUN sudo visudo -c; systemctl daemon-reload; enable --now both units'; else
  sudo visudo -c
  sudo systemctl daemon-reload
  sudo systemctl enable --now heimdall-cpu-performance.service
  sudo systemctl enable --now heimdall-rig.service
fi
say "INSTALL COMPLETE dry_run=$dry"
