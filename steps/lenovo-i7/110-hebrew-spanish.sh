# title: Hebrew and Spanish typing and spell check
# section: Hebrew and Spanish typing
# after: Log out and back in; switch layouts with Meta+Alt+K.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs noto-fonts hunspell-he hunspell-es_any || return 1
  l=$(kreadconfig6 --file kxkbrc --group Layout --key LayoutList 2>/dev/null)
  case ",$l," in *,il,*) ;; *) echo "the Hebrew keyboard layout isn't added"; return 1;; esac
  case ",$l," in *,es,*|*,latam,*) ;; *) echo "the Spanish keyboard layout isn't added"; return 1;; esac
}

apply() {
sudo pacman -S --needed noto-fonts hunspell-he hunspell-es_any
kwriteconfig6 --file kxkbrc --group Layout --key Use true
l=$(kreadconfig6 --file kxkbrc --group Layout --key LayoutList); l=${l:-us}; for x in il es; do case ",$l," in *,$x,*) ;; *) l="$l,$x";; esac; done; kwriteconfig6 --file kxkbrc --group Layout --key LayoutList "$l"
v=$(kreadconfig6 --file kxkbrc --group Layout --key VariantList); n=$(kreadconfig6 --file kxkbrc --group Layout --key LayoutList | tr -cd , | wc -c); while [ "$(printf %s "$v" | tr -cd , | wc -c)" -lt "$n" ]; do v="$v,"; done; kwriteconfig6 --file kxkbrc --group Layout --key VariantList "$v"
}
