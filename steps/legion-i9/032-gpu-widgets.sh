# title: GPU widgets don't wake the RTX
# section: GPU widgets that don't wake the RTX
# when: [ -e ~/.local/share/nvstats-service/backend/nvstats_gpu.py ] || [ -e ~/.local/share/plasma/plasmoids/org.dfuse.hardwaremonitor/contents/scripts/sensors.py ]
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  for f in ~/.local/share/nvstats-service/backend/nvstats_gpu.py ~/.local/share/plasma/plasmoids/org.dfuse.hardwaremonitor/contents/scripts/sensors.py; do
    [ -e "$f" ] && ! grep -q _nv_asleep "$f" && { echo "$(basename "$f") polls nvidia-smi even while the RTX sleeps (about 18 W)"; return 1; }
  done; return 0
}

apply() {
python3 $R/patch-widgets.py
systemctl --user try-restart nvstats.service; true
}
