# title: First-boot checks: multilib, firewall, snapshots, fish
# section: 7. First boot and checks
# check-as: root
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  grep -q '^\[multilib\]' /etc/pacman.conf || { echo "the multilib repository is off (Steam and Wine need it)"; return 1; }
  ufw status 2>/dev/null | grep -q 'Status: active' || { echo "the firewall (ufw) is off"; return 1; }
  [ -e /etc/snapper/configs/root ] || { echo "no snapper config for /"; return 1; }
  systemctl is-enabled -q limine-snapper-sync 2>/dev/null || { echo "snapshots aren't added to the boot menu (limine-snapper-sync)"; return 1; }
  [ "$(readlink -f "$(getent passwd "$USER" | cut -d: -f7)")" = "$(readlink -f /usr/bin/fish)" ] || { echo "your shell isn't fish"; return 1; }
}

apply() {
sudo grep -q '^\[multilib\]' /etc/pacman.conf || { sed -i '/^#\[multilib\]/,/^#Include/ s/^#//' /etc/pacman.conf && pacman -Syu --noconfirm; }
sudo pacman -S --needed ufw limine-snapper-sync
sudo ufw --force enable
sudo [ -e /etc/snapper/configs/root ] || snapper -c root create-config /
sudo systemctl enable --now limine-snapper-sync
sudo chsh -s /usr/bin/fish $USER
}
# after: Log out and back in if your shell was changed.
