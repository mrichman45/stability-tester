# title: Sound follows the TV when HDMI is plugged in
# section: If sound does not move to the TV
# default: off
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  same_as "$(F hdmi-audio-follow)" ~/.local/bin/hdmi-audio-follow || return
  same_as "$(F hdmi-audio-follow.service)" ~/.config/systemd/user/hdmi-audio-follow.service || return
  need_user_on hdmi-audio-follow.service
}

apply() {
install -Dm755 $R/hdmi-audio-follow ~/.local/bin/hdmi-audio-follow
install -Dm644 $R/hdmi-audio-follow.service ~/.config/systemd/user/hdmi-audio-follow.service
systemctl --user daemon-reload
systemctl --user enable --now hdmi-audio-follow.service
}
