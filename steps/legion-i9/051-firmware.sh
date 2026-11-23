# title: Firmware updates (fwupd)
# section: Firmware updates
# default: on
# manual: Skip any System Firmware (BIOS) update: this guide is tested on BIOS KWCN54WW.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs fwupd || return 1
  return 0
}

apply() {
sudo pacman -S --needed fwupd
}
