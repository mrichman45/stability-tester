# MSI GF75 Thin: Linux guide

| | |
|---|---|
| **Hardware** | MSI GF75 Thin 10SCXR: Intel 10th-gen Core (i5-10300H or i7-10750H), NVIDIA GTX 1650 with switchable graphics (Optimus), Intel Wi-Fi 6 AX201, Realtek gigabit Ethernet |
| **System** | CachyOS, KDE Plasma 6 |
| **Checkup profile** | `msi-gf75` in [`machines.json`](../machines.json) |

The **Checkup** app in this repo checks that every fix below is still in place and still works.
**Set up this laptop** applies all of them in one go (after a reinstall, for example). When a problem
Checkup found gets fixed, it adds an entry to the [Fix log](#fix-log) at the bottom.

> **Placeholders.** Personal details are replaced so this repo can be public:
> `<your-username>` your login name · `<hostname>` the laptop's network name ·
> `<windows-drive-uuid>` the Windows partition's UUID (find it with `lsblk -f`) ·
> `<partition>` a partition such as `/dev/nvme0n1p3` · `<router-or-dns-ip>` an IP address on your network ·
> `<network-share>` a shared folder on your network. Use your own values when you copy a command.

---
## Reinstalling this laptop

1. Install CachyOS with **KDE Plasma**.
2. Install Checkup:
   ```bash
   sudo pacman -S --needed git base-devel
   git clone https://github.com/mrichman45/stability-tester ~/.local/src/stability-tester
   cd ~/.local/src/stability-tester && makepkg -si
   ```
3. Open **Checkup** from the app menu, go to **My Setup**, and press **Set up this laptop**.
   It recognises the laptop by its hardware, asks for your password once, applies every fix in this
   guide (including the apps and settings listed under "Also set up on this laptop"), then lists anything
   that has to be done by hand (rebooting, BIOS settings, Secure Boot keys).
4. After big updates, run **Stability → Test this laptop's profile** to check the fixes still work.
   **Reapply fixes** puts back anything an update broke.

---
## Hardware notes

- **Graphics:** the GTX 1650 is a laptop GPU that works alongside the Intel graphics. Install the NVIDIA
  driver with CachyOS Hello's hardware detection (or `sudo chwd -a`). Apps run on the Intel graphics
  unless started on the NVIDIA card; Steam and most games choose it automatically.
- **Touchpad:** the Arch wiki lists touchpad support on the GF75 Thin 10SC as only partial. If gestures or
  tapping misbehave, check System Settings → Touchpad first.
- **BIOS:** press F2 at startup.
- **Memory:** often 8 GB in a single stick. The stability test's RAM check uses part of the free memory.

---

## Updates and packages

<a id="reading-an-update-list"></a>
### Reading an update list

- Version numbers ending in `.1` (like `-2.1`) are CachyOS's optimised rebuilds. Changing to a plain
  number (`-2.1` → `-3`) is fine.
- **Kernel** (`linux-cachyos-*`) or **NVIDIA** packages in the list mean **reboot afterwards**.
- AUR packages are compiled on the laptop, so they take longer.
- Always update with `sudo pacman -Syu`. Never `pacman -Sy <package>` on its own: that's a partial
  upgrade and can break programs.
- Use `sudo <command>` rather than `sudo su`.

<a id="install-404"></a>
### "404" errors when installing a package

**Symptom:** `failed retrieving file ... The requested URL returned error: 404`
**Cause:** the package list is out of date; the server already has a newer version.
**Fix:**
```bash
sudo pacman -Syu <package>
# still 404? refresh everything and re-rank mirrors
sudo pacman -Syyu
sudo cachyos-rate-mirrors
```

<a id="uninstall"></a>
### Uninstalling programs

```bash
pacman -Qs <name>               # find the exact package name
sudo pacman -Rns <package>      # remove it and dependencies nothing else needs
flatpak list                    # Flatpak apps
flatpak uninstall <app>
```

<a id="nvidia-mismatch"></a>
### Update fails: `nvidia-utils ... breaks dependency ... required by lib32-nvidia-utils`

**Cause:** the new NVIDIA driver arrived, but CachyOS hadn't rebuilt the 32-bit copy yet. pacman takes
packages from the highest-priority repo (CachyOS's), even when Arch's `multilib` has the matching version.
**Fix:** find which repo has the matching version and name it:
```bash
pacman -Si lib32-nvidia-utils | grep -E 'Repository|Version'
sudo pacman -Syu multilib/lib32-nvidia-utils     # the repo that shows the new version
```
Then reboot. **Never** force it with `-dd` or `--overwrite`, and never ignore only `nvidia-utils`:
a mismatched driver means a black screen at boot.

### "Driver/library version mismatch" from nvidia-smi
An NVIDIA update was installed but the old driver is still loaded. Reboot.

---

## Gaming

<a id="hybrid-gpu"></a>
### Which graphics card a game uses

The Intel graphics drives the screen, and the GTX 1650 wakes up when a program asks for it.
- **Most Steam games (through Proton) pick the NVIDIA card by themselves.**
- Some programs (older OpenGL games, launchers, emulators) stay on the Intel graphics. Start those with
  `prime-run`: in Steam, right-click the game → **Properties** → **Launch Options**: `prime-run %command%`

To check while a game is running: `nvidia-smi`. If the game is listed under **Processes**, it's on the NVIDIA card.

<a id="anti-cheat"></a>
### Will a game run?

A kernel change never decides this. What blocks games on Linux is **anti-cheat** in some online games
(Valorant, Call of Duty and Battlefield 6, for example). Single-player games almost always work.
Before buying, check the game on [ProtonDB](https://www.protondb.com) and the
[GamingOnLinux anti-cheat list](https://www.gamingonlinux.com/anticheat).
The GTX 1650 is an entry-level card: check a game's minimum requirements too.

---

## Drives

<a id="usb-automount"></a>
### Auto-mount USB drives

```bash
kcmshell6 kcm_device_automounter
```
Tick **On Login** and **On Attach**, Apply, then **reboot** (a KDE bug hides the device list until you do).
Fallback: `sudo pacman -S udisks2 udiskie` and autostart `udiskie`.

The grayed-out **Disks & Cameras** item in System Settings is a category heading, not a broken setting.

---

## Network

<a id="dns"></a>
### "Resolving timed out" and very slow downloads

Check how long a lookup takes: `time getent hosts wikipedia.org` should be well under 100 ms.
`resolvectl status | grep 'DNS Server'` shows which DNS server is in use (e.g. `<router-or-dns-ip>`).

On **airplane Wi-Fi** this is normal: satellite links add about half a second to every lookup.
Don't change DNS settings there (airlines often block outside DNS) and postpone big updates until you land.
Elsewhere: restart the router, or set DNS to `1.1.1.1, 9.9.9.9` in the Wi-Fi connection's IPv4 settings.

<a id="harmless"></a>
### Harmless messages in the system log

- `wpa_supplicant ... multicast RX registrations are not supported`: Wi-Fi Direct isn't supported by the
  Wi-Fi driver. Normal Wi-Fi isn't affected.

---

## Fix log

Entries below are added automatically by Checkup when a problem it found has been fixed.

<!-- checkup:fix-log -->
