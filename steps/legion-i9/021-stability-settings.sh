# title: Drive health warnings, monthly scrub, and trim done once
# section: Kernel and stability settings
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs plasma-disks smartmontools || return 1
  need_on btrfs-scrub@-.timer || return 1
  if findmnt -no OPTIONS / | grep -q discard=async; then need_off fstrim.timer || return 1; fi
  for t in cachyos-emerald-kde-theme-git cachyos-nord-kde-theme-git; do
    pacman -Q $t >/dev/null 2>&1 && { echo "unused theme still installed: $t"; return 1; }
  done; return 0
}

apply() {
sudo pacman -S --needed plasma-disks smartmontools
sudo systemctl enable --now btrfs-scrub@-.timer
sudo findmnt -no OPTIONS / | grep -q discard=async && { systemctl disable --now fstrim.timer; systemctl reset-failed fstrim.service; }; true
sudo sh -c 'for t in cachyos-emerald-kde-theme-git cachyos-nord-kde-theme-git; do pacman -Q $t >/dev/null 2>&1 && pacman -Rns --noconfirm $t; done; true'
}
