# title: Hardware video on the Intel GPU (and Spectacle recording)
# section: 10. Intel graphics and video
# default: on
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs intel-media-driver libva-utils intel-gpu-tools || return 1
  return 0
}

apply() {
sudo pacman -S --needed intel-media-driver libva-utils intel-gpu-tools
}
