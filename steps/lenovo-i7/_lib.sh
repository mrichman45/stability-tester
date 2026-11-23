# Shared helpers for the Legion guide steps (sourced by each step's test).
# Tests print one line saying what's missing and return non-zero; they never change anything.

need_pkgs() {   # need_pkgs PKG... : all installed?
  local miss=()
  for p in "$@"; do pacman -Q "$p" >/dev/null 2>&1 || miss+=("$p"); done
  [ ${#miss[@]} -eq 0 ] && return 0
  echo "missing packages: ${miss[*]}"; return 1
}
need_on() {     # need_on UNIT... : enabled at boot?
  local off=()
  for u in "$@"; do systemctl is-enabled -q "$u" 2>/dev/null || off+=("$u"); done
  [ ${#off[@]} -eq 0 ] && return 0
  echo "not switched on: ${off[*]}"; return 1
}
need_off() {    # need_off UNIT... : not enabled at boot?
  local on=()
  for u in "$@"; do systemctl is-enabled -q "$u" 2>/dev/null && on+=("$u"); done
  [ ${#on[@]} -eq 0 ] && return 0
  echo "should be off: ${on[*]}"; return 1
}
need_user_on() {
  local off=()
  for u in "$@"; do systemctl --user is-enabled -q "$u" 2>/dev/null || off+=("$u"); done
  [ ${#off[@]} -eq 0 ] && return 0
  echo "not switched on: ${off[*]}"; return 1
}
need_files() {  # need_files PATH... : all present?
  local miss=()
  for f in "$@"; do [ -e "$f" ] || miss+=("$(basename "$f")"); done
  [ ${#miss[@]} -eq 0 ] && return 0
  echo "missing: ${miss[*]}"; return 1
}
same_as() {     # same_as REPO_FILE LAPTOP_FILE : identical once placeholders are filled in?
                # missing -> 1; edited on this laptop -> 3 (Checkup offers to save your version)
  [ -e "$2" ] || { echo "missing: $(basename "$2")"; return 1; }
  local want
  want=$(sed -e "s|__USER__|$USER|g" -e "s|__HOME__|$HOME|g" -e "s|__NTFS_UUID__|$NTFS_UUID|g" \
             -e "s|__WINDOWS_UUID__|$WINDOWS_UUID|g" -e "s|__LAN_SUBNET__|$LAN_SUBNET|g" "$1")
  [ "$want" = "$(cat "$2")" ] && return 0
  echo "differs:$1|$2"; return 3
}
F() { echo "$STEP_FILES/$1"; }   # a file of this step in the repo
