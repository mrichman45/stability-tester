# title: Built-in mic: fan noise removed
# section: Mic: remove fan noise
# default: on
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs noise-suppression-for-voice || return 1
  same_as "$(F 99-noise-cancel.conf)" ~/.config/pipewire/pipewire.conf.d/99-noise-cancel.conf
}

apply() {
sudo pacman -S --needed noise-suppression-for-voice
install -Dm644 $R/99-noise-cancel.conf ~/.config/pipewire/pipewire.conf.d/99-noise-cancel.conf
systemctl --user restart pipewire pipewire-pulse wireplumber
}
