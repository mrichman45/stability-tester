# title: Computer name "legion"
# section: 2. Kernel, power modes and fans
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  [ "$(cat /etc/hostname 2>/dev/null)" = legion ] || { echo "the computer is called $(cat /etc/hostname 2>/dev/null), not legion"; return 1; }
}

apply() {
sudo hostnamectl set-hostname legion
}
