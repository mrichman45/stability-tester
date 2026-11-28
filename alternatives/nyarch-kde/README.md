# Nyarch's look on KDE Plasma

Two separate pieces; use either or both. Neither is part of Checkup.

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

## Credits

Based on [Nyarch Linux](https://github.com/NyarchLinux/NyarchLinux) and its
[Customize app](https://github.com/NyarchLinux/NyarchCustomize) (GPL-3.0); the accent colours are
Nyarch's. The boot art is by RavioliMavioli, as credited by Nyarch Linux. Colours come from
[KDE Material You Colors](https://github.com/luisbocanegra/kde-material-you-colors).
