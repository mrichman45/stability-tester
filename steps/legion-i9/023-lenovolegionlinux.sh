# title: LenovoLegionLinux: fans, Fn+Q modes, battery limit
# section: Fans, power modes, battery (Vantage replacement)
# after: Restart so the Legion module loads.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs linux-cachyos-lts-headers base-devel dkms clang llvm lld lm_sensors python-pyqt6 python-yaml python-argcomplete python-darkdetect || return 1
  { pacman -Q lenovolegionlinux-dkms-git || pacman -Q lenovolegionlinux-dkms; } >/dev/null 2>&1 || { echo "the Legion driver (lenovolegionlinux-dkms) isn't installed"; return 1; }
  { pacman -Q lenovolegionlinux-git || pacman -Q lenovolegionlinux; } >/dev/null 2>&1 || { echo "legion_gui and legiond (lenovolegionlinux) aren't installed"; return 1; }
}

apply() {
sudo pacman -S --needed linux-cachyos-lts-headers base-devel dkms clang llvm lld lm_sensors python-pyqt6 python-yaml python-argcomplete python-darkdetect
@aur lenovolegionlinux-dkms-git
@aur lenovolegionlinux-git
}
