# title: Heroic games follow the Game GPU mode
# section: Pick the GPU per game (Game GPU switcher)
# when: [ -e ~/.config/heroic/config.json ]
# after: Start Heroic again.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  grep -qs 'gpu-run' ~/.config/heroic/config.json || { echo "Heroic games don't start through gpu-run"; return 1; }
}

apply() {
pkill -f -x '.*heroic.*' ; sleep 2; true
bash $R/heroic-gpu-setup.sh
}
