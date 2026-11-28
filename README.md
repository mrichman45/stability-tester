# Stability Tester

**Checkup** is a desktop app (and terminal tool) for our CachyOS laptops. It has three parts:

| Tab | What it does | Works on |
|---|---|---|
| **My Setup** | Scans the laptop for apps and settings its guide doesn't cover yet and adds them automatically. Checks every fix from the guide; **Set up this laptop** applies all of them in one go, for example after a reinstall. | Laptops with a profile |
| **Stability** | Stress-tests the CPU, GPU, RAM and disks with live temperature graphs, and checks the system log for hardware errors. On a profiled laptop it also tests that the laptop's profile still **works**, and **Reapply fixes** puts back anything an update broke. | Any computer |
| **Guide** | Shows this laptop's guide. Fixed problems are added to its fix log automatically, and **Sync with GitHub** shares them. | Laptops with a profile |

## Laptops

| Profile | Laptop | Guide |
|---|---|---|
| `lenovo-i7` | Lenovo, Intel i7-13620H | [guides/lenovo-i7.md](guides/lenovo-i7.md) |
| `legion-i9` | Lenovo Legion, Intel i9, NVIDIA RTX | [guides/legion-i9.md](guides/legion-i9.md) |
| `msi-gf75` | MSI GF75 Thin 10SCXR, NVIDIA GTX 1650 | [guides/msi-gf75.md](guides/msi-gf75.md) |

Laptops are recognised by their hardware. Which fixes belong to which laptop is set in
[`machines.json`](machines.json). Edit it in your clone and the app picks the change up straight away.

## Where things live

Source folders go in the hidden `~/.local/src/` (this repo, `kcm-webcam`, `kwin-integration`, `kando-bin`),
and app data in `~/.local/share/` (for example `er-save-manager`), so the home folder stays tidy.

## Tools

| Tool | What it does |
|---|---|
| [`tools/er-save-manager-update`](tools/er-save-manager-update) | Installs the Elden Ring Save Manager (Linux) and keeps it up to date; its app icon checks for updates on launch. See the Legion guide's Gaming section. |

## Alternatives (optional)

[`alternatives/`](alternatives/) holds other operating systems for these laptops, in case you ever switch:
for now, [Gentoo on the Legion i9](alternatives/gentoo-legion-i9/). Checkup doesn't use that folder and
the package doesn't install it.

## Install

```bash
sudo pacman -S --needed git base-devel
git clone https://github.com/mrichman45/stability-tester ~/.local/src/stability-tester
cd ~/.local/src/stability-tester
makepkg -si
```

Then open **Checkup** from the app menu. Keep the clone in `~/.local/src/stability-tester` (a hidden folder, so it
stays out of the way; an older clone in `~/stability-tester` still works): the app reads the
guides and profiles from there, so the fix logs can be synced back to GitHub.

To update the app later: `cd ~/.local/src/stability-tester && git pull && makepkg -sif`.

## Terminal version

```bash
checkup-cli setup            # scan, then check this laptop against its guide
checkup-cli review           # remove things the scan added
checkup-cli apply            # apply every fix from the guide (one confirmation)
checkup-cli stability --quick
checkup-cli guide --sync     # commit and push the guide's fix log
checkup-cli machine --set legion-i9   # if the laptop isn't recognised
```

## How fixes are applied

- Every command is shown before it runs, and you confirm first.
- **You enter your password once per session.** Checkup then starts a small administrator helper
  (`checkup-root`) and runs every later step through it, so long setups never ask again.
- Fixes run inside the app, showing each command and its output live. If a step fails, the rest stop.
- Steps that should run as you (your settings, your services, building packages) run as you, not as root.
- Config files Checkup edits itself (your fish config, `/etc/fstab`) are backed up first.
- Checks also catch fixes that were applied wrongly: duplicates, wrong syntax, wrong options, or undone changes.
- Things that can't be automated safely (rebooting, BIOS settings, Secure Boot keys, the camera switch) are
  listed as "do by hand".

## The scan

Every time **My Setup** checks the laptop, it also compares it with how it looked right after installing
(from `/var/log/pacman.log`) and adds what you set up yourself to the laptop's guide and profile:
apps from the repos, the AUR and Flathub, apps you removed, services you enabled, groups you joined, your login
shell, and network shares (as placeholders only, since they need passwords). **Review found items** removes
anything you don't want, and it won't be added again. **Sync with GitHub** shares the updated guide and profile.

## Privacy

The guides and profiles contain no names, IP addresses, network shares, drive UUIDs or other personal
details; they use placeholders like `<your-username>`. Things Checkup learns on a laptop (which profile it is,
the Windows partition) are stored only on that laptop, in `~/.config/checkup/`.

License: GPL-2.0-or-later.
