# title: The LTS kernel starts by default
# section: Kernel and stability settings
# check-as: root
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  grep -q '^BOOT_ORDER="\*lts' /etc/default/limine || { echo "Limine puts the newest kernel first"; return 1; }
  ! grep -q '^remember_last_entry: yes' /boot/limine.conf || { echo "Limine starts whichever entry was picked last"; return 1; }
}

apply() {
sudo sed -i 's/^BOOT_ORDER=.*/BOOT_ORDER="*lts, *, *fallback, Snapshots"/' /etc/default/limine
sudo cp /boot/limine.conf /boot/limine.conf.bak
sudo sed -i 's/^remember_last_entry: yes/remember_last_entry: no/' /boot/limine.conf
sudo limine-update
}
