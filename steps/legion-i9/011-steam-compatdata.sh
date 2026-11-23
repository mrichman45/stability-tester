# title: Proton prefixes for the NTFS Steam library live on the Linux drive
# section: Games on the NTFS drive
# when: [ -d /mnt/ntfsdrive/Games/SteamLibrary/steamapps ]
# manual: In Steam: Settings > Storage > Add Drive > /mnt/ntfsdrive/Games/SteamLibrary (once, with Steam closed first for this fix).
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  [ -L /mnt/ntfsdrive/Games/SteamLibrary/steamapps/compatdata ] || { echo "the library's compatdata isn't a link to ~/.steam/compatdata-data (games quit on launch)"; return 1; }
}

apply() {
pgrep -x steam >/dev/null && { echo "Quit Steam first (Steam > Exit), then try again."; exit 1; }; true
mkdir -p ~/.steam/compatdata-data
L=/mnt/ntfsdrive/Games/SteamLibrary/steamapps; [ -d "$L/compatdata" ] && [ ! -L "$L/compatdata" ] && { cp -a "$L/compatdata"/. ~/.steam/compatdata-data/ && rm -rf "$L/compatdata"; }; true
ln -sfn ~/.steam/compatdata-data /mnt/ntfsdrive/Games/SteamLibrary/steamapps/compatdata
}
