# title: PRIME offload tools, Intel Vulkan, nvidia-persistenced off
# section: 3. Graphics: which GPU runs what
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs nvidia-prime switcheroo-control vulkan-intel lib32-vulkan-intel || return 1
  need_off nvidia-persistenced.service
}

apply() {
sudo pacman -S --needed nvidia-prime switcheroo-control vulkan-intel lib32-vulkan-intel
sudo systemctl disable --now nvidia-persistenced.service
}
