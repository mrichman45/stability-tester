"""Run from the customize folder:  python -m unittest discover -s tests"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nyarch_customize_kde import backend as b  # noqa: E402


class FakeRunner(b.Runner):
    def __init__(self, replies=None, installed=True):
        self.calls, self.spawned = [], []
        self.replies = replies or {}
        self.installed = installed
        self.kconf = {}

    def run(self, args, timeout=30):
        self.calls.append(args)
        if args[0] == "kreadconfig6":
            g, k = args[args.index("--group") + 1], args[args.index("--key") + 1]
            return 0, self.kconf.get((g, k), "")
        return self.replies.get(args[0], (0, ""))

    def which(self, name):
        return "/usr/bin/" + name if self.installed else None

    def spawn(self, args):
        self.spawned.append(args)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = dict(os.environ)
        os.environ.update(HOME=self.tmp.name, XDG_CONFIG_HOME=f"{self.tmp.name}/.config",
                          XDG_DATA_HOME=f"{self.tmp.name}/.local/share", XDG_CURRENT_DESKTOP="KDE")
        b.config_dir().mkdir(parents=True)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.env)
        self.tmp.cleanup()


class OutsidePlasma(Base):
    def test_refuses_without_running_anything(self):
        os.environ["XDG_CURRENT_DESKTOP"] = "Hyprland"
        r = FakeRunner()
        for ok, _ in (b.apply_layout(r, "top-dock"), b.set_effect(r, b.EFFECTS[0], True),
                      b.set_desktop_icons(r, False), b.restore_backup(r, Path(self.tmp.name))):
            self.assertFalse(ok)
        self.assertEqual(r.calls, [])
        self.assertEqual(r.spawned, [])


class Layouts(Base):
    def test_apply_backs_up_current_panels(self):
        (b.config_dir() / b.APPLETS_RC).write_text("original")
        r = FakeRunner()
        ok, _ = b.apply_layout(r, "top-menu-dock")
        self.assertTrue(ok)
        [saved] = b.list_backups()
        self.assertEqual((saved / b.APPLETS_RC).read_text(), "original")
        self.assertIn("org.kde.PlasmaShell.evaluateScript", r.calls[-1])

    def test_plasma_refusal_is_reported_as_failure(self):
        ok, msg = b.apply_layout(FakeRunner({"qdbus6": (1, "no such service")}), "top-dock")
        self.assertFalse(ok)
        self.assertIn("no such service", msg)

    def test_restore_puts_files_back(self):
        rc = b.config_dir() / b.APPLETS_RC
        rc.write_text("before")
        b.apply_layout(FakeRunner(), "bottom-panel")
        rc.write_text("after")
        ok, _ = b.restore_backup(FakeRunner(), b.list_backups()[0])
        self.assertTrue(ok)
        self.assertEqual(rc.read_text(), "before")

    def test_two_backups_in_one_second_dont_overwrite(self):
        (b.config_dir() / b.APPLETS_RC).write_text("x")
        b.backup_layout(); b.backup_layout()
        self.assertEqual(len(b.list_backups()), 2)

    def test_every_layout_clears_old_panels_first(self):
        for l in b.LAYOUTS:
            self.assertLess(l.script.index(".remove()"), l.script.index('bar("'), l.id)


class Effects(Base):
    def test_default_used_when_unset(self):
        blur = next(e for e in b.EFFECTS if e.id == "blur")
        wobbly = next(e for e in b.EFFECTS if e.id == "wobblywindows")
        r = FakeRunner()
        self.assertTrue(b.effect_enabled(r, blur))
        self.assertFalse(b.effect_enabled(r, wobbly))

    def test_magic_lamp_turns_squash_off(self):
        r = FakeRunner()
        lamp = next(e for e in b.EFFECTS if e.id == "magiclamp")
        b.set_effect(r, lamp, True)
        writes = [c for c in r.calls if c[0] == "kwriteconfig6"]
        self.assertIn("squashEnabled", [c[c.index("--key") + 1] for c in writes])
        self.assertIn(["qdbus6", "org.kde.KWin", "/Effects", "org.kde.kwin.Effects.unloadEffect", "squash"], r.calls)


class Colours(Base):
    def write_conf(self, text):
        b.my_config().parent.mkdir(parents=True, exist_ok=True)
        b.my_config().write_text(text)

    def test_set_then_follow_wallpaper(self):
        self.write_conf("[CUSTOM]\nmonitor = 0\n#color = 255,0,1\nlight = False\n")
        b.set_accent(FakeRunner(), "#BC9769")
        self.assertEqual(b.current_accent(), "#bc9769")
        b.set_accent(FakeRunner(), None)
        self.assertIsNone(b.current_accent())
        text = b.my_config().read_text()
        self.assertIn("light = False", text)
        self.assertEqual(text.count("color ="), 1)

    def test_adds_line_under_section_when_missing(self):
        self.write_conf("[CUSTOM]\nlight = False\n")
        b.set_accent(FakeRunner(), "#4285f4")
        lines = b.my_config().read_text().splitlines()
        self.assertLess(lines.index("[CUSTOM]"), lines.index("color = #4285f4"))

    def test_rejects_bad_colour_without_touching_file(self):
        self.write_conf("[CUSTOM]\n")
        ok, _ = b.set_accent(FakeRunner(), "red; rm -rf ~")
        self.assertFalse(ok)
        self.assertEqual(b.my_config().read_text(), "[CUSTOM]\n")

    def test_not_installed_is_a_failure(self):
        ok, _ = b.set_material_you(FakeRunner(installed=False), True)
        self.assertFalse(ok)


class DesktopIcons(Base):
    def test_switches_only_desktop_containments(self):
        # Shaped like a real Plasma 6 file: nested applet groups and General groups also exist.
        (b.config_dir() / b.APPLETS_RC).write_text(
            "[ActionPlugins][0]\nRightButton;NoModifier=org.kde.contextmenu\n\n"
            "[Containments][1]\nactivityId=abc\nformfactor=0\nplugin=org.kde.plasma.folder\n\n"
            "[Containments][1][General]\npositions=x\n\n"
            "[Containments][2]\nformfactor=2\nplugin=org.kde.panel\n\n"
            "[Containments][2][Applets][3]\nplugin=org.kde.plasma.folder\n")
        r = FakeRunner()
        self.assertTrue(b.desktop_icons_on(r))
        ok, _ = b.set_desktop_icons(r, False)
        self.assertTrue(ok)
        writes = [c for c in r.calls if c[0] == "kwriteconfig6"]
        self.assertEqual(len(writes), 1)
        self.assertIn("1", writes[0])
        self.assertEqual(writes[0][-1], b.PLAIN)
        self.assertEqual(len(b.list_backups()), 1)

    def test_repairs_the_wrong_id_an_earlier_version_wrote(self):
        (b.config_dir() / b.APPLETS_RC).write_text("[Containments][7]\nplugin=org.kde.desktop\n")
        r = FakeRunner()
        self.assertFalse(b.desktop_icons_on(r))
        b.set_desktop_icons(r, False)
        [w] = [c for c in r.calls if c[0] == "kwriteconfig6"]
        self.assertEqual(w[-1], "org.kde.desktopcontainment")


if __name__ == "__main__":
    unittest.main()
