# title: WinBoat, Docker and FreeRDP
# section: 12. WinBoat: Windows apps
# default: on
# manual: Open WinBoat and follow its setup: 6 GB RAM, 6 threads, 64 GB disk, home folder sharing on. Don't plug in USB sticks while Windows installs.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs winboat docker docker-compose freerdp || return 1
  need_on docker || return 1
  return 0
}

apply() {
sudo pacman -S --needed winboat docker docker-compose freerdp
sudo systemctl enable --now docker
}
