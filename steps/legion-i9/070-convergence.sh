# title: The Convergence: Seamless Co-op or Solo picker
# section: Step 7: Choose Seamless Co-op or Solo each launch
# when: [ -d ~/Games/ConvergenceER ]
# default: off
# manual: Add ~/bin/convergence.sh to Steam twice (Add a Non-Steam Game): "Convergence (Co-op)" with launch options %command% coop, "Convergence (Solo)" with %command% solo. Set cooppassword in SeamlessCoop/ersc_settings.ini.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs kdialog || return 1
  same_as "$(F convergence.sh)" ~/bin/convergence.sh
}

apply() {
sudo pacman -S --needed kdialog
install -Dm755 $R/convergence.sh ~/bin/convergence.sh
}
