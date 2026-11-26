#!/usr/bin/env bash
# Mac: stage the complete rig package, then run the Pi-side installer.
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
target=${1:-heimdall}
ssh_opts=(-o BatchMode=yes -o HostKeyAlias=heimdall.local -i "$HOME/.ssh/id_heimdall")
ssh "${ssh_opts[@]}" "$target" 'mkdir -p ~/heimdall-package; if [ -d ~/heimdall-package/rig ]; then mv ~/heimdall-package/rig ~/heimdall-package/rig.bak-$(date +%Y%m%d-%H%M%S); fi; mkdir -p ~/heimdall-package/rig'
COPYFILE_DISABLE=1 tar --format=ustar -C "$root" --exclude='*.bak-*' --exclude='__pycache__' --exclude='._*' --exclude='.DS_Store' -czf - . | ssh "${ssh_opts[@]}" "$target" 'tar -C ~/heimdall-package/rig -xzf -' 
ssh "${ssh_opts[@]}" "$target" 'bash ~/heimdall-package/rig/install.sh'
ssh "${ssh_opts[@]}" "$target" 'bash ~/heimdall-package/rig/verify.sh'
