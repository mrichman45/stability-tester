#!/usr/bin/env bash
# Nyarch look for the Limine boot menu (Acchan art + Nyarch colours), safe with Secure Boot.
#
#   nyarch-limine.sh preview   show what would change; touches nothing
#   nyarch-limine.sh apply     back up, change, re-enroll, re-sign, verify (asks first)
#   nyarch-limine.sh undo      put your previous boot menu look back
#
# If the laptop ever won't boot after this: turn Secure Boot off in the BIOS (F2), boot,
# run "nyarch-limine.sh undo", then turn Secure Boot back on.
set -euo pipefail

HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
EDIT=(python3 -I "$HERE/limine_theme.py")
CONF=/boot/limine.conf
IMG_NAME=nyarch-acchan.png
STATE=/var/lib/nyarch-limine-theme
# The art (by RavioliMavioli, from Nyarch Linux), pinned to one commit and checked by SHA-256.
# It's downloaded when you run this, never stored in this repo.
ART_URL=https://raw.githubusercontent.com/NyarchLinux/NyarchLinux/5088f5cbd80131176cdb2a669e8cfb7ce580312a/Gnome/etc/skel/.local/share/backgrounds/archlinux.png
ART_SHA256=53f2d290afec4dfeed2c20b25ba85b35131f3cfec1a1682b9517d0aeff5442b5

say()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

usage() { sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
[ $# -eq 1 ] || usage
MODE=$1
case $MODE in preview|apply|undo) ;; *) usage ;; esac

# One password prompt for the whole run.
if [ "$EUID" -ne 0 ]; then exec sudo "$0" "$@"; fi

for c in python3 b2sum sha256sum comm limine-update; do
  command -v "$c" >/dev/null || die "$c is missing; nothing was changed."
done
[ -f "$CONF" ] || die "$CONF not found; this script expects CachyOS's Limine layout. Nothing was changed."
BOOT_DIR=$(dirname "$CONF")

ENROLL=no
grep -qs '^ENABLE_ENROLL_LIMINE_CONFIG=yes' /etc/default/limine && ENROLL=yes
SECURE=no
command -v sbctl >/dev/null && sbctl status 2>/dev/null | grep -qi 'secure boot:.*enabled' && SECURE=yes
if [ "$ENROLL" = yes ]; then command -v limine-enroll-config >/dev/null || die "limine-enroll-config is missing; nothing was changed."; fi

# limine-update rebuilds limine.conf; with enrollment on, the config's hash is written into
# Limine's EFI file and that file is signed again. Same order as Checkup's step 170.
refresh() {
  limine-update
  if [ "$ENROLL" = yes ]; then
    limine-enroll-config
    limine-update
  fi
}

# Files sbctl reports as unsigned. Windows' own boot files can show up here on a dual-boot
# laptop, so only files that weren't already listed before this run count as a problem.
unsigned() { sbctl verify 2>&1 | grep -i 'not signed' | sort || true; }
BASELINE=""
[ "$SECURE" = yes ] && BASELINE=$(unsigned)
signed_ok() {
  [ "$SECURE" = yes ] || return 0
  local new; new=$(comm -13 <(printf '%s\n' "$BASELINE") <(printf '%s\n' "$(unsigned)") | sed '/^$/d')
  [ -z "$new" ] && return 0
  warn "Newly unsigned after the change:"; printf '%s\n' "$new" >&2
  return 1
}

has_theme() { grep -qxF '# <<< nyarch-limine-theme' "$CONF"; }

# ------------------------------------------------------------------------- undo
if [ "$MODE" = undo ]; then
  has_theme || { say "The Nyarch boot theme isn't in $CONF; nothing to undo."; exit 0; }
  mkdir -p "$STATE"; cp -a "$CONF" "$STATE/limine.conf.before-undo.$(date +%Y%m%d-%H%M%S)"
  tmp=$(mktemp); "${EDIT[@]}" strip "$CONF" > "$tmp"
  install -m 600 "$tmp" "$CONF"; rm -f "$tmp"
  refresh
  if has_theme; then die "limine-update put the theme back. Your config backups are in $STATE."; fi
  rm -f "$BOOT_DIR/$IMG_NAME"
  if signed_ok; then say "Undone. Your previous boot menu look is back."
  else warn "sbctl verify isn't clean. Don't reboot yet; run: sudo limine-update && sudo sbctl verify"; exit 1; fi
  exit 0
fi

# ------------------------------------------------------------------------- build the image
WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT
command -v curl >/dev/null || die "curl is missing; nothing was changed."
say "Downloading the Acchan art from Nyarch Linux's GitHub"
curl -fsSL --proto '=https' -o "$WORK/art.png" "$ART_URL" || die "Download failed; nothing was changed."
echo "$ART_SHA256  $WORK/art.png" | sha256sum -c --quiet - || die "The download doesn't match the expected file; nothing was changed."

# Native screen size of the built-in panel, so the art fills it without stretching.
mode=$(cat /sys/class/drm/card*-eDP-*/modes 2>/dev/null | head -n1 || true)
W=${mode%x*}; H=${mode#*x}; H=${H%%[^0-9]*}
STYLE=centered
if [[ "$W" =~ ^[0-9]+$ && "$H" =~ ^[0-9]+$ ]]; then
  # Cover the screen, centre-crop the rest (3840x2160 art onto 2560x1600 trims the sides a little).
  if command -v magick >/dev/null; then
    magick "$WORK/art.png" -resize "${W}x${H}^" -gravity center -extent "${W}x${H}" -alpha off -strip "$WORK/out.png" && STYLE=stretched
  elif command -v ffmpeg >/dev/null; then
    ffmpeg -nostdin -loglevel error -y -i "$WORK/art.png" \
      -vf "scale=${W}:${H}:force_original_aspect_ratio=increase,crop=${W}:${H}" -pix_fmt rgb24 "$WORK/out.png" && STYLE=stretched
  fi
fi
if [ "$STYLE" = centered ]; then
  warn "Couldn't resize the art (no screen size, or neither ImageMagick nor ffmpeg); it will be centred unscaled."
  cp "$WORK/art.png" "$WORK/out.png"
fi
DIGEST=$(b2sum "$WORK/out.png" | cut -d' ' -f1)

"${EDIT[@]}" apply "$CONF" "$IMG_NAME" "$DIGEST" "$STYLE" > "$WORK/new.conf"

if [ "$MODE" = preview ]; then
  say "Changes to $CONF (nothing has been written):"
  diff -u "$CONF" "$WORK/new.conf" || true
  echo; say "Wallpaper: $IMG_NAME, ${W:-?}x${H:-?}, style $STYLE"
  say "Secure Boot: $SECURE   config enrollment: $ENROLL"
  exit 0
fi

# ------------------------------------------------------------------------- apply
need=$(( $(stat -c %s "$WORK/out.png") / 1024 + 1024 ))
free=$(df -Pk "$BOOT_DIR" | awk 'NR==2{print $4}')
[ "$free" -gt "$need" ] || die "Only ${free} KiB free on the boot partition (need ${need}); nothing was changed."

diff -u "$CONF" "$WORK/new.conf" || true
echo
echo "Secure Boot: $SECURE   config enrollment: $ENROLL"
echo "If the laptop won't boot afterwards: turn Secure Boot off in the BIOS (F2), boot, run '$0 undo'."
read -r -p "Apply this to the boot menu? Type yes: " ok
[ "$ok" = yes ] || die "Cancelled; nothing was changed."

mkdir -p "$STATE"; chmod 700 "$STATE"
stamp=$(date +%Y%m%d-%H%M%S)
cp -a "$CONF" "$STATE/limine.conf.$stamp"
say "Backed up $CONF to $STATE/limine.conf.$stamp"

rollback() {
  warn "$1 Putting the old look back."
  tmp=$(mktemp); "${EDIT[@]}" strip "$CONF" > "$tmp" && install -m 600 "$tmp" "$CONF"; rm -f "$tmp"
  refresh || true
  rm -f "$BOOT_DIR/$IMG_NAME"
  if has_theme; then
    warn "The theme is still in $CONF. Don't reboot; restore $STATE/limine.conf.$stamp by hand, then run: sudo limine-update"
  elif signed_ok; then warn "Rolled back; your boot menu is as it was."
  else warn "Rolled back, but sbctl verify isn't clean. Don't reboot yet; run: sudo limine-update && sudo sbctl verify"; fi
  exit 1
}

install -m 644 "$WORK/out.png" "$BOOT_DIR/$IMG_NAME"
[ "$(b2sum "$BOOT_DIR/$IMG_NAME" | cut -d' ' -f1)" = "$DIGEST" ] || rollback "The copied image doesn't match."
install -m 600 "$WORK/new.conf" "$CONF"

say "Rebuilding and re-enrolling Limine's config"
refresh || rollback "limine-update or limine-enroll-config failed."
"${EDIT[@]}" check "$CONF" "$IMG_NAME" "$DIGEST" || rollback "limine-update didn't keep the theme lines."

if signed_ok; then
  say "Done. Reboot to see it. To go back: $0 undo"
else
  rollback "sbctl verify isn't clean after the change."
fi
