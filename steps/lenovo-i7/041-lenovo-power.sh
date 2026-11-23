# title: Low-power settings at every start (lenovo-power)
# section: A few power settings
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  same_as "$(F lenovo-power)" /usr/local/bin/lenovo-power || return
  same_as "$(F lenovo-power.service)" /etc/systemd/system/lenovo-power.service || return
  need_on lenovo-power.service
}

apply() {
sudo install -Dm755 $R/lenovo-power /usr/local/bin/lenovo-power
sudo install -Dm644 $R/lenovo-power.service /etc/systemd/system/lenovo-power.service
sudo systemctl daemon-reload
sudo systemctl enable --now lenovo-power.service
}
