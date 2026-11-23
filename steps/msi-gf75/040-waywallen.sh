# title: Waywallen live wallpapers
# section: 6. Waywallen live wallpapers (KDE Plasma)
# default: off
# manual: Add Waywallen in System Settings > Autostart, set the desktop's Wallpaper type to Waywallen, and in Waywallen pick the Intel GPU, pause when a window is fullscreen, 30 fps.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  pacman -Q waywallen-bin >/dev/null 2>&1 || { echo "Waywallen isn't installed"; return 1; }
  pacman -Q plasma-wallpaper-waywallen >/dev/null 2>&1 || { echo "Waywallen's Plasma wallpaper plugin isn't installed"; return 1; }
}

apply() {
sudo pacman -S --needed intel-media-driver
@aur waywallen-bin
@aur plasma-wallpaper-waywallen
}
