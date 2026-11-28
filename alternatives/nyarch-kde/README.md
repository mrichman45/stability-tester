# Nyarch's look on KDE Plasma

Three separate pieces; use any of them. Neither is part of Checkup.

## Nyarch Customize for KDE (`customize/`)

A KDE version of Nyarch Linux's Customize app (theirs is for GNOME), with four pages:

| Page | What it does |
|---|---|
| Layouts | Five Nyarch-style panel layouts: bottom panel; top panel with menu; top panel with menu and dock; top panel with dock; top panel with left dock. Your current panels are backed up before every change, and **Restore** puts any backup back. |
| Effects | Blur, wobbly windows, magic lamp (turns off "squash", which does the same job) and desktop cube. Changes apply at once. |
| Colours | Turns wallpaper-based colours (KDE Material You Colors) on or off, picks one of Nyarch's 13 accent colours, or goes back to following the wallpaper. |
| Desktop | Desktop icons on or off. Plasma's panels restart for a moment; the layout is backed up first. |

Install (from this folder):

```bash
paru -S --needed kde-material-you-colors kdeplasma-addons   # colours, and the cube effect
cd alternatives/nyarch-kde/customize
makepkg -si
```

Then open **Nyarch Customize** from the app menu. It only changes things inside a Plasma session.
Layout backups are in `~/.local/share/nyarch-customize-kde/backups/`.

To remove it: `sudo pacman -R nyarch-customize-kde`. Your panels stay as they are; restore a backup
first if you want your old ones.

Tests: `python -m unittest discover -s tests` (in `customize/`).

## Nyarch boot menu for Limine (`limine/`)

Puts Nyarch's GRUB art (Acchan, by RavioliMavioli) and Nyarch's blues and pinks on the Limine boot
menu, safely with Secure Boot on. The art isn't stored here: the script downloads it from Nyarch
Linux's GitHub, pinned to one version and checked against its SHA-256, then crops it to your screen.

```bash
cd alternatives/nyarch-kde/limine
./nyarch-limine.sh preview   # shows exactly what would change; touches nothing
./nyarch-limine.sh apply     # asks before changing anything
./nyarch-limine.sh undo      # your previous look back
```

What `apply` does, in order, stopping at the first problem:

1. Downloads and checks the art, crops it to the built-in screen's size, and shows you the change.
2. Asks you to type `yes`.
3. Backs up `/boot/limine.conf` to `/var/lib/nyarch-limine-theme/`.
4. Copies the picture to `/boot` and adds a marked block of settings above the boot entries. The
   old wallpaper and colour lines stay in the file, commented out, so undo can restore them exactly.
5. Runs `limine-update`, then `limine-enroll-config` and `limine-update` again, so the config hash
   is re-enrolled and Limine is signed again (the same order as Checkup's Limine step).
6. Checks the settings survived and that `sbctl verify` reports no newly unsigned files. If either
   fails, it puts the old look back by itself and tells you.

Undo removes only the block and the picture; your boot entries are never replaced with an old copy.

**If the laptop ever won't boot after this:** turn Secure Boot off in the BIOS (F2 at the Legion
logo), boot, run `./nyarch-limine.sh undo`, then turn Secure Boot back on.

Tests: `python3 -m unittest test_limine_theme` (in `limine/`).

## Nyarch boot splash (`plymouth/`)

Nyarch's Plymouth splash (the screen after the boot menu): its logo cycles through faces while
the laptop starts, with a paw-print password box. It picks pictures to fit your screen. It needs
the `plymouth` hook in mkinitcpio and `splash` on the kernel line, which CachyOS already has; the
script checks both and changes neither.

```bash
cd alternatives/nyarch-kde/plymouth
makepkg -si                    # installs the theme; files pinned to one Nyarch commit by SHA-256
./nyarch-plymouth.sh preview   # shows your current splash and what would change; touches nothing
./nyarch-plymouth.sh apply     # asks first
./nyarch-plymouth.sh undo      # back to the splash you had
```

`apply` saves your current splash's name, switches to Nyarch's, runs `limine-update` (new
initramfs, re-enrolled config, re-signed Limine, as for the boot menu), then checks every rebuilt
initramfs contains the splash and nothing became unsigned. If not, it switches back by itself.

Same recovery as the boot menu: if it won't boot, Secure Boot off (F2), boot,
`./nyarch-plymouth.sh undo`, Secure Boot on. To remove the theme package afterwards, undo first,
then `sudo pacman -R plymouth-theme-nyarch-logo`.

## Credits

Based on [Nyarch Linux](https://github.com/NyarchLinux/NyarchLinux) and its
[Customize app](https://github.com/NyarchLinux/NyarchCustomize) (GPL-3.0); the accent colours are
Nyarch's. The boot art is by RavioliMavioli and the splash adaptation by Cloveian, as credited by Nyarch Linux. Colours come from
[KDE Material You Colors](https://github.com/luisbocanegra/kde-material-you-colors).
