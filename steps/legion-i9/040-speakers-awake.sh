# title: Speakers never go to sleep (no silence after Bluetooth)
# section: Speakers: no sound after switching from Bluetooth
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  same_as "$(F 51-no-suspend.conf)" ~/.config/wireplumber/wireplumber.conf.d/51-no-suspend.conf
}

apply() {
install -Dm644 $R/51-no-suspend.conf ~/.config/wireplumber/wireplumber.conf.d/51-no-suspend.conf
systemctl --user restart pipewire pipewire-pulse wireplumber
}
