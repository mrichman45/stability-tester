# title: Every way of starting Steam goes through steam-gpu
# section: intel-run and the Steam menu entry (plumbing for section 3's GPU rules)
# when: [ -e /usr/share/applications/steam.desktop ]
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  grep -qs "^Exec=$HOME/.local/bin/steam-gpu" ~/.local/share/applications/steam.desktop || { echo "Steam's menu entry starts Steam without the GPU rules"; return 1; }
}

apply() {
mkdir -p ~/.local/share/applications
cp /usr/share/applications/steam.desktop ~/.local/share/applications/steam.desktop
sed -i -E "s|^Exec=(/usr/bin/)?steam(-runtime)?|Exec=$HOME/.local/bin/steam-gpu|" ~/.local/share/applications/steam.desktop
kbuildsycoca6 >/dev/null 2>&1; true
}
