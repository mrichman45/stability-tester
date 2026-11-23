# title: Control this laptop from another computer over SSH
# section: Optional: control this laptop from another computer over SSH
# default: off
# manual: Reserve the laptop's address in your router so it doesn't change. From the other computer: ssh-copy-id <you>@<laptop address>.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs openssh || return 1
  need_on sshd || return 1
  return 0
}

apply() {
sudo pacman -S --needed openssh
sudo systemctl enable --now sshd
sudo ufw allow ssh
}
