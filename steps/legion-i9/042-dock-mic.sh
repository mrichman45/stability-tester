# title: Dock mic: keyboard and fan noise removed
# section: Bluetooth headset (Galaxy Buds3 Pro)
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs noise-suppression-for-voice || return 1
  same_as "$(F 98-dock-mic.conf)" ~/.config/pipewire/pipewire.conf.d/98-dock-mic.conf
}

apply() {
sudo pacman -S --needed noise-suppression-for-voice
install -Dm644 $R/98-dock-mic.conf ~/.config/pipewire/pipewire.conf.d/98-dock-mic.conf
systemctl --user restart pipewire pipewire-pulse wireplumber
}
