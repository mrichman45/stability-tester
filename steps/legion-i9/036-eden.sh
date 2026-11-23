# title: Eden (Switch emulator) in the menu, on the GPU rules
# section: Eden (Switch emulator)
# when: [ -e ~/Applications/Eden.AppImage ]
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs fuse2 || return 1
  need_files ~/.local/share/applications/eden.desktop
}

apply() {
sudo pacman -S --needed fuse2
chmod +x ~/Applications/Eden.AppImage
printf '[Desktop Entry]\nType=Application\nName=Eden\nComment=Nintendo Switch emulator\nExec=%s/.local/bin/game-gpu %s/Applications/Eden.AppImage %%f\nIcon=applications-games\nTerminal=false\nCategories=Game;Emulator;\n' $HOME $HOME > ~/.local/share/applications/eden.desktop
kbuildsycoca6 >/dev/null 2>&1; true
}
