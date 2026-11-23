# title: Windows is in the boot menu
# section: Install step 8. Windows in the boot menu (when reinstalling)
# when: [ -n "$WINDOWS_UUID" ]
# default: manual
# check-as: root
# manual: Run sudo limine-scan and pick Windows Boot Manager.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  grep -qi windows /boot/limine.conf || { echo "the Limine menu has no Windows entry"; return 1; }
}
