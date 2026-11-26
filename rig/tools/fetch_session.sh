#!/usr/bin/env bash
# Mac: fetch a numbered or newest session and render a review video.
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
target=${HEIMDALL_TARGET:-heimdall}
ssh_opts=(-o BatchMode=yes -o HostKeyAlias=heimdall.local -i "$HOME/.ssh/id_heimdall")
if [[ ${1:-} == --latest ]]; then
  name=$(ssh "${ssh_opts[@]}" "$target" 'find ~/rec -maxdepth 1 -name "session_*.meta.json" -printf "%f\n" | sed "s/\.meta\.json$//" | sort -V | tail -1')
else name=${1:-}; fi
[[ $name =~ ^session_[0-9]+$ ]] || { echo 'Use session_NNNN or --latest' >&2; exit 2; }
destination=${2:-$HOME/Desktop/heimdall-sessions/$name}
mkdir -p "$destination"
rsync -av -e "ssh -o BatchMode=yes -o HostKeyAlias=heimdall.local -i $HOME/.ssh/id_heimdall" "$target:~/rec/$name.*" "$destination/"
if ssh "${ssh_opts[@]}" "$target" "test -d ~/det/output/$name"; then
  mkdir -p "$destination/detector"
  rsync -av -e "ssh -o BatchMode=yes -o HostKeyAlias=heimdall.local -i $HOME/.ssh/id_heimdall" "$target:~/det/output/$name/" "$destination/detector/"
fi
python3 "$root/tools/review_session.py" "$destination" --rgb --output "$destination/$name.review.mp4"
echo "$destination"
