#!/bin/bash
# 1-live-usb.sh FOLDER — phase 1 of the Gentoo guide. Run as root from the Gentoo live USB.
# FOLDER is the legion-gentoo folder 0-on-cachyos.sh wrote on your external drive.
#
# Formats nothing. On the existing Btrfs partition it adds two subvolumes, @gentoo and
# @gentoo-snapshots, next to CachyOS's, which stay untouched. Then it downloads and checks
# the stage file, unpacks it into @gentoo, copies in the config, and prepares the chroot.
set -euo pipefail

SRC=${1:-}
[ -n "$SRC" ] && [ -f "$SRC/notes.env" ] || { echo "Usage: $0 /path/to/legion-gentoo (the folder with notes.env)"; exit 1; }
[ "$(id -u)" = 0 ] || { echo "Run as root (the live USB's root shell)."; exit 1; }
SRC=$(cd "$SRC" && pwd)
# shellcheck source=/dev/null
. "$SRC/notes.env"
HERE="$SRC/legion-i9"
say() { printf '\n== %s\n' "$*"; }
die() { printf '!! %s\n' "$*"; exit 1; }

say "Checking the drives from notes.env"
ROOT=$(blkid -U "$ROOT_UUID") || die "No partition with UUID $ROOT_UUID. Is this the Legion's drive?"
ESP=$(blkid -U "$ESP_UUID") || die "No EFI partition with UUID $ESP_UUID."
[ "$(blkid -o value -s TYPE "$ROOT")" = btrfs ] || die "$ROOT isn't Btrfs."
[ "$(blkid -o value -s TYPE "$ESP")" = vfat ] || die "$ESP isn't an EFI (vfat) partition."
echo "Linux partition: $ROOT    EFI partition: $ESP"
lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINTS

say "The clock"
date
read -rp "Is that roughly the right date and time (UTC is fine)? [Y/n] " a
[[ $a == [nN] ]] && die "Set it first, e.g.: chronyd -q   (or: date MMDDhhmmYYYY)"

say "New subvolumes next to CachyOS's"
TOP=/mnt/btrfs-top
mkdir -p "$TOP"
mountpoint -q "$TOP" || mount -o subvolid=5 "$ROOT" "$TOP"
ls "$TOP"
[ -d "$TOP/@home" ] || die "No @home subvolume on $ROOT."
if [ -e "$TOP/@gentoo" ]; then
  die "@gentoo already exists. To start over: btrfs subvolume delete $TOP/@gentoo $TOP/@gentoo-snapshots"
fi
btrfs subvolume create "$TOP/@gentoo"
btrfs subvolume create "$TOP/@gentoo-snapshots"

say "Mounting the new system at /mnt/gentoo"
OPTS=noatime,compress=zstd:1
mkdir -p /mnt/gentoo
mount -o "subvol=@gentoo,$OPTS" "$ROOT" /mnt/gentoo
mkdir -p /mnt/gentoo/{home,efi,.snapshots}
mount -o "subvol=@home,$OPTS" "$ROOT" /mnt/gentoo/home
mount -o "subvol=@gentoo-snapshots,$OPTS" "$ROOT" /mnt/gentoo/.snapshots
mount "$ESP" /mnt/gentoo/efi
findmnt -R /mnt/gentoo

say "Downloading the stage file (desktop, systemd)"
cd /mnt/gentoo
BASE=https://distfiles.gentoo.org/releases/amd64/autobuilds
wget -q "$BASE/latest-stage3-amd64-desktop-systemd.txt" -O latest.txt
REL=$(grep -oE '[0-9]{8}T[0-9]{6}Z/stage3-amd64-desktop-systemd-[0-9]{8}T[0-9]{6}Z\.tar\.xz' latest.txt | head -1)
[ -n "$REL" ] || die "Couldn't read latest.txt. Download the stage file by hand (see the guide)."
FILE=$(basename "$REL")
echo "Stage file: $FILE"
wget -c "$BASE/$REL" "$BASE/$REL.asc"

say "Checking its signature"
if [ -r /usr/share/openpgp-keys/gentoo-release.asc ]; then
  gpg --import /usr/share/openpgp-keys/gentoo-release.asc
else
  gpg --auto-key-locate=clear,nodefault,wkd --locate-key releng@gentoo.org
fi
gpg --verify "$FILE.asc" "$FILE" || die "The signature doesn't match. Delete $FILE and run this again."

say "Unpacking"
tar xpf "$FILE" --xattrs-include='*.*' --numeric-owner -C /mnt/gentoo
rm -f "$FILE" "$FILE.asc" latest.txt

say "Copying the Legion's Portage and system config"
cp "$HERE/portage/make.conf" /mnt/gentoo/etc/portage/make.conf
for d in package.use package.accept_keywords package.mask binrepos.conf; do
  mkdir -p "/mnt/gentoo/etc/portage/$d"
  cp "$HERE/portage/$d/"* "/mnt/gentoo/etc/portage/$d/"
done
install -Dm644 "$HERE/etc/dracut.conf.d/legion.conf" /mnt/gentoo/etc/dracut.conf.d/legion.conf
install -Dm644 "$HERE/etc/modprobe.d/nvidia-legion.conf" /mnt/gentoo/etc/modprobe.d/nvidia-legion.conf
install -Dm440 "$HERE/etc/sudoers.d/wheel" /mnt/gentoo/etc/sudoers.d/wheel
install -Dm755 "$HERE/etc/prime-run" /mnt/gentoo/usr/local/bin/prime-run

say "Copying the scripts, notes and keys into the new system"
mkdir -p /mnt/gentoo/root/legion-gentoo
for f in notes.env fstab.cachyos sbctl-keys.tar.gz; do
  [ -e "$SRC/$f" ] && cp "$SRC/$f" /mnt/gentoo/root/legion-gentoo/
done
cp -r "$HERE" /mnt/gentoo/root/legion-gentoo/legion-i9
chmod 700 /mnt/gentoo/root/legion-gentoo

say "Preparing the chroot"
cp --dereference /etc/resolv.conf /mnt/gentoo/etc/
mount --types proc /proc /mnt/gentoo/proc
mount --rbind /sys /mnt/gentoo/sys
mount --make-rslave /mnt/gentoo/sys
mount --rbind /dev /mnt/gentoo/dev
mount --make-rslave /mnt/gentoo/dev
mount --bind /run /mnt/gentoo/run
mount --make-slave /mnt/gentoo/run

say "Phase 1 done"
cat <<'EOF'
Next, enter the new system and run phase 2:

  chroot /mnt/gentoo /bin/bash
  bash /root/legion-gentoo/legion-i9/2-chroot.sh
EOF
