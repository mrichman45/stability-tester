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

### NVIDIA extras updating a day later
After a driver update, `opencl-nvidia`, `lib32-opencl-nvidia`, `nvidia-settings` and `libxnvctrl` may arrive
in a later update as CachyOS finishes rebuilding them. That's normal and safe. No reboot is needed for
these alone; restart apps that use OpenCL (Blender, DaVinci Resolve, AI tools).

<a id="kernel"></a>
### Kernel: one kernel, the LTS one

This laptop runs **only** `linux-cachyos-lts`, by choice:
- it changes the least, which matters with no second kernel to fall back on;
- fewer updates means fewer NVIDIA catch-ups, Secure Boot re-signs and reboots;
- nothing on this laptop needs a newer kernel (checked: NVIDIA, Wi-Fi, webcam, Secure Boot, Proton gaming).

The safety net instead of a second kernel is the **boot snapshots**: CachyOS snapshots the system before
updates, and the boot menu can start from one.

Kernel packages that belong together: `linux-cachyos-lts`, `linux-cachyos-lts-headers`,
`linux-cachyos-lts-nvidia-open`. Checkup's **One kernel, with its NVIDIA module** check makes sure exactly these
are installed: it adds a missing piece, and removes any extra kernel (never the one that's running).
The kernel this laptop should use is set by `"kernel"` in `machines.json`; change it there if you switch.

**If a newer kernel is ever needed** (a new game or device that needs it), switch safely:
```bash
sudo pacman -S linux-cachyos linux-cachyos-headers linux-cachyos-nvidia-open
sudo sbctl verify                       # sign anything marked ✗ with: sudo sbctl sign -s <file>
# reboot, choose the new kernel, check `uname -r` and run Checkup's profile test, then:
sudo pacman -Rns linux-cachyos-lts linux-cachyos-lts-headers linux-cachyos-lts-nvidia-open
```
Never remove the running kernel before the new one has booted successfully.

To check for hardware problems a kernel change might fix:
```bash
journalctl -b -p err --no-pager | grep -iE 'firmware|driver|not supported|failed to load' | head -20
```

<a id="secure-boot"></a>
### Secure Boot after a kernel or bootloader update

sbctl re-signs the kernel automatically. Before rebooting after an update that includes the kernel
(`linux-cachyos-lts`) **or the bootloader** (`limine`), check:
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

## Sound

<a id="speakers"></a>
### Speakers silent or quiet (TAS2781 amplifier)

The Legion's speaker amplifier (Texas Instruments TAS2781) needs a fix on Linux. This laptop uses
[tas2781-fix-16IRX8H](https://github.com/DanielWeiner/tas2781-fix-16IRX8H), made for the Legion Pro 7 16IRX8H.
It applies the fix when the sound system starts and again after waking from sleep.

Install (Checkup's **Speaker fix installed** check does this for you):
```bash
sudo pacman -S --needed git jq i2c-tools
git clone https://github.com/DanielWeiner/tas2781-fix-16IRX8H ~/.local/src/tas2781-fix-16IRX8H
sudo bash ~/.local/src/tas2781-fix-16IRX8H/tas2781-fix --install    # the script's name in that folder
systemctl --user enable --now tas2781-fix.service
```
Then restart.

- Speakers silent again: `systemctl --user restart tas2781-fix.service`
- Check it ran: `systemctl status tas2781-fix.service` should say **active (exited)**.
- Remove: `/usr/local/bin/tas2781-fix --uninstall`
- A future kernel may fix the amplifier by itself; the fix is harmless either way.

---

## Set up this laptop: the guide's steps

Every setup section of the full Legion guide is a step in `steps/legion-i9/`: a test that says whether
it's done, and the commands that do it. **Set up this laptop** runs every step that isn't done, with
one password prompt. Steps already done are skipped. A file you've changed on this laptop (a config,
a script) is never overwritten: Checkup offers to save your version to the repo instead, with your
username, drive IDs and network replaced by placeholders. Optional steps start unticked;
`checkup-cli apply --optional` includes them.

Not automated, because they happen outside CachyOS or in another app's window: the BIOS settings
(install step 1), the installer itself (install steps 2–6), Secure Boot's Setup Mode and key
enrolment (section 17), fan presets in `sudo legion_gui`, Steam/Heroic settings, the Windows side of
WinBoat, and Bottles (Flatpak only). Checkup still tests the ones it can and says what to do.

| Step | Guide section | How |
|---|---|---|
| Base packages the later sections rely on | Install step 7. First boot and checks | automatic |
| First-boot checks: multilib, firewall, snapshots, fish | Install step 7. First boot and checks | automatic |
| Computer name "legion" | 2. Kernel, power modes and fans | automatic |
| NTFS data drive mounts at /mnt/ntfsdrive | 1. The NTFS data drive | automatic — only when [ -n "$NTFS_UUID" ] |
| Proton prefixes for the NTFS Steam library live on the Linux drive | Games on the NTFS drive | automatic — only when [ -d /mnt/ntfsdrive/Games/SteamLibrary/steamapps ] |
| Dolphin doesn't offer the data drive twice or ask to mount Windows | Errors seen and fixes | automatic — only when [ -n "$NTFS_UUID" ] |
| The LTS kernel starts by default | Kernel and stability settings | automatic |
| Drive health warnings, monthly scrub, and trim done once | Kernel and stability settings | automatic |
| Legion module reloads itself after a driver update | If the Legion module stops being loaded | automatic |
| LenovoLegionLinux: fans, Fn+Q modes, battery limit | Fans, power modes, battery (Vantage replacement) | automatic |
| legiond: fan presets on, its CPU and GPU control off | Enable legiond (automatic fan profiles) | automatic — only when [ -d /usr/share/legion_linux ] &#124;&#124; [ -d /etc/legion_linux ] |
| PRIME offload tools, Intel Vulkan, nvidia-persistenced off | 3. Graphics: which GPU runs what | automatic |
| RTX HDMI audio switch (lets the RTX power down) | HDMI audio switch | optional (unticked) |
| GPU widgets don't wake the RTX | GPU widgets that don't wake the RTX | automatic — only when [ -e ~/.local/share/nvstats-service/backend/nvstats_gpu.py ] &#124;&#124; [ -e ~/.local/share/plasma/plasmoids/org.dfuse.hardwaremonitor/contents/scripts/sensors.py ] |
| intel-run (pins an app to the Intel GPU) | intel-run and the Steam menu entry (plumbing for section 3's GPU rules) | automatic |
| Every way of starting Steam goes through steam-gpu | intel-run and the Steam menu entry (plumbing for section 3's GPU rules) | automatic — only when [ -e /usr/share/applications/steam.desktop ] |
| Heroic games pick their GPU when they launch | Heroic: the GPU per game | automatic — only when [ -e ~/.config/heroic/config.json ] |
| Eden (Switch emulator) in the menu, on the GPU rules | Eden (Switch emulator) | automatic — only when [ -e ~/Applications/Eden.AppImage ] |
| Speakers never go to sleep (no silence after Bluetooth) | Speakers: no sound after switching from Bluetooth | automatic |
| Built-in mic: fan noise removed | Mic: remove fan noise | automatic |
| Dock mic: keyboard and fan noise removed | Bluetooth headset (Galaxy Buds3 Pro) | automatic |
| USB headsets start with their analog mic | Bluetooth headset (Galaxy Buds3 Pro) | automatic |
| Bigger audio buffer for every app (no hiccups in games) | Audio buffer for every app (stops hiccups) | automatic |
| Hardware video decoding and recording on the Intel GPU | Hardware video on the Intel GPU | automatic |
| Firmware updates (fwupd) | Firmware updates | automatic |
| Kup backups | Backups of your files | automatic |
| Printing and scanning | Printing and scanning | automatic |
| Canon UFR II printer driver | Printers | automatic |
| Microsoft fonts for Office documents | Microsoft fonts | automatic |
| OneDrive as a folder (rclone) | OneDrive (if you use it) | optional (unticked) |
| Japanese typing (Fcitx 5 + Mozc) | Japanese typing (Fcitx 5 + Mozc) | automatic |
| Anki starts (software rendering) and plays card audio | Anki | automatic — only when pacman -Q anki &#124;&#124; pacman -Q anki-bin &#124;&#124; pacman -Q anki-qt5 |
| Gaming stack: Steam, Heroic, Lutris, MangoHud, proton-cachyos, GE-Proton | 6. Gaming | automatic |
| Bigger NVIDIA shader cache | 6. Gaming | automatic |
| The Convergence: Seamless Co-op or Solo picker | Step 7: Choose Seamless Co-op or Solo each launch | optional (unticked) — only when [ -d ~/Games/ConvergenceER ] |
| Docker networks stay off your home network's addresses | 8. Docker, and reaching your home network from containers | automatic — only when pacman -Q docker |
| WinBoat with working USB passthrough | 9. WinBoat: Windows apps, with your shares | optional (unticked) |
| legion-integrity (is the system intact?) | Integrity check | automatic |
| pacman checks for free space before updating | Config files pacman left as .pacnew | automatic |
| No outdated NVIDIA options at boot | Leftover NVIDIA options after an update | automatic — only when ls /etc/modprobe.d/*.conf |
| Hibernation (32 GiB swapfile, resume from it) | 14. Hibernation | automatic |
| Blu-ray: MakeMKV and VLC | 15. Blu-ray: MakeMKV and VLC | optional (unticked) |
| Waywallen starts at login, on the Intel GPU | 16. Waywallen at login (KDE Plasma) | automatic — only when command -v waywallen |
| Limine re-signs itself after every snapshot (Secure Boot) | 17. Secure Boot (do this last) | automatic — only when pacman -Q sbctl |
| Secure Boot is on | 17. Secure Boot (do this last) | you do it; Checkup checks |
| Windows is in the boot menu | Install step 8. Windows in the boot menu (when reinstalling) | you do it; Checkup checks — only when [ -n "$WINDOWS_UUID" ] |

## Custom Legion services (power, audio, GPU)

These are the services written for this laptop. The files live in `tools/legion/` in this repo, with
`__USER__` and `__NTFS_UUID__` as placeholders; Checkup fills those in when it installs them and puts the
placeholders back when it saves your edits to the repo. **Set up this laptop** installs all of them;
the *Legion services* check reports anything missing, switched off or edited since the repo copy.

| File | Where it goes | What it does |
|---|---|---|
| `legion-system` + `legion-system.service` | `/usr/local/bin`, `/etc/systemd/system` | Root service: wakes the RTX, sets CPU speed caps and fans per Fn+Q mode, keeps power-profiles-daemon in step, runs nvidia-powerd only on the charger, then calls legion-power |
| `legion-power` | `/usr/local/bin` | Battery vs charger tuning; stops GPU-polling user services (nvstats) on battery |
| `10-modprobe.conf`, `legion.conf` | `legion-system.service.d/`, `/etc/modules-load.d/` | Loads the `legion_laptop` module at boot and before legion-system |
| `legion-session` + `legion-session.service` | `~/.local/bin`, `~/.config/systemd/user` | Per-login: headset switching (Bluetooth, USB dock, HDMI), call mode, speaker wake, weekly update reminder, repairs its own audio configs |
| `gpu-run`, `game-gpu`, `steam-gpu`, `gpu-app` | `~/.local/bin` | Start an app on the RTX on the charger, Intel on battery (`gpu-run --which` shows which) |
| `steam-power-watch.service`, `gpu-app-auto.path/.service` | `~/.config/systemd/user` | Re-route Steam and newly installed games when power or the app menu changes |
| `ntfs-autofix.sh` | `/usr/local/sbin` | Repairs a dirty NTFS data drive at boot so it still mounts (`--install` sets up its boot service) |

Also needed: `legiond` and `legiond-onresume` from LenovoLegionLinux on, `legiond-cpuset.timer` off,
`nvidia-powerd` not enabled at boot (legion-system starts it on the charger).

Check they're running:

```bash
systemctl status legion-system              # active (running)
systemctl --user status legion-session      # active (running)
journalctl -t legion-system -n 5
journalctl -t legion-session -n 5
```

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
If the page disappears after a big KDE update, run `makepkg -sif` in `~/.local/src/kcm-webcam` (Checkup downloads it again if it is missing).

---

## Gaming

<a id="hybrid-gpu"></a>
### Which graphics card a game uses (GPU mode: Auto)

The Intel graphics drives the screen, and the NVIDIA card wakes up when a program asks for it.
- **Most Steam games (through Proton) pick the NVIDIA card by themselves.**
- Some programs (older OpenGL games, launchers, emulators) stay on the Intel graphics. Start those with
  `prime-run`: in Steam, right-click the game → **Properties** → **Launch Options**: `prime-run %command%`

To check while a game is running: `nvidia-smi`. If the game is listed under **Processes**, it's on the NVIDIA card.
Lenovo's automatic GPU switching relies partly on its Windows software; on Linux, Auto behaves like Hybrid.

<a id="anti-cheat"></a>
### Will a game run?

A kernel change never decides this. What blocks games on Linux is **anti-cheat** in some online games
(Valorant, Call of Duty and Battlefield 6, for example). Single-player games almost always work.
Before buying, check the game on [ProtonDB](https://www.protondb.com) and the
[GamingOnLinux anti-cheat list](https://www.gamingonlinux.com/anticheat).

- **007 First Light:** Steam Deck Verified, no anti-cheat, plays fine on CachyOS. Known quirk: the resolution
  may not be saved between sessions; set it again in the game's settings.

<a id="elden-ring"></a>
### Elden Ring: Save Manager that updates itself

`tools/er-save-manager-update` in this repo installs the Linux version of the Elden Ring Save Manager
(Hapfel1/er-save-manager) and keeps it up to date:
```bash
install -Dm755 ~/.local/src/stability-tester/tools/er-save-manager-update ~/.local/bin/er-save-manager-update
er-save-manager-update
```
- Clicking its icon checks for an update first (8 seconds at most), then opens the app.
- Right-click the icon: **Check for updates now**, or **Open previous version** if an update misbehaves.
- `er-save-manager-update --enable-auto` also checks daily. Settings and save backups are never touched.
- FUSE error when it starts: `sudo pacman -S fuse2`.
- The app itself lives in `~/.local/share/er-save-manager` (an older `~/Applications/er-save-manager` is moved there
  automatically the next time the updater runs).
- Checkup's **Elden Ring Save Manager updates itself** check installs the updater (and the Save Manager) after a
  reinstall, and keeps the updater script in step with this repo.

**The Convergence mod** keeps its own save file, separate from normal characters, and updates through its
own downloader. Before updating it: back up the Convergence save, and check the mod supports the current
Elden Ring version (its Discord or Nexus page). Never open modded saves in the unmodded game.

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

- `wpa_supplicant ... nl80211: kernel reports: multicast RX registrations are not supported`:
  Wi-Fi Direct (connecting to printers or phones without a router) isn't supported by the Wi-Fi driver.
  Normal Wi-Fi isn't affected.

<a id="nordvpn"></a>
### NordVPN

```bash
paru -S nordvpn-bin
sudo systemctl enable --now nordvpnd
sudo usermod -aG nordvpn <your-username>     # then log out and back in
nordvpn login
nordvpn connect
```
"Cannot reach System Daemon" (or the app saying "We couldn't connect to NordVPN service") means the service isn't
running, or you aren't in the `nordvpn` group yet: run `sudo groupadd -f nordvpn`, then the `usermod` line above,
and restart. Checkup doesn't check NordVPN.
VPNs often don't work on airplane Wi-Fi.
---

<!-- checkup:found:start -->
## Also set up on this laptop (found by Checkup)

Checkup found these on the laptop and added them to its profile, so **Set up this laptop** redoes them after a reinstall. Remove anything you don't want with **Review** on the My Setup tab.

**Apps**
```bash
sudo pacman -S --needed chntpw dolphin-plugins etcher-bin fcitx5 fcitx5-configtool fcitx5-gtk fcitx5-mozc fcitx5-qt fuse2 gamescope-session-cachyos github-cli gst-plugins-base gst-plugins-good guvcview handbrake intel-media-driver jdk17-openjdk lenovolegionlinux-dkms lib32-gamemode lib32-vulkan-intel libreoffice-fresh-sdk libxml2-legacy nodejs noise-suppression-for-voice npm nvme-cli nvtop obs-studio papirus-icon-theme plasma-disks powertop print-manager qogir-icon-theme rustup s-tui turbostat vivaldi vlc-gui-qt vulkan-intel wit
```

**AUR apps**
```bash
paru -S --needed android-sdk-cmdline-tools-latest
paru -S --needed android-studio
paru -S --needed anydesk-bin
paru -S --needed cemu
paru -S --needed cndrvcups-lb-bin
paru -S --needed er-save-manager
paru -S --needed galaxybudsclient-bin
paru -S --needed lenovo-logo-changer
paru -S --needed logiops
paru -S --needed makemkv-libaacs
paru -S --needed open-wallpaper-engine
paru -S --needed pcsx2
paru -S --needed pear-desktop-bin
paru -S --needed rpcs3-bin
paru -S --needed waywallen
```

**Removed after installing**
```bash
sudo pacman -Rns alsa-tools noisetorch
```

**Services**
```bash
sudo systemctl enable --now legion-system.service
sudo systemctl enable --now vantaged.service
```

**Your services**
```bash
systemctl --user enable --now tas2781-fix.service
```

**Groups** (log out and back in afterwards)
```bash
sudo usermod -aG nopasswdlogin <your-username>
```
<!-- checkup:found:end -->

---

## Fix log

Entries below are added automatically by Checkup when a problem it found has been fixed.

<!-- checkup:fix-log -->

### 2026-11-23 · Lenovo Legion i9 · System up to date
- **Problem:** Couldn't reach the package servers to check for updates.
- **Fix:** Fixed outside Checkup
- **More:** [System up to date](#reading-an-update-list)



### 2026-11-21 · Lenovo Legion i9 · System up to date
- **Problem:** 4 updates available (including the kernel or NVIDIA driver).
- **Fix:** Updated the system
- **More:** [System up to date](#reading-an-update-list)



### 2026-11-21 · Lenovo Legion i9 · fastfetch greeting in fish
- **Problem:** Fastfetch isn't set to run when a terminal opens.
- **Fix:** Repaired the fastfetch greeting in fish
- **More:** [fastfetch greeting in fish](#fastfetch)



### 2026-11-21 · Lenovo Legion i9 · Docker running and usable
- **Problem:** The Docker service is inactive and not enabled at boot.
- **Fix:** Installed/enabled Docker and joined the docker group
- **More:** [Docker running and usable](#docker)



### 2026-11-21 · Lenovo Legion i9 · Secure Boot files signed
- **Problem:** Not signed (the laptop won't boot them): /boot/EFI/BOOT/BOOTX64.EFI, /boot/EFI/Microsoft/Boot/Resources/bootres.dll, /boot/EFI/Microsoft/Boot/Resources/en-US/bootres.dll.mui, /boot/EFI/Microsoft/Boot/SecureBootRecovery.efi, /boot/EFI/Microsoft/Boot/bg-BG/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/bg-BG/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/bootmgfw.efi, /boot/EFI/Microsoft/Boot/bootmgr.efi, /boot/EFI/Microsoft/Boot/cs-CZ/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/cs-CZ/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/cs-CZ/memtest.efi.mui, /boot/EFI/Microsoft/Boot/da-DK/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/da-DK/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/da-DK/memtest.efi.mui, /boot/EFI/Microsoft/Boot/de-DE/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/de-DE/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/de-DE/memtest.efi.mui, /boot/EFI/Microsoft/Boot/el-GR/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/el-GR/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/el-GR/memtest.efi.mui, /boot/EFI/Microsoft/Boot/en-GB/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/en-GB/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/en-US/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/en-US/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/en-US/memtest.efi.mui, /boot/EFI/Microsoft/Boot/es-ES/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/es-ES/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/es-ES/memtest.efi.mui, /boot/EFI/Microsoft/Boot/es-MX/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/es-MX/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/et-EE/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/et-EE/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/fi-FI/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/fi-FI/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/fi-FI/memtest.efi.mui, /boot/EFI/Microsoft/Boot/fr-CA/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/fr-CA/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/fr-FR/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/fr-FR/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/fr-FR/memtest.efi.mui, /boot/EFI/Microsoft/Boot/hr-HR/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/hr-HR/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/hu-HU/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/hu-HU/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/hu-HU/memtest.efi.mui, /boot/EFI/Microsoft/Boot/it-IT/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/it-IT/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/it-IT/memtest.efi.mui, /boot/EFI/Microsoft/Boot/ja-JP/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/ja-JP/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/ja-JP/memtest.efi.mui, /boot/EFI/Microsoft/Boot/kd_02_10df.dll, /boot/EFI/Microsoft/Boot/kd_02_10ec.dll, /boot/EFI/Microsoft/Boot/kd_02_1137.dll, /boot/EFI/Microsoft/Boot/kd_02_1414.dll, /boot/EFI/Microsoft/Boot/kd_02_14e4.dll, /boot/EFI/Microsoft/Boot/kd_02_15ad.dll, /boot/EFI/Microsoft/Boot/kd_02_15b3.dll, /boot/EFI/Microsoft/Boot/kd_02_1969.dll, /boot/EFI/Microsoft/Boot/kd_02_19a2.dll, /boot/EFI/Microsoft/Boot/kd_02_1af4.dll, /boot/EFI/Microsoft/Boot/kd_02_1d0f.dll, /boot/EFI/Microsoft/Boot/kd_02_8086.dll, /boot/EFI/Microsoft/Boot/kd_07_1415.dll, /boot/EFI/Microsoft/Boot/kd_0C_8086.dll, /boot/EFI/Microsoft/Boot/kdnet_uart16550.dll, /boot/EFI/Microsoft/Boot/kdstub.dll, /boot/EFI/Microsoft/Boot/ko-KR/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/ko-KR/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/ko-KR/memtest.efi.mui, /boot/EFI/Microsoft/Boot/lt-LT/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/lt-LT/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/lv-LV/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/lv-LV/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/memtest.efi, /boot/EFI/Microsoft/Boot/nb-NO/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/nb-NO/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/nb-NO/memtest.efi.mui, /boot/EFI/Microsoft/Boot/nl-NL/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/nl-NL/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/nl-NL/memtest.efi.mui, /boot/EFI/Microsoft/Boot/pl-PL/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/pl-PL/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/pl-PL/memtest.efi.mui, /boot/EFI/Microsoft/Boot/pt-BR/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/pt-BR/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/pt-BR/memtest.efi.mui, /boot/EFI/Microsoft/Boot/pt-PT/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/pt-PT/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/pt-PT/memtest.efi.mui, /boot/EFI/Microsoft/Boot/qps-ploc/memtest.efi.mui, /boot/EFI/Microsoft/Boot/qps-plocm/memtest.efi.mui, /boot/EFI/Microsoft/Boot/ro-RO/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/ro-RO/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/ru-RU/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/ru-RU/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/ru-RU/memtest.efi.mui, /boot/EFI/Microsoft/Boot/sk-SK/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/sk-SK/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/sl-SI/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/sl-SI/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/sr-Latn-RS/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/sr-Latn-RS/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/sv-SE/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/sv-SE/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/sv-SE/memtest.efi.mui, /boot/EFI/Microsoft/Boot/tr-TR/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/tr-TR/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/tr-TR/memtest.efi.mui, /boot/EFI/Microsoft/Boot/uk-UA/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/uk-UA/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/zh-CN/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/zh-CN/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/zh-CN/memtest.efi.mui, /boot/EFI/Microsoft/Boot/zh-TW/bootmgfw.efi.mui, /boot/EFI/Microsoft/Boot/zh-TW/bootmgr.efi.mui, /boot/EFI/Microsoft/Boot/zh-TW/memtest.efi.mui
- **Fix:** Signed the unsigned boot files with sbctl
- **More:** [Secure Boot files signed](#secure-boot)


