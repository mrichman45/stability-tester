#!/usr/bin/env bash
# Switch the boot splash (Plymouth) to Nyarch's, safely with Secure Boot.
# Install the theme package first:  makepkg -si   (in this folder)
#
#   nyarch-plymouth.sh preview   show what would change; touches nothing
#   nyarch-plymouth.sh apply     switch to Nyarch's splash (asks first), rebuild, verify
#   nyarch-plymouth.sh undo      switch back to the splash you had before
#
# If the laptop ever won't boot after this: turn Secure Boot off in the BIOS (F2), boot,
# run "nyarch-plymouth.sh undo", then turn Secure Boot back on.
set -euo pipefail

THEME=nyarch-logo
THEMES=/usr/share/plymouth/themes
PLYCONF=/etc/plymouth/plymouthd.conf
STATE=/var/lib/nyarch-plymouth
BOOT=/boot

say()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

usage() { sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
[ $# -eq 1 ] || usage
MODE=$1
case $MODE in preview|apply|undo) ;; *) usage ;; esac

# One password prompt for the whole run.
if [ "$EUID" -ne 0 ]; then exec sudo "$0" "$@"; fi

for c in plymouth-set-default-theme limine-update lsinitcpio comm; do
  command -v "$c" >/dev/null || die "$c is missing; nothing was changed."
done

ENROLL=no
grep -qs '^ENABLE_ENROLL_LIMINE_CONFIG=yes' /etc/default/limine && ENROLL=yes
SECURE=no
command -v sbctl >/dev/null && sbctl status 2>/dev/null | grep -qi 'secure boot:.*enabled' && SECURE=yes
if [ "$ENROLL" = yes ]; then command -v limine-enroll-config >/dev/null || die "limine-enroll-config is missing; nothing was changed."; fi

# Same rebuild as the boot menu script: new initramfs, new hashes, re-enroll, re-sign.
refresh() {
  limine-update
  if [ "$ENROLL" = yes ]; then
    limine-enroll-config
    limine-update
  fi
}

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

# Initramfs images under /boot. Snapshot entries keep older copies there too, so the checks
# below only look at images rebuilt during this run (newer than $STAMP).
initramfs_files() { find "$BOOT" -type f -name 'initramfs*' ! -name '*fallback*' "$@" 2>/dev/null | sort; }
STAMP=$(mktemp); trap 'rm -f "$STAMP"' EXIT
mark() { touch "$STAMP"; sleep 1; }

# True if every image rebuilt since mark() carries the given theme, and there is at least one.
theme_in_initramfs() {
  local t=$1 f n=0
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    n=$((n + 1))
    lsinitcpio "$f" 2>/dev/null | grep -q "usr/share/plymouth/themes/$t/" || { warn "$f doesn't contain the $t splash."; return 1; }
  done < <(initramfs_files -newer "$STAMP")
  [ "$n" -gt 0 ] || { warn "No initramfs under $BOOT was rebuilt."; return 1; }
}

# The plymouth hook must be in the initramfs, and "splash" on the kernel line, for any splash to show.
hook_present() {
  # A missing drop-in folder makes the first grep fail; with pipefail that would read as "no hook".
  { grep -hsE '^\s*HOOKS=' /etc/mkinitcpio.conf /etc/mkinitcpio.conf.d/*.conf || true; } | grep -w plymouth >/dev/null
}
splash_on() {
  grep -qw splash /proc/cmdline || grep -qsE '^KERNEL_CMDLINE.*\bsplash\b' /etc/default/limine
}

CURRENT=$(plymouth-set-default-theme 2>/dev/null || true)
[ -n "$CURRENT" ] || die "Couldn't read the current splash theme; nothing was changed."

# ------------------------------------------------------------------------- undo
if [ "$MODE" = undo ]; then
  if [ ! -s "$STATE/previous-theme" ] && [ "$CURRENT" != "$THEME" ]; then
    say "Nyarch's splash isn't on (the splash is $CURRENT); nothing to undo."; exit 0
  fi
  [ -s "$STATE/previous-theme" ] || die "No saved previous theme in $STATE; nothing was changed. List themes with: plymouth-set-default-theme -l"
  PREV=$(cat "$STATE/previous-theme")
  [ -f "$THEMES/$PREV/$PREV.plymouth" ] || die "The previous theme ($PREV) isn't installed any more; nothing was changed."
  if [ "$CURRENT" = "$PREV" ]; then say "The splash is already $PREV; nothing to undo."; exit 0; fi
  say "Switching the splash back to $PREV and rebuilding"
  mark
  plymouth-set-default-theme "$PREV"
  refresh
  theme_in_initramfs "$PREV" || die "The rebuilt initramfs doesn't contain $PREV. Don't reboot; send the output above."
  if signed_ok; then say "Undone. The splash is $PREV again."; rm -f "$STATE/previous-theme"
  else warn "sbctl verify isn't clean. Don't reboot yet; run: sudo limine-update && sudo sbctl verify"; exit 1; fi
  exit 0
fi

# ------------------------------------------------------------------------- checks
[ -f "$THEMES/$THEME/$THEME.plymouth" ] || die "Nyarch's splash isn't installed. In this folder run: makepkg -si   Nothing was changed."
HOOK=no; hook_present && HOOK=yes
SPLASH=no; splash_on && SPLASH=yes
H=$(cat /sys/class/drm/card*-eDP-*/modes 2>/dev/null | head -n1 | cut -dx -f2 | tr -dc 0-9 || true)
TIER="?"
if [[ "$H" =~ ^[0-9]+$ ]]; then
  if [ "$H" -lt 900 ]; then TIER=720p; elif [ "$H" -lt 1260 ]; then TIER=1080p
  elif [ "$H" -lt 1800 ]; then TIER=1440p; else TIER=4k; fi
fi

report() {
  echo "Current splash:     $CURRENT"
  echo "New splash:         $THEME (its ${TIER} pictures, picked from your screen height)"
  echo "plymouth hook:      $HOOK"
  echo "'splash' on boot:   $SPLASH"
  echo "Secure Boot: $SECURE   config enrollment: $ENROLL"
  echo "Initramfs images on $BOOT (the ones limine-update builds get rebuilt):"; initramfs_files | sed 's/^/  /'
}

if [ "$MODE" = preview ]; then
  say "Nothing has been changed."
  report
  [ "$HOOK" = yes ]   || warn "Without the plymouth hook no splash shows; this script doesn't add it."
  [ "$SPLASH" = yes ] || warn "Without 'splash' on the kernel line no splash shows; this script doesn't add it."
  [ "$CURRENT" != "$THEME" ] || say "Nyarch's splash is already the current one."
  exit 0
fi

# ------------------------------------------------------------------------- apply
[ "$CURRENT" != "$THEME" ] || { say "Nyarch's splash is already the current one; nothing to do."; exit 0; }
[ "$HOOK" = yes ] || die "The plymouth hook isn't in mkinitcpio's HOOKS, so no splash would show. Nothing was changed."
[ "$SPLASH" = yes ] || warn "'splash' isn't on the kernel line, so the splash won't show until it is. Carrying on."

report
echo
echo "If the laptop won't boot afterwards: turn Secure Boot off in the BIOS (F2), boot, run '$0 undo'."
read -r -p "Switch the boot splash to Nyarch's? Type yes: " ok
[ "$ok" = yes ] || die "Cancelled; nothing was changed."

mkdir -p "$STATE"; chmod 700 "$STATE"
printf '%s\n' "$CURRENT" > "$STATE/previous-theme"
[ -f "$PLYCONF" ] && cp -a "$PLYCONF" "$STATE/plymouthd.conf.$(date +%Y%m%d-%H%M%S)"
say "Saved your current splash ($CURRENT) for undo"

rollback() {
  warn "$1 Switching back to $CURRENT."
  mark
  plymouth-set-default-theme "$CURRENT" || true
  refresh || true
  if theme_in_initramfs "$CURRENT" && signed_ok; then warn "Rolled back; the splash is $CURRENT again."; rm -f "$STATE/previous-theme"
  else warn "Rollback didn't verify. Don't reboot; run: sudo limine-update && sudo sbctl verify, and send the output."; fi
  exit 1
}

mark
plymouth-set-default-theme "$THEME" || rollback "Couldn't set the theme."
say "Rebuilding the initramfs and re-enrolling Limine's config"
refresh || rollback "limine-update or limine-enroll-config failed."
[ "$(plymouth-set-default-theme)" = "$THEME" ] || rollback "The theme setting didn't stick."
theme_in_initramfs "$THEME" || rollback "The new initramfs doesn't contain the splash."
signed_ok || rollback "sbctl verify isn't clean after the change."
say "Done. Reboot to see it. To go back: $0 undo"
