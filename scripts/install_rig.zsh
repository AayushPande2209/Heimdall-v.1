#!/bin/zsh
# Run on the Mac from this rig directory. Requires key-based ssh and passwordless sudo during install.
set -euo pipefail
here=${0:A:h}
project=${here:h}
remote=${1:-heimdall}
stamp=$(date +%Y%m%d-%H%M%S)
ssh "$remote" 'mkdir -p ~/rig ~/det ~/rec'
for file in lep_vsync.py lepton_gpio.py record.py run_live.py rig_record.py rig_controller.py rig.conf.example heimdall-rig.service README.md; do
  scp "$here/$file" "$remote:~/rig/$file"
done
# Preserve validated files on a configured Pi. New installations receive the bundled copies.
ssh "$remote" "for file in lep_vsync.py lepton_gpio.py record.py; do if [ ! -e \"\$HOME/\$file\" ]; then cp \"\$HOME/rig/\$file\" \"\$HOME/\$file\"; fi; done; if [ ! -e \"\$HOME/det/run_live.py\" ]; then cp \"\$HOME/rig/run_live.py\" \"\$HOME/det/run_live.py\"; fi; if [ ! -e \"\$HOME/rig.conf\" ]; then cp \"\$HOME/rig/rig.conf.example\" \"\$HOME/rig.conf\"; fi"
# Install detector source and model only if missing; never alter deployed detector files.
for file in crop_classifier.py pipeline.py hotspot.py tracker.py __init__.py; do
  if ! ssh "$remote" "test -e ~/det/$file"; then
    scp "$project/heimdall/$file" "$remote:~/det/$file"
  fi
done
if ! ssh "$remote" 'test -e ~/det/heimdall_cnn_full.onnx'; then
  scp "$project/models/heimdall_cnn_full.onnx" "$remote:~/det/heimdall_cnn_full.onnx"
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
sudo cp \"\$HOME/rig/heimdall-rig.service\" /etc/systemd/system/heimdall-rig.service
sudo systemctl daemon-reload
sudo systemctl enable --now heimdall-rig.service
"
