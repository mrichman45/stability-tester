# title: Bigger NVIDIA shader cache
# section: 6. Gaming
# after: Restart for the shader cache size to apply.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  grep -qs '^__GL_SHADER_DISK_CACHE_SIZE=' ~/.config/environment.d/*.conf || { echo "NVIDIA's shader cache is at its small default"; return 1; }
}

apply() {
mkdir -p ~/.config/environment.d
grep -qs '^__GL_SHADER_DISK_CACHE_SIZE=' ~/.config/environment.d/gaming.conf || echo '__GL_SHADER_DISK_CACHE_SIZE=12000000000' >> ~/.config/environment.d/gaming.conf
}
