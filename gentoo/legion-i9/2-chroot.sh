#!/bin/bash
# 2-chroot.sh — phase 2 of the Gentoo guide. Run as root inside the chroot that
# 1-live-usb.sh prepared. Safe to run again after an error: finished steps are skipped
# or simply repeated.
#
# Sets up Portage and the binary packages, the profile, language and time zone, the
# Secure Boot keys, the signed kernel and boot menu, /etc/fstab, networking, and your
# account (same user ID as on CachyOS, so your home folder fits).
set -euo pipefail

D=/root/legion-gentoo
[ -f "$D/notes.env" ] || { echo "Run 1-live-usb.sh first (no $D/notes.env)."; exit 1; }
# shellcheck source=/dev/null
. "$D/notes.env"
# /etc/profile isn't written for "set -u"
set +u; . /etc/profile; set -u
say() { printf '\n== %s\n' "$*"; }
die() { printf '!! %s\n' "$*"; exit 1; }
mountpoint -q /efi || die "/efi isn't mounted. Leave the chroot and run 1-live-usb.sh again."

say "1/12 Getting the package list (the ebuild repository)"
[ -d /var/db/repos/gentoo/profiles ] || emerge-webrsync
emerge --sync --quiet

say "2/12 Profile: desktop, KDE Plasma, systemd"
eselect profile set default/linux/amd64/23.0/desktop/plasma/systemd
eselect profile show

say "3/12 Trust for Gentoo's signed binary packages"
getuto

say "4/12 Your CPU's instruction sets"
emerge --oneshot --noreplace app-portage/cpuid2cpuflags
echo "*/* $(cpuid2cpuflags)" > /etc/portage/package.use/00cpu-flags
cat /etc/portage/package.use/00cpu-flags

say "5/12 Language and time zone ($LANG_DEFAULT, $TIMEZONE)"
for l in "${LANG_DEFAULT%.*}.UTF-8 UTF-8" "en_US.UTF-8 UTF-8" "ja_JP.UTF-8 UTF-8"; do
  grep -qxF "$l" /etc/locale.gen || echo "$l" >> /etc/locale.gen
done
locale-gen
eselect locale set "$(eselect locale list | awk -v w="${LANG_DEFAULT%.*}.utf8" 'tolower($2) == tolower(w) {gsub(/[][]/, "", $1); print $1; exit}')" \
  || eselect locale set C.utf8
ln -sf "/usr/share/zoneinfo/$TIMEZONE" /etc/localtime
env-update; set +u; . /etc/profile; set -u

say "6/12 Secure Boot keys (before anything signed is built)"
if [ -f "$D/sbctl-keys.tar.gz" ]; then
  mkdir -p /var/lib/sbctl && chmod 700 /var/lib/sbctl
  [ -f /var/lib/sbctl/keys/db/db.key ] || tar -xzf "$D/sbctl-keys.tar.gz" -C /var/lib/sbctl
  echo "Your existing keys are in /var/lib/sbctl: nothing needs enrolling again."
else
  echo "No Secure Boot keys came from CachyOS, and the kernel can't be signed without them."
  echo "Stop here and ask: new keys have to be made (sbctl create-keys) and enrolled first."
  exit 1
fi
if [ ! -f /etc/portage/keys/modules.pem ]; then
  mkdir -p /etc/portage/keys && chmod 700 /etc/portage/keys
  openssl req -new -nodes -utf8 -sha512 -x509 -days 36500 -subj "/CN=Legion kernel module signing/" \
    -keyout /etc/portage/keys/modules.pem -out /etc/portage/keys/modules.pem
  chmod 600 /etc/portage/keys/modules.pem
  echo "Made the key that signs kernel modules (NVIDIA, Legion): /etc/portage/keys/modules.pem"
fi

say "7/12 Updating everything to the new profile (mostly binary packages)"
emerge --verbose --update --deep --newuse @world
emerge --noreplace app-crypt/sbctl app-crypt/sbsigntools

say "8/12 Firmware and microcode"
emerge --noreplace sys-kernel/linux-firmware sys-firmware/intel-microcode sys-firmware/sof-firmware

say "9/12 Boot menu (systemd-boot, signed)"
systemd-machine-id-setup        # kernel-install names the boot entry after it
emerge --noreplace sys-kernel/installkernel
bootctl install --esp-path=/efi
CMDLINE="root=UUID=$ROOT_UUID rootflags=subvol=@gentoo rw quiet"
# Hibernation: reuse CachyOS's swapfile in the @swap subvolume, and tell the kernel
# where it starts on the disk.
mkdir -p /swap
if ! mountpoint -q /swap; then mount -o subvol=@swap "UUID=$ROOT_UUID" /swap 2>/dev/null || true; fi
if [ -f /swap/swapfile ]; then
  OFFSET=$(btrfs inspect-internal map-swapfile -r /swap/swapfile)
  CMDLINE="$CMDLINE resume=UUID=$ROOT_UUID resume_offset=$OFFSET"
  mkdir -p /etc/systemd/sleep.conf.d
  printf '[Sleep]\nHibernateDelaySec=2h\n' > /etc/systemd/sleep.conf.d/hibernate-delay.conf
  echo "Hibernation: resumes from /swap/swapfile (offset $OFFSET); sleep becomes hibernation after 2 hours."
else
  echo "No /swap/swapfile in @swap: hibernation is skipped for now (ask me to set it up)."
fi
if mountpoint -q /swap; then umount /swap; fi
echo "$CMDLINE" > /etc/kernel/cmdline
echo "Kernel command line: $(cat /etc/kernel/cmdline)"

say "10/12 The kernel (6.18 LTS, built here; dracut signs its image; takes a while)"
emerge --verbose --noreplace sys-kernel/gentoo-kernel
ls -l /efi/EFI/Linux/ 2>/dev/null || true
bootctl list --no-pager || true

say "11/12 /etc/fstab"
if ! grep -q 'subvol=@gentoo,' /etc/fstab 2>/dev/null; then
  OPTS=noatime,compress=zstd:1
  {
    echo "# Written by 2-chroot.sh"
    echo "UUID=$ROOT_UUID  /            btrfs  subvol=@gentoo,$OPTS            0 0"
    echo "UUID=$ROOT_UUID  /home        btrfs  subvol=@home,$OPTS              0 0"
    echo "UUID=$ROOT_UUID  /.snapshots  btrfs  subvol=@gentoo-snapshots,$OPTS  0 0"
    echo "UUID=$ESP_UUID   /efi         vfat   umask=0077                      0 2"
    # Reused from CachyOS: the swap subvolume and swapfile, and the NTFS data drive.
    grep -E '^[^#].*\s/swap\s' "$D/fstab.cachyos" || true
    grep -E '^/swap/swapfile\s' "$D/fstab.cachyos" || true
    grep -E '^[^#].*\s/mnt/ntfsdrive\s' "$D/fstab.cachyos" || true
  } > /etc/fstab
  mkdir -p /swap /mnt/ntfsdrive
fi
cat /etc/fstab

say "12/12 Computer name, network, tools and your account"
echo legion > /etc/hostname
emerge --noreplace net-misc/networkmanager app-admin/sudo app-shells/fish sys-fs/btrfs-progs \
  sys-fs/dosfstools app-eselect/eselect-repository dev-vcs/git app-portage/gentoolkit app-portage/eix
systemctl enable NetworkManager systemd-timesyncd fstrim.timer
echo "Password for root:"
passwd root
getent group "$USER_GID" >/dev/null || groupadd -g "$USER_GID" "$USERNAME"
if ! id "$USERNAME" >/dev/null 2>&1; then
  extra=$(for g in wheel video input usb users; do getent group "$g" >/dev/null && printf '%s,' "$g"; done; true)
  useradd -M -d "/home/$USERNAME" -u "$USER_UID" -g "$USER_GID" -G "${extra%,}" -s /usr/bin/fish "$USERNAME"
  echo "Password for $USERNAME (can be the same as on CachyOS):"
  passwd "$USERNAME"
fi
id "$USERNAME"
[ -d "/home/$USERNAME" ] && ls -ld "/home/$USERNAME"

say "Checking the signatures"
sbctl verify || true

say "Phase 2 done"
cat <<'EOF'
Leave the chroot and restart into Gentoo:

  exit
  umount -R /mnt/gentoo
  umount /mnt/btrfs-top
  reboot

In the boot menu pick "Gentoo" (systemd-boot). CachyOS is still there through the F12 menu.
You'll get a text login: that's expected. Log in as yourself and continue with phase 3.
EOF
