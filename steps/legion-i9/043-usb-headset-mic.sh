# title: USB headsets start with their analog mic
# section: Bluetooth headset (Galaxy Buds3 Pro)
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  same_as "$(F 51-usb-headset-analog-mic.conf)" ~/.config/wireplumber/wireplumber.conf.d/51-usb-headset-analog-mic.conf
}

apply() {
install -Dm644 $R/51-usb-headset-analog-mic.conf ~/.config/wireplumber/wireplumber.conf.d/51-usb-headset-analog-mic.conf
systemctl --user restart pipewire pipewire-pulse wireplumber
}
