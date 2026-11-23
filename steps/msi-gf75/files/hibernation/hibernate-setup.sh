#!/bin/bash
# hibernate-setup.sh — section 14 of the Legion guide in one go. Safe to run again: each part
# checks whether it's already done. Run as root (Checkup does this for you).
#   1. a Btrfs @swap subvolume at /swap with a 16 GiB swapfile, in /etc/fstab
#   2. resume=UUID=… resume_offset=… on the kernel line in /etc/default/limine
#   3. the resume hook, only for an initramfs without the systemd hook
#   4. limine-update, and a 2-hour delay for "sleep, then hibernate"
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run as root."; exit 1; }
SIZE=16g

src=$(findmnt -no SOURCE / | sed 's/\[.*//')
uuid=$(findmnt -no UUID /)
[ "$(findmnt -no FSTYPE /)" = btrfs ] || { echo "/ isn't Btrfs; this guide's hibernation setup doesn't apply."; exit 1; }

# 1. swapfile
if ! swapon --show=NAME --noheadings | grep -qx /swap/swapfile; then
  if ! btrfs subvolume list / | grep -qE ' path @swap$'; then
    top=$(mktemp -d)
    mount -o subvolid=5 "$src" "$top"
    btrfs subvolume create "$top/@swap"
    umount "$top"; rmdir "$top"
    echo "created the @swap subvolume"
  fi
  mkdir -p /swap
  grep -qE '\s/swap\s' /etc/fstab || echo "UUID=$uuid  /swap  btrfs  noatime,subvol=/@swap  0 0" >> /etc/fstab
  grep -qE '^/swap/swapfile\s' /etc/fstab || echo '/swap/swapfile  none  swap  defaults  0 0' >> /etc/fstab
  systemctl daemon-reload
  findmnt -n /swap >/dev/null || mount /swap
  [ -e /swap/swapfile ] || btrfs filesystem mkswapfile --size "$SIZE" --uuid clear /swap/swapfile
  swapon /swap/swapfile
  echo "swapfile on: $(swapon --show=NAME,SIZE --noheadings | grep /swap/swapfile)"
fi

# 2. where to resume from
offset=$(btrfs inspect-internal map-swapfile -r /swap/swapfile)
cp -n /etc/default/limine /etc/default/limine.before-hibernation
if grep -q 'resume_offset=' /etc/default/limine; then
  sed -i -E "s/resume=UUID=[0-9a-fA-F-]+/resume=UUID=$uuid/; s/resume_offset=[0-9]+/resume_offset=$offset/" /etc/default/limine
else
  sed -i -E "/^KERNEL_CMDLINE\[default\]/ s/\"\s*$/ resume=UUID=$uuid resume_offset=$offset\"/" /etc/default/limine
fi
grep -q "resume_offset=$offset" /etc/default/limine || { echo "Couldn't add resume= to KERNEL_CMDLINE[default] in /etc/default/limine; add it by hand: resume=UUID=$uuid resume_offset=$offset"; exit 1; }
echo "resume from UUID=$uuid offset $offset"

# 3. initramfs hook (the systemd hook reads resume= by itself)
hooks=$(grep '^HOOKS' /etc/mkinitcpio.conf || true)
if [[ "$hooks" != *systemd* && "$hooks" != *resume* ]]; then
  cp -n /etc/mkinitcpio.conf /etc/mkinitcpio.conf.before-hibernation
  sed -i -E '/^HOOKS/ s/\bfilesystems\b/filesystems resume/' /etc/mkinitcpio.conf
  echo "added the resume hook"
fi

# 4. rebuild, and sleep-then-hibernate delay
limine-update
mkdir -p /etc/systemd/sleep.conf.d
printf '[Sleep]\nHibernateDelaySec=2h\n' > /etc/systemd/sleep.conf.d/hibernate-delay.conf
command -v sbctl >/dev/null && sbctl verify || true
echo "Done. Restart, then: systemctl hibernate"
