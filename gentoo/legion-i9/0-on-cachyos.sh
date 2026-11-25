#!/bin/bash
# 0-on-cachyos.sh DEST — phase 0 of the Gentoo guide. Run on CachyOS, as yourself (it asks
# for sudo where it needs it). Changes nothing on this laptop: it only reads and copies.
#
# DEST is a folder on an external drive. Into DEST/legion-gentoo/ it writes:
#   notes.env            what the later scripts need: your user, drives, timezone, language
#   fstab.cachyos        CachyOS's /etc/fstab (the NTFS drive and swap lines are reused)
#   sbctl-keys.tar.gz    your Secure Boot keys (private: keep this drive safe)
#   packages-*.txt       what you have installed now, for reference
#   legion-i9/           these scripts and config files, for the live USB
#   home.tar.zst         optional: a backup of your home folder
set -euo pipefail

DEST=${1:-}
[ -n "$DEST" ] && [ -d "$DEST" ] || { echo "Usage: $0 /path/to/external/drive"; exit 1; }
[ "$(id -u)" != 0 ] || { echo "Run this as yourself, not as root."; exit 1; }
OUT="$DEST/legion-gentoo"
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
mkdir -p "$OUT"
say() { printf '\n== %s\n' "$*"; }
warn() { printf '!! %s\n' "$*"; }

say "Your account"
USERNAME=$(id -un); USER_UID=$(id -u); USER_GID=$(id -g)
echo "$USERNAME (uid $USER_UID, gid $USER_GID)"

say "The Linux partition"
ROOT_DEV=$(findmnt -no SOURCE / | sed 's/\[.*//')
ROOT_UUID=$(findmnt -no UUID /)
[ "$(findmnt -no FSTYPE /)" = btrfs ] || { warn "/ isn't Btrfs. This guide assumes CachyOS's Btrfs layout; stop here."; exit 1; }
echo "$ROOT_DEV (Btrfs, UUID $ROOT_UUID)"
SUBVOLS=$(sudo btrfs subvolume list / | awk '{print $NF}')
echo "Subvolumes: $(echo "$SUBVOLS" | tr '\n' ' ')"
echo "$SUBVOLS" | grep -qx '@home' || { warn "No @home subvolume: the guide's 'keep your home folder' step won't apply. Stop and ask."; exit 1; }
if echo "$SUBVOLS" | grep -qx '@gentoo'; then warn "@gentoo already exists (an earlier attempt?). 1-live-usb.sh will refuse until it's removed."; fi
FREE_GB=$(sudo btrfs filesystem usage -b / 2>/dev/null | awk '/Free \(estimated\)/ {printf "%d", $3/1024/1024/1024}')
echo "Free space: ${FREE_GB:-?} GB"
[ "${FREE_GB:-0}" -ge 60 ] || warn "Gentoo needs about 60 GB next to CachyOS until CachyOS is removed. Free some space first."

say "The EFI partition (boot files)"
ESP_MNT=""
for m in /boot /boot/efi /efi; do
  [ "$(findmnt -no FSTYPE "$m" 2>/dev/null)" = vfat ] && { ESP_MNT=$m; break; }
done
[ -n "$ESP_MNT" ] || { warn "Couldn't find the EFI partition at /boot, /boot/efi or /efi."; exit 1; }
ESP_DEV=$(findmnt -no SOURCE "$ESP_MNT"); ESP_UUID=$(findmnt -no UUID "$ESP_MNT")
ESP_FREE_MB=$(df -m --output=avail "$ESP_MNT" | tail -1 | tr -d ' ')
echo "$ESP_DEV mounted at $ESP_MNT, UUID $ESP_UUID, $ESP_FREE_MB MB free"
[ "$ESP_FREE_MB" -ge 300 ] || warn "Gentoo's signed kernel images are about 100 MB each and two are kept. Under 300 MB free: read the guide's note on a small EFI partition before going on."
if sudo test -f "$ESP_MNT/EFI/Microsoft/Boot/bootmgfw.efi"; then
  WINDOWS_ON_ESP=yes; echo "Windows' boot files are on this EFI partition: the new boot menu will list Windows."
else
  WINDOWS_ON_ESP=no; echo "Windows' boot files are on another EFI partition: start Windows from the F12 menu (see the guide)."
fi

say "The NTFS data drive and swap"
NTFS_LINE=$(grep -E '^[^#].*\s/mnt/ntfsdrive\s' /etc/fstab || true)
[ -n "$NTFS_LINE" ] && echo "fstab: $NTFS_LINE" || echo "No /mnt/ntfsdrive line in /etc/fstab (ntfs-autofix may mount it; that's fine)."
grep -qE '^[^#].*\s/swap\s' /etc/fstab && echo "Swap subvolume @swap is in fstab; Gentoo reuses it." || true
cp /etc/fstab "$OUT/fstab.cachyos"

say "Secure Boot keys"
KEYDIR=""
for d in /var/lib/sbctl /usr/share/secureboot; do
  sudo test -f "$d/keys/db/db.key" && { KEYDIR=$d; break; }
done
if [ -n "$KEYDIR" ]; then
  sudo tar -C "$KEYDIR" -czf "$OUT/sbctl-keys.tar.gz" .
  sudo chown "$USER_UID:$USER_GID" "$OUT/sbctl-keys.tar.gz"; chmod 600 "$OUT/sbctl-keys.tar.gz"
  echo "Saved $KEYDIR to sbctl-keys.tar.gz. These are the private keys your firmware trusts: keep this drive safe."
else
  warn "No sbctl keys found. Gentoo will need new keys enrolled (the guide covers it)."
fi
sudo sbctl status 2>/dev/null || true

say "Time zone and language"
TIMEZONE=$(timedatectl show -p Timezone --value 2>/dev/null || echo UTC)
LANG_DEFAULT=$(localectl status 2>/dev/null | sed -n 's/.*LANG=\([^ ]*\).*/\1/p' | head -1)
LANG_DEFAULT=${LANG_DEFAULT:-en_US.UTF-8}
echo "$TIMEZONE, $LANG_DEFAULT"

say "What's installed now (for reference)"
pacman -Qqe > "$OUT/packages-explicit.txt"
pacman -Qqm > "$OUT/packages-aur.txt" || true
systemctl list-unit-files --state=enabled --no-legend > "$OUT/services-enabled.txt" || true
systemctl --user list-unit-files --state=enabled --no-legend > "$OUT/services-user-enabled.txt" || true
echo "$(wc -l < "$OUT/packages-explicit.txt") packages, $(wc -l < "$OUT/packages-aur.txt") from the AUR"

cat > "$OUT/notes.env" <<EOF
# Written by 0-on-cachyos.sh on $(date -I). Read by the later scripts.
USERNAME=$USERNAME
USER_UID=$USER_UID
USER_GID=$USER_GID
ROOT_DEV=$ROOT_DEV
ROOT_UUID=$ROOT_UUID
ESP_DEV=$ESP_DEV
ESP_UUID=$ESP_UUID
ESP_FREE_MB=$ESP_FREE_MB
WINDOWS_ON_ESP=$WINDOWS_ON_ESP
TIMEZONE=$TIMEZONE
LANG_DEFAULT=$LANG_DEFAULT
EOF

say "Copying the Gentoo scripts for the live USB"
rm -rf "$OUT/legion-i9"; cp -r "$HERE" "$OUT/legion-i9"
echo "Copied to $OUT/legion-i9"

say "Home folder backup"
echo "Gentoo keeps using your @home subvolume, so this is only insurance."
read -rp "Make home.tar.zst now (needs space on the drive, takes a while)? [y/N] " a
if [[ $a == [yY] ]]; then
  tar -C "$HOME/.." -cpf - --exclude="$USERNAME/.cache" --exclude="$USERNAME/.local/share/Steam/steamapps" "$USERNAME" \
    | zstd -T0 -3 > "$OUT/home.tar.zst"
  echo "Saved $(du -h "$OUT/home.tar.zst" | cut -f1) (Steam games and caches left out)."
fi

say "Done"
echo "Everything is in $OUT. Next: phase 1 of the guide, from the Gentoo live USB."
