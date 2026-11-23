# title: VLC with all plugins
# section: VLC with all plugins
# default: on
# manual: For lighter playback: VLC > Tools > Preferences > Input / Codecs > Hardware-accelerated decoding > VA-API.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs vlc vlc-plugins-all || return 1
  return 0
}

apply() {
sudo pacman -S --needed vlc vlc-plugins-all
}
