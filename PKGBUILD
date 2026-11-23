# Build and install from this folder with: makepkg -si
pkgname=checkup
pkgver=0.2.0
pkgrel=1
pkgdesc="One-button laptop setup from our guide, profile checks, and hardware stability tests"
arch=('any')
url="https://github.com/mrichman45/stability-tester"
license=('GPL-2.0-or-later')
depends=('python' 'pyside6' 'polkit' 'pciutils' 'util-linux' 'pacman-contrib' 'git'
         'stress-ng' 'memtester' 'smartmontools' 'glmark2' 'v4l-utils' 'mesa-utils')
optdepends=('nvidia-utils: NVIDIA temperature, clock and power readings'
            'ffmpeg: VLC playback test'
            'alacritty: terminal window for fixes (any terminal works)')
source=()

package() {
  cd "$startdir"
  install -d "$pkgdir/usr/lib/checkup/checkup"
  install -m644 checkup/*.py "$pkgdir/usr/lib/checkup/checkup/"
  install -m755 checkup-root "$pkgdir/usr/lib/checkup/checkup-root"
  install -Dm755 bin/checkup "$pkgdir/usr/bin/checkup"
  install -Dm755 bin/checkup-cli "$pkgdir/usr/bin/checkup-cli"
  install -Dm644 data/checkup.desktop "$pkgdir/usr/share/applications/checkup.desktop"
  install -Dm644 data/org.stabilitytester.checkup.policy "$pkgdir/usr/share/polkit-1/actions/org.stabilitytester.checkup.policy"
  install -d "$pkgdir/usr/share/checkup/guides"
  install -m644 guides/*.md "$pkgdir/usr/share/checkup/guides/"
  install -Dm644 machines.json "$pkgdir/usr/share/checkup/machines.json"
  install -Dm755 tools/er-save-manager-update "$pkgdir/usr/share/checkup/tools/er-save-manager-update"
  install -d "$pkgdir/usr/share/checkup/tools/legion"
  cp -a tools/legion/. "$pkgdir/usr/share/checkup/tools/legion/"
  install -d "$pkgdir/usr/share/checkup/steps"
  cp -a steps/. "$pkgdir/usr/share/checkup/steps/"
}
