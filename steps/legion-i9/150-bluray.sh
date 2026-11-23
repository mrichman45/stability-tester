# title: Blu-ray: MakeMKV and VLC
# section: 15. Blu-ray: MakeMKV and VLC
# default: off
# after: Log out and back in. In VLC set the Blu-ray region to A (Tools > Preferences > All > Input/Codecs > Access modules > Blu-ray).
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs vlc-plugins-all jre17-openjdk || return 1
  pacman -Q makemkv >/dev/null 2>&1 || { echo "MakeMKV isn't installed"; return 1; }
  need_files /etc/modules-load.d/sg.conf ~/.config/environment.d/makemkv-bluray.conf
}

apply() {
sudo pacman -S --needed vlc-plugins-all jre17-openjdk
@aur makemkv
sudo modprobe sg
sudo echo sg > /etc/modules-load.d/sg.conf
mkdir -p ~/.config/environment.d
printf 'LIBAACS_PATH=libmmbd\nLIBBDPLUS_PATH=libmmbd\n' > ~/.config/environment.d/makemkv-bluray.conf
}
