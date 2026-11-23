# title: legiond: fan presets on, its CPU and GPU control off
# section: Enable legiond (automatic fan profiles)
# when: [ -d /usr/share/legion_linux ] || [ -d /etc/legion_linux ]
# capture: /etc/legion_linux/*
# manual: Save a fan preset for each mode in sudo legion_gui (Read from HW, pick the preset name, Save to Preset); Checkup keeps them in the repo after that.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  [ -f /etc/legion_linux/legiond.ini ] || { echo "legiond has no config in /etc/legion_linux"; return 1; }
  grep -qE '^\s*cpu_control\s*=\s*false' /etc/legion_linux/legiond.ini || { echo "legiond's CPU control is on (it would lock the CPU at 2.2 GHz)"; return 1; }
  grep -qE '^\s*gpu_control\s*=\s*false' /etc/legion_linux/legiond.ini || { echo "legiond's GPU control is on (it only works with old drivers)"; return 1; }
}

apply() {
sudo [ -f /etc/legion_linux/legiond.ini ] || cp -rn /usr/share/legion_linux/. /etc/legion_linux/
sudo sed -i -E 's/^(\s*cpu_control\s*=).*/\1 false/; s/^(\s*gpu_control\s*=).*/\1 false/' /etc/legion_linux/legiond.ini
sudo systemctl restart legiond.service
}
