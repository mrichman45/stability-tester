# title: Bigger audio buffer for every app (no hiccups in games)
# section: Audio buffer for every app (stops hiccups)
# after: Quit Discord from its tray icon and start it again.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  same_as "$(F pipewire-60-min-buffer.conf)" ~/.config/pipewire/pipewire.conf.d/60-min-buffer.conf || return
  same_as "$(F pulse-60-min-buffer.conf)" ~/.config/pipewire/pipewire-pulse.conf.d/60-min-buffer.conf
}

apply() {
install -Dm644 $R/pipewire-60-min-buffer.conf ~/.config/pipewire/pipewire.conf.d/60-min-buffer.conf
install -Dm644 $R/pulse-60-min-buffer.conf ~/.config/pipewire/pipewire-pulse.conf.d/60-min-buffer.conf
rm -f ~/.config/pipewire/pipewire-pulse.conf.d/60-gaming-buffer.conf
systemctl --user restart pipewire pipewire-pulse wireplumber
}
