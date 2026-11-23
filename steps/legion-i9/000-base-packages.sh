# title: Base packages the later sections rely on
# section: Install step 7. First boot and checks
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs base-devel linux-cachyos-lts-headers power-profiles-daemon switcheroo-control snap-pac sof-firmware kdeconnect || return 1
  need_on switcheroo-control || return 1
  systemctl is-enabled -q power-profiles-daemon 2>/dev/null || systemctl is-active -q power-profiles-daemon || { echo "power-profiles-daemon isn't running"; return 1; }
}

apply() {
sudo pacman -S --needed base-devel linux-cachyos-lts-headers power-profiles-daemon switcheroo-control snap-pac sof-firmware kdeconnect
sudo systemctl enable --now power-profiles-daemon switcheroo-control
}
