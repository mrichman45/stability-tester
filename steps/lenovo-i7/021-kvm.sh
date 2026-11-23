# title: Virtualization (KVM) is on for WinBoat
# section: Install
# default: manual
# manual: Turn on Intel Virtualization Technology in the BIOS (F2 at power-on).
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  [ -e /dev/kvm ] || { echo "/dev/kvm is missing: virtualization is off in the BIOS"; return 1; }
}
