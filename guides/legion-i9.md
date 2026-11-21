# Lenovo Legion i9: Linux guide

| | |
|---|---|
| **Hardware** | Lenovo Legion, Intel Core i9, NVIDIA RTX graphics, camera kill switch |
| **System** | CachyOS, KDE Plasma 6 |
| **Checkup profile** | `legion-i9` in [`machines.json`](../machines.json) |

Uses **Secure Boot** with sbctl, and **Alacritty** instead of Konsole.

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
   git clone https://github.com/mrichman45/stability-tester ~/stability-tester
   cd ~/stability-tester && makepkg -si
   ```
3. Open **Checkup** from the app menu, go to **My Setup**, and press **Set up this laptop**.
   It recognises the laptop by its hardware, applies every fix in this guide, then lists anything
   that has to be done by hand (rebooting, BIOS settings, Secure Boot keys).
4. After big updates, run **Stability → Test this laptop's profile** to check the fixes still work.
   **Reapply fixes** puts back anything an update broke.

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

<a id="secure-boot"></a>
### Secure Boot after a kernel update

sbctl re-signs the kernel automatically. Before rebooting after a kernel update, check:
```bash
sudo sbctl verify                      # every file should be ✓ signed
sudo sbctl sign -s /path/from/the/list # only if something shows ✗
```
The NVIDIA driver doesn't need signing in this setup.

<a id="shelly-remove"></a>
### Removing Shelly: "breaks dependency required by shelly-flatpak-backend"

```bash
sudo pacman -Rns shelly shelly-flatpak-backend
```
Shelly is CachyOS's default graphical package manager; reinstall it any time with `sudo pacman -Syu shelly`.

---

## Terminal

<a id="konsole"></a>
### Using Alacritty instead of Konsole

1. System Settings → **Default Applications** → **Terminal Emulator** → **Alacritty**.
2. `sudo pacman -Rns konsole`
3. Dolphin's built-in terminal panel (F4) stops working; "Open Terminal Here" opens Alacritty.

If Alacritty ever breaks: **Ctrl+Alt+F3** gives a text login, and `sudo pacman -S konsole` brings Konsole back.

---

## Camera

<a id="webcam"></a>
### Webcam not detected

1. Check the **camera switch** on the right side of the laptop. When it's off, the camera disappears completely.
2. `ls /dev/video*` should list `/dev/video0` (`video1` is metadata).
3. Test with `guvcview`. Only one app can use the camera at a time.

<a id="kcm-webcam"></a>
### Webcam settings page in System Settings

Installed from [kcm-webcam](https://github.com/mrichman45/kcm-webcam). Settings saved with **Apply** are
restored at login and when the camera switch is turned back on, as long as the service is enabled:
```bash
systemctl --user enable --now webcam-settings.service
```
If the page disappears after a big KDE update, run `makepkg -sif` in the kcm-webcam folder.

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

<a id="nordvpn"></a>
### NordVPN

```bash
paru -S nordvpn-bin
sudo systemctl enable --now nordvpnd
sudo usermod -aG nordvpn <your-username>     # then log out and back in
nordvpn login
nordvpn connect
```
"Cannot reach System Daemon" means the service isn't running, or you haven't logged out and back in yet.
VPNs often don't work on airplane Wi-Fi.
---

## Fix log

Entries below are added automatically by Checkup when a problem it found has been fixed.

<!-- checkup:fix-log -->
