# title: Run apps on the GTX 1650 (switcheroo-control, prime-run)
# section: Set up switcheroo-control ("Run using dedicated graphics card")
# default: on
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs switcheroo-control nvidia-prime vulkan-intel lib32-vulkan-intel || return 1
  need_on switcheroo-control || return 1
  return 0
}

apply() {
sudo pacman -S --needed switcheroo-control nvidia-prime vulkan-intel lib32-vulkan-intel
sudo systemctl enable --now switcheroo-control
}
