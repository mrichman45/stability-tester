# title: WinBoat's USB Passthrough panel works (camera, drives)
# section: Making the USB Passthrough panel work
# when: pacman -Q winboat
# check-as: root
# after: Quit WinBoat and open it again, then use USB Passthrough > Add Device.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs socat usbutils libnotify || return 1
  need_files /usr/local/bin/winboat-usb /etc/sudoers.d/winboat-usb /usr/local/bin/winboat-usb-bake /etc/pacman.d/hooks/90-winboat-usb-bake.hook || return 1
  [ ! -e /usr/local/share/applications/winboat-usb.desktop ] && [ ! -e /usr/local/share/applications/winboat-webcam.desktop ] || { echo "the old WinBoat Webcam/USB launcher icons are still in the menu"; return 1; }
}

apply() {
sudo pacman -S --needed socat usbutils libnotify
sudo install -Dm755 $R/winboat-usb /usr/local/bin/winboat-usb
sudo visudo -cf $R/sudoers && install -Dm440 $R/sudoers /etc/sudoers.d/winboat-usb
sudo install -Dm755 $R/winboat-usb-bake /usr/local/bin/winboat-usb-bake
sudo rm -f /etc/pacman.d/hooks/90-winboat-usb-id.hook /usr/local/share/applications/winboat-usb.desktop /usr/local/share/applications/winboat-webcam.desktop /usr/local/bin/winboat-usb-button
sudo install -Dm644 $R/90-winboat-usb-bake.hook /etc/pacman.d/hooks/90-winboat-usb-bake.hook
sudo /usr/local/bin/winboat-usb-bake
kbuildsycoca6 >/dev/null 2>&1; true
}
