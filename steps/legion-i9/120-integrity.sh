# title: legion-integrity (is the system intact?)
# section: Integrity check
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  same_as "$(F legion-integrity)" /usr/local/bin/legion-integrity
}

apply() {
sudo install -Dm755 $R/legion-integrity /usr/local/bin/legion-integrity
}
