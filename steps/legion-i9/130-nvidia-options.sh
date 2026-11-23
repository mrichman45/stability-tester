# title: No outdated NVIDIA options at boot
# section: Leftover NVIDIA options after an update
# when: ls /etc/modprobe.d/*.conf
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  ! grep -qs 'NVreg_UsePageAttributeTable' /etc/modprobe.d/*.conf || { echo "an NVIDIA option the driver no longer knows is set in /etc/modprobe.d"; return 1; }
}

apply() {
sudo sed -i 's/ NVreg_UsePageAttributeTable=[0-9]*//' /etc/modprobe.d/*.conf
sudo limine-mkinitcpio
}
