# title: The computer has its own name
# section: 2. Installing CachyOS
# default: manual
# manual: The installer leaves it as cachyos-x8664. Pick the name and run: sudo hostnamectl set-hostname <name>
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  case "$(cat /etc/hostname 2>/dev/null)" in cachyos*|"") echo "the computer is still called $(cat /etc/hostname 2>/dev/null)"; return 1;; esac
}
