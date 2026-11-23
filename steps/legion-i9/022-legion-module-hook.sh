# title: Legion module reloads itself after a driver update
# section: If the Legion module stops being loaded
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_files /etc/pacman.d/hooks/90-legion-reload.hook
}

apply() {
sudo install -Dm644 $R/90-legion-reload.hook /etc/pacman.d/hooks/90-legion-reload.hook
}
