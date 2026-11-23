# title: Hibernation (32 GiB swapfile, resume from it)
# section: 14. Hibernation
# check-as: root
# after: Restart, then try it: systemctl hibernate (save your work first).
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  swapon --show=NAME --noheadings | grep -qx /swap/swapfile || { echo "there's no swapfile, so the laptop can't hibernate"; return 1; }
  grep -q 'resume_offset=' /etc/default/limine || { echo "the kernel doesn't know where to resume from"; return 1; }
  [ -e /etc/systemd/sleep.conf.d/hibernate-delay.conf ] || { echo "sleep-then-hibernate has no delay set"; return 1; }
}

apply() {
sudo bash $R/hibernate-setup.sh
}
