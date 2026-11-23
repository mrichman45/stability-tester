# title: Updates with a click in Discover
# section: 16. Updates with Discover
# default: on
# manual: System Settings > Software Update: Update software Manually, Notification frequency Weekly, Apply system updates Immediately.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs discover packagekit-qt6 || return 1
  return 0
}

apply() {
sudo pacman -S --needed discover packagekit-qt6
}
