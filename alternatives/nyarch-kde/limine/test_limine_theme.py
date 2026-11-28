"""Run:  python3 -m unittest test_limine_theme   (from this folder)"""
import unittest

import limine_theme as t

H = "a" * 128
CONF = """timeout: 5
default_entry: 2
interface_branding: CachyOS
interface_branding_colour: 2
wallpaper: boot():/limine-splash.png#""" + "b" * 128 + """
wallpaper_style: centered

/+CachyOS
    comment: CachyOS
    //linux-cachyos-lts
        protocol: efi
        path: boot():/vmlinuz-linux-cachyos-lts#""" + "c" * 128 + """
        cmdline: quiet
/Windows
    protocol: efi
    path: boot():/EFI/Microsoft/Boot/bootmgfw.efi
"""


class Theme(unittest.TestCase):
    def test_undo_gives_back_the_original(self):
        self.assertEqual(t.strip(t.apply(CONF, "nyarch-acchan.png", H, "stretched")), CONF)

    def test_applying_twice_is_the_same_as_once(self):
        once = t.apply(CONF, "nyarch-acchan.png", H, "stretched")
        self.assertEqual(t.apply(once, "nyarch-acchan.png", H, "stretched"), once)

    def test_theme_sits_before_entries_and_old_lines_are_disabled(self):
        out = t.apply(CONF, "nyarch-acchan.png", H, "stretched")
        lines = out.splitlines()
        self.assertLess(lines.index(t.END), lines.index("/+CachyOS"))
        active = [l for l in lines if l.startswith("wallpaper:")]
        self.assertEqual(active, [f"wallpaper: boot():/nyarch-acchan.png#{H}"])
        self.assertIn("interface_branding: CachyOS", lines)   # text kept, only colours change
        self.assertTrue(t.check(out, "nyarch-acchan.png", H))

    def test_entries_are_untouched(self):
        out = t.apply(CONF, "nyarch-acchan.png", H, "stretched")
        self.assertEqual(out[out.index("/+CachyOS"):], CONF[CONF.index("/+CachyOS"):])

    def test_check_notices_lost_or_changed_lines(self):
        out = t.apply(CONF, "nyarch-acchan.png", H, "stretched")
        self.assertFalse(t.check(CONF, "nyarch-acchan.png", H))
        self.assertFalse(t.check(out, "nyarch-acchan.png", "d" * 128))
        self.assertFalse(t.check(out.replace("term_palette: ", "term_palette: 000000;"), "nyarch-acchan.png", H))

    def test_machine_id_comment_stays_next_to_the_entries(self):
        conf = ("timeout: 5\nwallpaper: boot():/limine-splash.png#" + "b" * 128 +
                "\n\ncomment: machine-id=0123456789abcdef0123456789abcdef\n\n/+CachyOS\n    //linux\n")
        out = t.apply(conf, "nyarch-acchan.png", H, "stretched")
        lines = out.splitlines()
        self.assertLess(lines.index(t.END), lines.index("comment: machine-id=0123456789abcdef0123456789abcdef"))
        self.assertTrue(t.check(out, "nyarch-acchan.png", H))
        self.assertEqual(t.strip(out), conf)

    def test_unfinished_block_is_refused(self):
        with self.assertRaises(SystemExit):
            t.strip(CONF + t.BEGIN + "\n")

    def test_bad_input_is_refused(self):
        for name, digest, style in (("../x.png", H, "stretched"), ("a.png", "zz", "stretched"),
                                    ("a.png", H, "fill\nwallpaper: x")):
            with self.assertRaises(SystemExit):
                t.apply(CONF, name, digest, style)

    def test_config_without_entries(self):
        out = t.apply("timeout: 3\n", "nyarch-acchan.png", H, "centered")
        self.assertTrue(t.check(out, "nyarch-acchan.png", H))
        self.assertEqual(t.strip(out), "timeout: 3\n\n")


if __name__ == "__main__":
    unittest.main()
