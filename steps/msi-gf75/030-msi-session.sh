# title: msi-session: headset switching, call mode, weekly update reminder
# section: 7. Background service and weekly updates
# after: Quit Discord from its tray icon and reopen it.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs jq kdialog libnotify noise-suppression-for-voice || return 1
  same_as "$(F msi-session)" ~/.local/bin/msi-session || return
  same_as "$(F msi-session.service)" ~/.config/systemd/user/msi-session.service || return
  need_user_on msi-session.service
}

apply() {
sudo pacman -S --needed jq kdialog libnotify noise-suppression-for-voice
install -Dm755 $R/msi-session ~/.local/bin/msi-session
install -Dm644 $R/msi-session.service ~/.config/systemd/user/msi-session.service
systemctl --user daemon-reload
systemctl --user enable --now msi-session.service
}
