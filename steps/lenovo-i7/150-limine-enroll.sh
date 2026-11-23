# title: Limine re-signs itself after every snapshot (Secure Boot)
# section: 15. Secure Boot (do this last)
# when: pacman -Q sbctl
# check-as: root
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  grep -q '^ENABLE_ENROLL_LIMINE_CONFIG=yes' /etc/default/limine || { echo "snapshots would change limine.conf without re-enrolling it (boot fails with Secure Boot on)"; return 1; }
  if grep -q '^wallpaper: boot():/limine-splash.png' /boot/limine.conf; then
    grep -q '^wallpaper: boot():/limine-splash.png#' /boot/limine.conf || { echo "the boot splash has no checksum (Limine stops with Secure Boot on)"; return 1; }
  fi; return 0
}

apply() {
sudo grep -q '^ENABLE_ENROLL_LIMINE_CONFIG=yes' /etc/default/limine || echo 'ENABLE_ENROLL_LIMINE_CONFIG=yes' >> /etc/default/limine
sudo h=$(b2sum /boot/limine-splash.png 2>/dev/null | cut -d' ' -f1); [ -z "$h" ] || sed -i "s|^wallpaper: boot():/limine-splash.png\$|wallpaper: boot():/limine-splash.png#$h|" /boot/limine.conf
sudo limine-enroll-config
sudo limine-update
sudo sbctl verify
}
