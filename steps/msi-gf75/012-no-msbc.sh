# title: Bluetooth calls without static (mSBC off)
# section: Headsets (Bluetooth earbuds, USB, laptop jacks)
# default: on
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  same_as "$(F 51-no-msbc.conf)" ~/.config/wireplumber/wireplumber.conf.d/51-no-msbc.conf
}

apply() {
install -Dm644 $R/51-no-msbc.conf ~/.config/wireplumber/wireplumber.conf.d/51-no-msbc.conf
systemctl --user restart pipewire pipewire-pulse wireplumber
}
