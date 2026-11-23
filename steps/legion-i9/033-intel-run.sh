# title: intel-run (pins an app to the Intel GPU)
# section: intel-run and the Steam menu entry (plumbing for section 3's GPU rules)
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  same_as "$(F intel-run)" ~/.local/bin/intel-run
}

apply() {
install -Dm755 $R/intel-run ~/.local/bin/intel-run
}
