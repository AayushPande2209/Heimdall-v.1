#!/bin/zsh
# Run from the repository. Requires key-based SSH and passwordless sudo during install.
set -euo pipefail
here=${0:A:h}
project=${here:h}
recorder=$project/rig/recorder
remote=${1:-heimdall}
stamp=$(date +%Y%m%d-%H%M%S)
ssh "$remote" 'mkdir -p ~/rig/recorder ~/heimdall ~/det ~/rec'
scp "$project/rig/__init__.py" "$remote:~/rig/__init__.py"
for file in __init__.py lepton_grab.py lepton_gpio.py sources.py run_live.py recorder.py controller.py rig.conf.example heimdall-rig.service README.md; do
  scp "$recorder/$file" "$remote:~/rig/recorder/$file"
done
ssh "$remote" "if [ ! -e \"\$HOME/rig.conf\" ]; then cp \"\$HOME/rig/recorder/rig.conf.example\" \"\$HOME/rig.conf\"; fi"
# Install detector source only if missing; never alter deployed detector files.
for file in crop_classifier.py pipeline.py hotspot.py tracker.py __init__.py; do
  if ! ssh "$remote" "test -e ~/heimdall/$file"; then
    scp "$project/src/heimdall/$file" "$remote:~/heimdall/$file"
  fi
done
if ! ssh "$remote" 'test -e ~/det/heimdall_cnn_full.onnx' && [[ -f "$project/models/_local/heimdall_cnn_full.onnx" ]]; then
  scp "$project/models/_local/heimdall_cnn_full.onnx" "$remote:~/det/heimdall_cnn_full.onnx"
fi
ssh "$remote" "set -eu
sudo apt-get update
sudo apt-get install -y python3-venv python3-numpy python3-spidev python3-libgpiod i2c-tools
if [ ! -x \"\$HOME/det/.venv/bin/python\" ]; then python3 -m venv --system-site-packages \"\$HOME/det/.venv\"; \"\$HOME/det/.venv/bin/pip\" install opencv-python-headless scipy onnxruntime; fi
if [ -f /boot/firmware/config.txt ] && grep -Eq '^dtoverlay=gpio-shutdown(,|$)' /boot/firmware/config.txt; then
  sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.bak-$stamp
  sudo sed -i '/^dtoverlay=gpio-shutdown\(,.*\)\?\$/d' /boot/firmware/config.txt
fi
if [ -e /etc/sudoers.d/heimdall-rig-poweroff ]; then sudo cp /etc/sudoers.d/heimdall-rig-poweroff /etc/sudoers.d/heimdall-rig-poweroff.bak-$stamp; fi
printf '%s\\n' 'aayushpande2009 ALL=(root) NOPASSWD: /usr/bin/systemctl poweroff' | sudo tee /etc/sudoers.d/heimdall-rig-poweroff >/dev/null
sudo chmod 440 /etc/sudoers.d/heimdall-rig-poweroff
sudo visudo -c
if [ -e /etc/systemd/system/heimdall-rig.service ]; then sudo cp /etc/systemd/system/heimdall-rig.service /etc/systemd/system/heimdall-rig.service.bak-$stamp; fi
sudo cp \"\$HOME/rig/recorder/heimdall-rig.service\" /etc/systemd/system/heimdall-rig.service
sudo systemctl daemon-reload
sudo systemctl enable --now heimdall-rig.service
"
