# title: Heroic games pick their GPU when they launch
# section: Heroic: the GPU per game
# when: [ -e ~/.config/heroic/config.json ]
# after: Start Heroic again.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  grep -qs game-gpu ~/.config/heroic/config.json || { echo "Heroic games don't start through game-gpu"; return 1; }
}

apply() {
pkill -f -x '.*heroic.*' ; sleep 2; true
bash $R/heroic-gpu-setup.sh
}
