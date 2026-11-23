# title: Japanese typing (Fcitx 5 + Mozc)
# section: Japanese typing (Fcitx 5 + Mozc)
# capture: ~/.config/fcitx5/profile
# after: Log out and back in, then Ctrl+Space switches to Mozc.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs fcitx5 fcitx5-configtool fcitx5-gtk fcitx5-qt fcitx5-mozc noto-fonts-cjk || return 1
  grep -q '^XMODIFIERS=@im=fcitx' /etc/environment || { echo "XWayland apps (Steam, games) can't type Japanese"; return 1; }
  [ "$(kreadconfig6 --file kwinrc --group Wayland --key InputMethod 2>/dev/null)" = /usr/share/applications/org.fcitx.Fcitx5.desktop ] || { echo "Plasma doesn't start Fcitx 5"; return 1; }
}

apply() {
sudo pacman -S --needed fcitx5-im fcitx5-mozc noto-fonts-cjk
sudo grep -q '^XMODIFIERS=@im=fcitx' /etc/environment || echo 'XMODIFIERS=@im=fcitx' >> /etc/environment
kwriteconfig6 --file kwinrc --group Wayland --key InputMethod /usr/share/applications/org.fcitx.Fcitx5.desktop
}
# manual: Add Mozc once: System Settings > Input Method > Add Input Method, untick Only Show Current Language, Mozc, Apply.
