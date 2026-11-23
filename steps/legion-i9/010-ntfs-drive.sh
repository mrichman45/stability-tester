# title: NTFS data drive mounts at /mnt/ntfsdrive
# section: 1. The NTFS data drive
# when: [ -n "$NTFS_UUID" ]
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  findmnt --fstab -n /mnt/ntfsdrive >/dev/null || { echo "the data drive isn't in /etc/fstab"; return 1; }
  findmnt -n /mnt/ntfsdrive >/dev/null || { echo "the data drive is in fstab but not mounted"; return 1; }
}

apply() {
sudo pacman -S --needed ntfsprogs ntfs-3g smartmontools
sudo mkdir -p /mnt/ntfsdrive
sudo grep -qE '\s/mnt/ntfsdrive\s' /etc/fstab || echo "UUID=$NTFS_UUID  /mnt/ntfsdrive  ntfs3  uid=$UID,gid=$GID,umask=022,exec,windows_names,nofail  0 0" >> /etc/fstab
sudo systemctl daemon-reload
sudo findmnt -n /mnt/ntfsdrive >/dev/null || mount /mnt/ntfsdrive || { ntfsfix -d /dev/disk/by-uuid/$NTFS_UUID && mount /mnt/ntfsdrive; }
}
