# title: Printing and scanning
# section: Printing and scanning
# check-as: root
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs cups cups-browsed print-manager system-config-printer avahi nss-mdns sane-airscan skanpage || return 1
  need_on cups.socket cups-browsed avahi-daemon || return 1
  grep -qE '^hosts:.*mdns_minimal' /etc/nsswitch.conf || { echo "network printers can't be found by name (mdns missing in nsswitch.conf)"; return 1; }
  ufw status 2>/dev/null | grep -q '5353/udp' || { echo "the firewall blocks printer discovery (mDNS)"; return 1; }
}

apply() {
sudo pacman -S --needed cups cups-browsed print-manager system-config-printer avahi nss-mdns sane-airscan skanpage
sudo systemctl enable --now cups.socket cups-browsed avahi-daemon
sudo ufw allow 5353/udp comment 'mDNS: find printers'
sudo grep -qE '^hosts:.*mdns_minimal' /etc/nsswitch.conf || sed -i -E 's/^(hosts:.*)\b(resolve)/\1mdns_minimal [NOTFOUND=return] \2/' /etc/nsswitch.conf
}
