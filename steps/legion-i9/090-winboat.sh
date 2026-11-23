# title: WinBoat with working USB passthrough
# section: 9. WinBoat: Windows apps, with your shares
# default: off
# after: Quit WinBoat completely and start it again. Windows-side steps (mapping the file share) are in the guide.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs winboat freerdp socat usbutils libnotify || return 1
  need_files /usr/local/bin/winboat-usb /etc/sudoers.d/winboat-usb /usr/local/bin/winboat-usb-bake /etc/pacman.d/hooks/90-winboat-usb-bake.hook
}

apply() {
sudo pacman -S --needed winboat freerdp socat usbutils libnotify
sudo install -Dm755 $R/winboat-usb /usr/local/bin/winboat-usb
sudo visudo -cf $R/sudoers && install -Dm440 $R/sudoers /etc/sudoers.d/winboat-usb
sudo install -Dm755 $R/winboat-usb-bake /usr/local/bin/winboat-usb-bake
sudo rm -f /etc/pacman.d/hooks/90-winboat-usb-id.hook
sudo install -Dm644 $R/90-winboat-usb-bake.hook /etc/pacman.d/hooks/90-winboat-usb-bake.hook
sudo /usr/local/bin/winboat-usb-bake
}
