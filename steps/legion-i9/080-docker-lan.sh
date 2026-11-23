# title: Docker networks stay off your home network's addresses
# section: 8. Docker, and reaching your home network from containers
# when: pacman -Q docker
# check-as: root
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  same_as "$(F daemon.json)" /etc/docker/daemon.json || return
  [ -z "$LAN_SUBNET" ] || ufw status 2>/dev/null | grep -q "$LAN_SUBNET" || { echo "the firewall blocks containers from reaching your network"; return 1; }
}

apply() {
sudo install -Dm644 $R/daemon.json /etc/docker/daemon.json
sudo systemctl restart docker
sudo [ -z "$LAN_SUBNET" ] || ufw route allow from 172.16.0.0/12 to $LAN_SUBNET
sudo ufw reload
}
