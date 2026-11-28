#!/bin/bash
# 3-desktop.sh — phase 3 of the Gentoo guide. Run as root on the new Gentoo, after the
# first boot (text login): sudo bash ~/.local/src/stability-tester/alternatives/gentoo-legion-i9/3-desktop.sh
#
# Installs KDE Plasma, the NVIDIA driver, sound and Bluetooth, Japanese typing, fonts,
# the Legion module, Steam and MangoHud, snapshots; turns on the login screen last.
# Every emerge shows its plan and asks first. Safe to run again.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run with sudo."; exit 1; }
say() { printf '\n== %s\n' "$*"; }

# emerge with a fallback: if Portage needs USE or keyword changes (Steam's 32-bit
# libraries, usually), let it write them, review them with dispatch-conf, try again.
em() {
  emerge --ask --verbose --noreplace "$@" && return 0
  echo
  echo "That didn't go through. If Portage listed USE or keyword changes it needs, it can write them for you."
  read -rp "Let Portage write them, then review them with dispatch-conf? [Y/n] " a
  [[ $a == [nN] ]] && return 1
  emerge --ask --verbose --noreplace --autounmask-write=y --autounmask-continue=n "$@" || true
  dispatch-conf
  emerge --ask --verbose --noreplace "$@"
}

say "1/9 Network"
if ! ping -c1 -W3 distfiles.gentoo.org >/dev/null 2>&1; then
  echo "No internet. Wi-Fi: nmcli device wifi connect \"<network name>\" --ask   (then run this again)"
  exit 1
fi

say "2/9 Extra package repositories: GURU (Legion module, MangoHud) and Steam's"
for r in guru steam-overlay; do
  eselect repository list -i | grep -qw "$r" || eselect repository enable "$r"
done
emaint sync -r guru -r steam-overlay

say "3/9 KDE Plasma and everyday apps"
em kde-plasma/plasma-meta kde-apps/dolphin kde-apps/konsole kde-apps/kate kde-apps/ark \
   kde-apps/spectacle kde-apps/okular kde-apps/gwenview kde-apps/kdialog x11-terms/alacritty \
   www-client/vivaldi www-client/firefox-bin

say "4/9 Graphics: NVIDIA (open modules, signed), Intel video, Vulkan"
em x11-drivers/nvidia-drivers media-libs/mesa media-libs/libva-intel-media-driver \
   media-libs/vulkan-loader dev-util/vulkan-tools sys-apps/switcheroo-control
systemctl enable switcheroo-control
systemctl disable nvidia-powerd 2>/dev/null || true   # legion-system starts it on the charger
for u in nvidia-suspend nvidia-hibernate nvidia-resume; do   # RTX memory survives sleep and hibernation
  if systemctl list-unit-files "$u.service" --no-legend | grep -q .; then systemctl enable "$u.service"; fi
done

say "5/9 Sound, Bluetooth, power profiles"
em media-video/pipewire media-video/wireplumber media-libs/noise-suppression-for-voice \
   net-wireless/bluez sys-power/power-profiles-daemon
systemctl enable bluetooth power-profiles-daemon
systemctl --global enable pipewire.socket pipewire-pulse.socket wireplumber.service

say "6/9 Japanese typing and fonts"
em app-i18n/fcitx app-i18n/fcitx-qt app-i18n/fcitx-gtk app-i18n/fcitx-configtool app-i18n/mozc \
   media-fonts/noto media-fonts/noto-cjk media-fonts/noto-emoji media-fonts/corefonts

say "7/9 Tools the Legion scripts use, firmware updates, snapshots"
em sys-apps/lm-sensors sys-fs/ntfs3g app-misc/jq x11-libs/libnotify media-libs/libpulse \
   sys-apps/smartmontools sys-apps/dmidecode sys-apps/pciutils sys-apps/usbutils sys-apps/fwupd \
   app-backup/snapper app-misc/fastfetch app-portage/pfl
em sys-firmware/lenovolegionlinux
if ! snapper list-configs 2>/dev/null | grep -q '^root'; then
  # snapper wants to create /.snapshots itself; give it the @gentoo-snapshots subvolume back after.
  umount /.snapshots && rmdir /.snapshots
  snapper -c root create-config /
  btrfs subvolume delete /.snapshots
  mkdir /.snapshots && mount /.snapshots && chmod 750 /.snapshots
  snapper -c root set-config TIMELINE_CREATE=no NUMBER_LIMIT=10
fi
systemctl enable snapper-cleanup.timer fwupd-refresh.timer 2>/dev/null || true

say "8/9 Gaming: Steam, MangoHud, gamescope, GameMode"
em games-util/steam-launcher games-util/mangohud gui-wm/gamescope games-util/gamemode

say "9/9 Login screen"
systemctl enable sddm
snapper -c root create -d "Gentoo desktop installed" 2>/dev/null || true

say "Phase 3 done"
cat <<'EOF'
Reboot. You'll get the graphical login screen. Log in, open a terminal, then run phase 4
as yourself (not with sudo):

  bash ~/.local/src/stability-tester/alternatives/gentoo-legion-i9/4-legion.sh
EOF
