# Lenovo i7-13620H: Linux guide

| | |
|---|---|
| **Hardware** | Lenovo laptop, Intel Core i7-13620H |
| **System** | CachyOS, KDE Plasma 6 |
| **Checkup profile** | `lenovo-i7` in [`machines.json`](../machines.json) |

This laptop uses the **fish** shell (the CachyOS default).

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

---

## Terminal

<a id="fastfetch"></a>
### Show fastfetch (with the CachyOS logo) in every terminal

CachyOS uses the **fish** shell. In `~/.config/fish/config.fish`:
```fish
function fish_greeting
    fastfetch --logo cachyos
end
```
The bash version (`if [ ... ]; then ... fi`) doesn't work in fish. Checkup's fix removes any earlier
attempts (duplicates, bash syntax, Alacritty-only versions) and keeps one correct block.

To set the logo in fastfetch's own config instead: `fastfetch --gen-config`, then in
`~/.config/fastfetch/config.jsonc` set `"logo": { "source": "cachyos" }`.

---

## Docker

<a id="docker"></a>
### Docker daemon not running / user not in docker group

**Cause:** Docker wasn't installed through pacman, so the `docker` group didn't exist either.
**Fix:**
```bash
sudo pacman -S docker
sudo systemctl enable --now docker.service
sudo usermod -aG docker <your-username>
```
Then **log out and back in** (or reboot). Test with `docker run hello-world`.

---

## Media

<a id="vlc"></a>
### VLC: "Codec not supported" for h264 or DTS

**Cause:** Arch split VLC's plugins into separate packages.
**Fix:**
```bash
sudo pacman -S vlc-plugins-all      # or just: vlc-plugin-ffmpeg
rm -rf ~/.cache/vlc                 # if it still complains
```

---

## Drives

<a id="ntfs"></a>
### Windows (NTFS) drive won't mount: "wrong fs type, bad option, bad superblock"

**Symptom:** the file manager says
`Error mounting <partition> at /run/media/<your-username>/<windows-drive-uuid>: wrong fs type...`
**Cause:** Windows left the drive "dirty" (Fast Startup or filesystem errors).
`sudo dmesg | grep -i ntfs` shows `volume is dirty and "force" flag is not set`.
**Fix:**
- Best: boot Windows, run `chkdsk C: /f` as administrator, turn off Fast Startup
  (Control Panel → Power Options → "Choose what the power buttons do"), and shut down fully.
- From Linux, `ntfsfix` comes from the **ntfsprogs** package:
  ```bash
  sudo pacman -S ntfsprogs
  sudo ntfsfix -d <partition>
  ```
  This only clears the flag; it isn't a full repair.

Never use the `force` mount option.

<a id="ntfs-automount"></a>
### Auto-mount the Windows drive at boot

```bash
lsblk -f                         # find the ntfs partition's UUID
sudo mkdir -p /mnt/windows
echo 'UUID=<windows-drive-uuid>  /mnt/windows  ntfs3  defaults,uid=1000,gid=1000,umask=022,nofail,x-gvfs-show  0 0' | sudo tee -a /etc/fstab
sudo systemctl daemon-reload && sudo mount -a
```
`uid`/`gid` come from the `id` command (usually 1000). `nofail` lets the laptop boot even if the drive won't mount.
Checkup finds the Windows partition by itself, and its fix also removes duplicate or broken lines for the drive.

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
---

## Fix log

Entries below are added automatically by Checkup when a problem it found has been fixed.

<!-- checkup:fix-log -->
