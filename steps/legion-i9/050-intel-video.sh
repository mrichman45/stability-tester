# title: Hardware video decoding and recording on the Intel GPU
# section: Hardware video on the Intel GPU
# default: on
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs intel-media-driver libva-utils || return 1
  return 0
}

apply() {
sudo pacman -S --needed intel-media-driver libva-utils
}
