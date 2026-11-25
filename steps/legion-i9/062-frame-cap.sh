# title: Games capped at 60 FPS (Shift+F1: 144, then no cap)
# section: Frame rate cap
# after: Log out and back in so MangoHud starts with every game.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

# Any fps_limit counts as done, so a cap you change yourself (say to 144) is kept.
check() {
  grep -qs '^MANGOHUD=1' ~/.config/environment.d/*.conf || { echo "MangoHud doesn't start with every game, so no cap applies"; return 1; }
  grep -qs '^fps_limit=' ~/.config/MangoHud/MangoHud.conf || { echo "games aren't capped (no fps_limit in MangoHud.conf)"; return 1; }
}

apply() {
mkdir -p ~/.config/environment.d ~/.config/MangoHud
grep -qs '^MANGOHUD=1' ~/.config/environment.d/gaming.conf || echo 'MANGOHUD=1' >> ~/.config/environment.d/gaming.conf
grep -qs '^fps_limit=' ~/.config/MangoHud/MangoHud.conf || echo 'fps_limit=60,144,0' >> ~/.config/MangoHud/MangoHud.conf
}
