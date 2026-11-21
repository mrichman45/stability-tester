# Stability Tester

**Checkup** is a desktop app (and terminal tool) for our CachyOS laptops. It has three parts:

| Tab | What it does | Works on |
|---|---|---|
| **My Setup** | Checks every fix from this laptop's guide. **Set up this laptop** applies all of them in one go, for example after a reinstall. | Laptops with a profile |
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

## Install

```bash
sudo pacman -S --needed git base-devel
git clone https://github.com/mrichman45/stability-tester ~/stability-tester
cd ~/stability-tester
makepkg -si
```

Then open **Checkup** from the app menu. Keep the clone in `~/stability-tester`: the app reads the
guides and profiles from there, so the fix logs can be synced back to GitHub.

To update the app later: `cd ~/stability-tester && git pull && makepkg -sif`.

## Terminal version

```bash
checkup-cli setup            # check this laptop against its guide
checkup-cli apply            # apply every fix from the guide (one confirmation)
checkup-cli stability --quick
checkup-cli guide --sync     # commit and push the guide's fix log
checkup-cli machine --set legion-i9   # if the laptop isn't recognised
```

## How fixes are applied

- Every command is shown before it runs, and you confirm first.
- Commands that need your password run in a terminal window you can watch. If a step fails, the rest stop.
- Config files Checkup edits itself (your fish config, `/etc/fstab`) are backed up first.
- Checks also catch fixes that were applied wrongly: duplicates, wrong syntax, wrong options, or undone changes.
- Things that can't be automated safely (rebooting, BIOS settings, Secure Boot keys, the camera switch) are
  listed as "do by hand".
- Administrator access for tests uses a small read-only helper (`checkup-root`) that can only run the RAM test,
  read disk health, Secure Boot status and the system log.

## Privacy

The guides and profiles contain no names, IP addresses, network shares, drive UUIDs or other personal
details; they use placeholders like `<your-username>`. Things Checkup learns on a laptop (which profile it is,
the Windows partition) are stored only on that laptop, in `~/.config/checkup/`.

License: GPL-2.0-or-later.
