# title: Firmware updates still work with Secure Boot
# section: 15. Secure Boot (do this last)
# when: pacman -Q sbctl && pacman -Q fwupd
# check-as: root
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  [ -e /usr/lib/fwupd/efi/fwupdx64.efi.signed ] || { echo "fwupd's boot helper isn't signed, so firmware updates fail with Secure Boot on"; return 1; }
  grep -q '^DisableShimForSecureBoot=true' /etc/fwupd/fwupd.conf || { echo "fwupd still looks for a shim this laptop doesn't use"; return 1; }
}

apply() {
sudo sbctl sign -s -o /usr/lib/fwupd/efi/fwupdx64.efi.signed /usr/lib/fwupd/efi/fwupdx64.efi
sudo grep -q '^DisableShimForSecureBoot=true' /etc/fwupd/fwupd.conf || { grep -q '^\[uefi_capsule\]' /etc/fwupd/fwupd.conf && sed -i '/^\[uefi_capsule\]/a DisableShimForSecureBoot=true' /etc/fwupd/fwupd.conf || printf '\n[uefi_capsule]\nDisableShimForSecureBoot=true\n' >> /etc/fwupd/fwupd.conf; }
}
