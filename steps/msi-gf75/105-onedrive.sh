# title: OneDrive as a folder (rclone)
# section: OneDrive (if you use it)
# default: off
# manual: Run rclone config (new remote named onedrive), then add a login script with: rclone mount onedrive: ~/OneDrive --vfs-cache-mode full --daemon
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs rclone || return 1
  return 0
}

apply() {
sudo pacman -S --needed rclone
}
