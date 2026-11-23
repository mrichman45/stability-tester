# title: Secure Boot is on
# section: 9. Secure Boot (do this last)
# default: manual
# check-as: root
# manual: Do this last. Reboot to the BIOS (systemctl reboot --firmware-setup), Security > Reset to Setup Mode, boot back, then: sudo pacman -S sbctl; sudo sbctl create-keys; sudo sbctl enroll-keys --microsoft --firmware-builtin. Run Checkup again (Limine step), then turn Secure Boot on in the BIOS.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  command -v sbctl >/dev/null || { echo "sbctl isn't installed yet"; return 1; }
  sbctl status 2>/dev/null | grep -qiE 'secure boot:.*enabled' || { echo "Secure Boot is off"; return 1; }
}
