# title: Anki starts (software rendering) and plays card audio
# section: Anki
# when: pacman -Q anki || pacman -Q anki-bin || pacman -Q anki-qt5
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  [ "$(cat ~/.local/share/Anki2/gldriver6 2>/dev/null)" = software ] || { echo "Anki crashes at start (needs software rendering)"; return 1; }
  need_pkgs mpv || return 1
  grep -qs '^NoDisplay=true' ~/.local/share/applications/mpv.desktop || { echo "mpv shows up in the app menu"; return 1; }
}

apply() {
mkdir -p ~/.local/share/Anki2
echo software > ~/.local/share/Anki2/gldriver6
sudo pacman -S --needed mpv
mkdir -p ~/.local/share/applications
cp /usr/share/applications/mpv.desktop ~/.local/share/applications/mpv.desktop
sed -i '/^NoDisplay=/d; /^\[Desktop Entry\]/a NoDisplay=true' ~/.local/share/applications/mpv.desktop
}
