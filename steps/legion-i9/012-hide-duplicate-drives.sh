# title: Dolphin doesn't offer the data drive twice or ask to mount Windows
# section: Errors seen and fixes
# when: [ -n "$NTFS_UUID" ]
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  grep -qs "$NTFS_UUID" /etc/udev/rules.d/99-hide-ntfsdrive-dup.rules || { echo "Dolphin shows a second, broken entry for the data drive"; return 1; }
  [ -z "$WINDOWS_UUID" ] || grep -qs "$WINDOWS_UUID" /etc/udev/rules.d/99-hide-windows.rules || { echo "KDE asks for a password to mount the Windows partition at login"; return 1; }
}

apply() {
sudo echo 'ENV{ID_FS_UUID}=="$NTFS_UUID", ENV{UDISKS_IGNORE}="1"' > /etc/udev/rules.d/99-hide-ntfsdrive-dup.rules
sudo [ -z "$WINDOWS_UUID" ] || echo 'ENV{ID_FS_UUID}=="$WINDOWS_UUID", ENV{UDISKS_IGNORE}="1"' > /etc/udev/rules.d/99-hide-windows.rules
sudo udevadm control --reload
sudo udevadm trigger
}
