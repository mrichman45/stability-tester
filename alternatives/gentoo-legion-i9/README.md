# Gentoo on the Legion i9

Scripts and config for replacing CachyOS with Gentoo (systemd, KDE Plasma, Secure Boot) on the
Legion i9, keeping Windows, the NTFS data drive and the `@home` subvolume. The step-by-step guide
is a separate doc; these files are what it runs. No personal details: each script reads them
from the laptop.

| File | Run where | What it does |
|---|---|---|
| `0-on-cachyos.sh DEST` | CachyOS, as yourself | Reads your drives, user, time zone; saves Secure Boot keys, fstab and these files to an external drive. Changes nothing |
| `1-live-usb.sh FOLDER` | Gentoo live USB, as root | Adds `@gentoo` and `@gentoo-snapshots` next to CachyOS's subvolumes, checks and unpacks the stage file, copies the config, prepares the chroot. Formats nothing |
| `2-chroot.sh` | Inside the chroot | Portage, binary packages, profile, locale, keys, signed kernel and systemd-boot, fstab, your account |
| `3-desktop.sh` | New Gentoo, `sudo` | KDE Plasma, NVIDIA, sound, Bluetooth, Japanese input, fonts, Legion module, Steam, MangoHud, snapper |
| `4-legion.sh` | New Gentoo, as yourself | Puts back legion-system, legion-power, the module and NTFS-repair services, legiond's settings |
| `portage/` | copied to `/etc/portage` | `make.conf`, USE flags, keywords, the kernel and Flatpak masks, the x86-64-v3 binary host |
| `etc/` | copied to `/etc`, `/usr/local/bin` | dracut (signed kernel images), NVIDIA options, sudo for wheel, `prime-run` |

Checkup doesn't support Gentoo yet: its steps and checks are written for pacman.
