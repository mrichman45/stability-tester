# title: RTX HDMI audio switch (lets the RTX power down)
# section: HDMI audio switch
# default: off
# check-as: root
# after: Add the button: app launcher, search "RTX HDMI Audio", right-click, Add to Panel.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  same_as "$(F 62-rtx-no-hdmi-audio.rules)" /etc/udev/rules.d/62-rtx-no-hdmi-audio.rules || return
  need_files /usr/local/bin/rtx-hdmi-audio /usr/local/bin/rtx-hdmi-audio-button /etc/sudoers.d/rtx-hdmi-audio /usr/local/share/applications/rtx-hdmi-audio.desktop
}

apply() {
sudo install -Dm644 $R/62-rtx-no-hdmi-audio.rules /etc/udev/rules.d/62-rtx-no-hdmi-audio.rules
sudo install -Dm755 $R/rtx-hdmi-audio /usr/local/bin/rtx-hdmi-audio
sudo install -Dm755 $R/rtx-hdmi-audio-button /usr/local/bin/rtx-hdmi-audio-button
sudo visudo -cf $R/sudoers && install -Dm440 $R/sudoers /etc/sudoers.d/rtx-hdmi-audio
sudo install -Dm644 $R/rtx-hdmi-audio.desktop /usr/local/share/applications/rtx-hdmi-audio.desktop
sudo udevadm control --reload
kbuildsycoca6 >/dev/null 2>&1; true
}
