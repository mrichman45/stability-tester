# title: Battery stops charging early (lasts for years)
# section: Stop charging at 60%
# when: ls /sys/bus/platform/drivers/ideapad_acpi/*/conservation_mode
# manual: Before a trip, turn it off the day before: echo 0 | sudo tee /sys/bus/platform/drivers/ideapad_acpi/*/conservation_mode
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  [ "$(cat /sys/bus/platform/drivers/ideapad_acpi/*/conservation_mode 2>/dev/null | head -n1)" = 1 ] || { echo "the battery charges to 100% (conservation mode is off)"; return 1; }
}

apply() {
sudo sh -c 'for f in /sys/bus/platform/drivers/ideapad_acpi/*/conservation_mode; do echo 1 > "$f"; done'
}
