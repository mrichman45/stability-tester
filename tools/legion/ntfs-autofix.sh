#!/usr/bin/env bash
# ntfs-autofix.sh — check the NTFS data drive for errors and repair it before it mounts.
# Written for CachyOS on the Legion Pro 7: nvme1n1p1 → /mnt/ntfsdrive, mounted by /etc/fstab.
#
# Usage:
#   sudo ./ntfs-autofix.sh              check + repair now, then remount from fstab
#   sudo ./ntfs-autofix.sh --check      check only, change nothing (exit 2 = problems found)
#   sudo ./ntfs-autofix.sh --install    install as a boot service that runs before /mnt/ntfsdrive mounts
#   sudo ./ntfs-autofix.sh --uninstall  remove the boot service
#   (--boot is what the service runs: check + repair only; systemd mounts it from fstab right after)
#
# Log: /var/log/ntfs-autofix.log

set -uo pipefail

# ---------- settings ----------
UUID="__NTFS_UUID__"          # from: lsblk -f /dev/nvme1n1
DEVICE="/dev/disk/by-uuid/${UUID}"
MOUNTPOINT="/mnt/ntfsdrive"       # must match the /etc/fstab line
CLEAR_HIBERNATION="yes"           # yes = if Windows left the drive hibernated, discard that session so it can mount
LOGFILE="/var/log/ntfs-autofix.log"
# ------------------------------

SERVICE_NAME="ntfs-autofix"
INSTALL_PATH="/usr/local/sbin/ntfs-autofix.sh"
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
MODE="${1:-}"

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg"
    echo "$msg" >> "$LOGFILE" 2>/dev/null || true
}
die() { log "ERROR: $*"; exit 1; }

[[ $EUID -eq 0 ]] || { echo "Run this with sudo."; exit 1; }

install_service() {
    command -v ntfsfix >/dev/null || die "ntfsfix missing: sudo pacman -S --needed ntfsprogs"
    grep -qE "^[^#]*[[:space:]]${MOUNTPOINT}[[:space:]]" /etc/fstab \
        || die "No /etc/fstab line for ${MOUNTPOINT}. Add it first (see the guide)."
    install -m 755 "$(readlink -f "$0")" "$INSTALL_PATH"
    local mount_unit dev_unit
    mount_unit="$(systemd-escape -p --suffix=mount "$MOUNTPOINT")"
    dev_unit="$(systemd-escape -p --suffix=device "$DEVICE")"
    cat > "$UNIT_PATH" <<EOF
[Unit]
Description=Check and repair NTFS drive ${UUID} before it mounts at ${MOUNTPOINT}
DefaultDependencies=no
After=${dev_unit} systemd-remount-fs.service
Before=${mount_unit}

[Service]
Type=oneshot
ExecStart=${INSTALL_PATH} --boot
RemainAfterExit=yes
TimeoutStartSec=5min

[Install]
WantedBy=${mount_unit}
EOF
    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}.service"
    echo "Installed. It now runs at every boot, just before ${MOUNTPOINT} mounts."
    echo "Check:  systemctl is-enabled ${SERVICE_NAME}   |   Log:  tail -n 20 ${LOGFILE}"
    exit 0
}

uninstall_service() {
    systemctl disable --now "${SERVICE_NAME}.service" 2>/dev/null || true
    rm -f "$UNIT_PATH" "$INSTALL_PATH"
    systemctl daemon-reload
    echo "Removed the boot service. /etc/fstab still mounts ${MOUNTPOINT} as before."
    exit 0
}

case "$MODE" in
    --install)   install_service ;;
    --uninstall) uninstall_service ;;
    ""|--check|--boot) ;;
    *) echo "Unknown option: $MODE"; exit 1 ;;
esac

command -v ntfsfix >/dev/null || die "ntfsfix missing: sudo pacman -S --needed ntfsprogs"

# The drive may take a moment to appear at boot.
for _ in $(seq 1 20); do [[ -b "$DEVICE" ]] && break; sleep 0.5; done
[[ -b "$DEVICE" ]] || { log "Drive ${UUID} not found; skipping."; exit 0; }

fstype="$(blkid -o value -s TYPE "$DEVICE" 2>/dev/null)"
case "$fstype" in
    ntfs) ;;
    BitLocker) die "Drive is BitLocker-encrypted; unlock it first." ;;
    *) die "Drive is '${fstype:-unknown}', not NTFS." ;;
esac

log "=== ${MODE:-manual} run on $(readlink -f "$DEVICE") ==="

# Drive health: a failing drive needs replacing, not repairing.
if command -v smartctl >/dev/null; then
    parent="/dev/$(lsblk -no PKNAME "$(readlink -f "$DEVICE")" | head -n1)"
    if smartctl -H "$parent" 2>/dev/null | grep -qE 'PASSED|OK'; then
        log "Drive health ($parent): OK"
    else
        log "WARNING: health check for $parent did not pass. Back up your data."
    fi
fi

# Must be unmounted to check or repair.
if findmnt -rn -S "$DEVICE" >/dev/null; then
    [[ "$MODE" == "--check" ]] && log "Note: checking while mounted; results may be incomplete."
    if [[ "$MODE" != "--check" ]]; then
        log "Unmounting ${MOUNTPOINT} ..."
        umount "$DEVICE" 2>>"$LOGFILE" || die "Can't unmount ${MOUNTPOINT}: something is using it (close files, cd out of it)."
    fi
fi

check_clean() {
    local out rc
    out="$(ntfsfix -n "$DEVICE" 2>&1)"; rc=$?
    echo "$out" >> "$LOGFILE" 2>/dev/null || true
    [[ $rc -eq 0 ]] && ! grep -qiE 'FAILED|corrupt|inconsistent|dirty|hibernat|unclean|error' <<<"$out"
}

clear_hibernation() {
    # ntfs-3g can delete the hibernation file during a mount; ntfs3 can't.
    [[ "$CLEAR_HIBERNATION" == "yes" ]] && command -v ntfs-3g >/dev/null || return 1
    local tmp=/run/ntfs-autofix-mnt
    mkdir -p "$tmp"
    if mount -t ntfs-3g -o remove_hiberfile "$DEVICE" "$tmp" 2>>"$LOGFILE"; then
        umount "$tmp"; rmdir "$tmp"
        log "Cleared Windows hibernation state."
        return 0
    fi
    rmdir "$tmp" 2>/dev/null
    return 1
}

repair() {
    log "Repairing ..."
    if ntfsfix -d "$DEVICE" >>"$LOGFILE" 2>&1; then
        log "Repair completed."; return 0
    fi
    if clear_hibernation && ntfsfix -d "$DEVICE" >>"$LOGFILE" 2>&1; then
        log "Repair completed after clearing hibernation."; return 0
    fi
    log "ntfsfix couldn't fully repair it. Run 'chkdsk /f' from Windows."
    return 1
}

if check_clean; then
    log "No errors found."
else
    log "Problems found."
    [[ "$MODE" == "--check" ]] && { log "Check only: nothing changed."; exit 2; }
    repair
fi

[[ "$MODE" == "--check" ]] && exit 0

if [[ "$MODE" == "--boot" ]]; then
    log "Done; systemd mounts ${MOUNTPOINT} from fstab next."
    exit 0
fi

# Manual run: remount with the fstab options.
if mount "$MOUNTPOINT" 2>>"$LOGFILE"; then
    log "Mounted ${MOUNTPOINT}."
    probe="${MOUNTPOINT}/.ntfs-autofix-test"
    if touch "$probe" 2>/dev/null && rm -f "$probe"; then
        log "Write test passed: read-write."
    else
        log "WARNING: mounted but not writable."
    fi
else
    die "Couldn't mount ${MOUNTPOINT}. See ${LOGFILE} and 'sudo dmesg | tail'."
fi
log "=== Done ==="