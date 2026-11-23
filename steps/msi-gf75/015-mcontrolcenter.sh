# title: Fans, Cooler Boost and battery limit (MControlCenter)
# section: Fans, power modes, battery (MSI Center replacement)
# default: manual
# when: [ -d /sys/devices/platform/msi-ec ]
# manual: Install MControlCenter from the AUR (paru mcontrolcenter) and set the battery limit there.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  pacman -Qq 2>/dev/null | grep -qi mcontrolcenter || { echo "MControlCenter isn't installed"; return 1; }
}
