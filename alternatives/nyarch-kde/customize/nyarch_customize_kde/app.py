"""Nyarch Customize for KDE: the window. All changes go through backend.py."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLabel,
    QListWidget, QMainWindow, QMessageBox, QPushButton, QRadioButton, QStackedWidget,
    QStatusBar, QVBoxLayout, QWidget,
)

from . import backend as b


def _page(title: str, intro: str) -> tuple[QWidget, QVBoxLayout]:
    w = QWidget()
    v = QVBoxLayout(w)
    h = QLabel(f"<h2>{title}</h2>")
    v.addWidget(h)
    i = QLabel(intro)
    i.setWordWrap(True)
    v.addWidget(i)
    return w, v


class Window(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.r = b.Runner()
        self.setWindowTitle("Nyarch Customize for KDE")
        self.setWindowIcon(QIcon.fromTheme("preferences-desktop-theme"))
        self.resize(760, 520)
        self.setStatusBar(QStatusBar())

        nav = QListWidget()
        nav.setFixedWidth(170)
        nav.setAccessibleName("Sections")
        self.stack = QStackedWidget()
        for name, page in (("Layouts", self._layouts()), ("Effects", self._effects()),
                           ("Colours", self._colours()), ("Desktop", self._desktop())):
            nav.addItem(name)
            self.stack.addWidget(page)
        nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        nav.setCurrentRow(0)

        root = QWidget()
        h = QHBoxLayout(root)
        h.addWidget(nav)
        h.addWidget(self.stack, 1)
        self.setCentralWidget(root)

        if not b.in_plasma():
            self.say(False, b.NOT_PLASMA)

    def say(self, ok: bool, msg: str) -> None:
        self.statusBar().showMessage(msg, 15000)
        if not ok:
            QMessageBox.warning(self, "Nyarch Customize", msg)

    # ------------------------------------------------------------------ layouts
    def _layouts(self) -> QWidget:
        w, v = _page("Panel layouts", "Pick a layout and press Apply. Your current panels are backed up "
                     "first; use Restore to go back.")
        self.layout_group = QButtonGroup(w)
        for i, l in enumerate(b.LAYOUTS):
            rb = QRadioButton(f"{l.label}: {l.description}")
            rb.setProperty("layout_id", l.id)
            rb.setChecked(i == 0)
            self.layout_group.addButton(rb)
            v.addWidget(rb)
        row = QHBoxLayout()
        apply_btn = QPushButton("Apply layout")
        apply_btn.clicked.connect(self._apply_layout)
        row.addWidget(apply_btn)
        row.addStretch()
        v.addLayout(row)

        v.addWidget(QLabel("<b>Restore a backup</b>"))
        row2 = QHBoxLayout()
        self.backups = QComboBox()
        self.backups.setAccessibleName("Layout backups")
        row2.addWidget(self.backups, 1)
        restore = QPushButton("Restore")
        restore.clicked.connect(self._restore)
        row2.addWidget(restore)
        v.addLayout(row2)
        self._fill_backups()
        v.addStretch()
        return w

    def _fill_backups(self) -> None:
        self.backups.clear()
        for p in b.list_backups():
            self.backups.addItem(p.name, str(p))

    def _apply_layout(self) -> None:
        btn = self.layout_group.checkedButton()
        if btn is None:
            return
        self.say(*b.apply_layout(self.r, btn.property("layout_id")))
        self._fill_backups()

    def _restore(self) -> None:
        path = self.backups.currentData()
        if not path:
            self.say(False, "There are no backups yet.")
            return
        if QMessageBox.question(self, "Restore layout",
                                f"Restore panels from {self.backups.currentText()}? "
                                "Plasma's panels restart for a moment.") != QMessageBox.StandardButton.Yes:
            return
        self.say(*b.restore_backup(self.r, Path(path)))

    # ------------------------------------------------------------------ effects
    def _effects(self) -> QWidget:
        w, v = _page("Window effects", "Changes apply straight away.")
        avail = b.effects_available(self.r)
        for eff in b.EFFECTS:
            cb = QCheckBox(f"{eff.label}: {eff.description}")
            cb.setChecked(b.effect_enabled(self.r, eff))
            if avail is not None and eff.id not in avail:
                cb.setEnabled(False)
                cb.setText(cb.text() + " (not installed)")
            cb.toggled.connect(lambda on, e=eff: self.say(*b.set_effect(self.r, e, on)))
            v.addWidget(cb)
        v.addStretch()
        return w

    # ------------------------------------------------------------------ colours
    def _colours(self) -> QWidget:
        w, v = _page("Accent colours", "Uses KDE Material You Colors to build a colour scheme from "
                     "your wallpaper or from one of Nyarch's accents.")
        installed = b.material_you_installed(self.r)
        self.my_on = QCheckBox("Wallpaper-based colours (Material You)")
        self.my_on.setChecked(b.material_you_on())
        self.my_on.setEnabled(installed)
        self.my_on.toggled.connect(lambda on: self.say(*b.set_material_you(self.r, on)))
        v.addWidget(self.my_on)
        if not installed:
            v.addWidget(QLabel("Install it first: <code>paru -S kde-material-you-colors</code>"))

        follow = QPushButton("Follow the wallpaper")
        follow.setEnabled(installed)
        follow.clicked.connect(lambda: self.say(*b.set_accent(self.r, None)))
        v.addWidget(follow)

        grid = QGridLayout()
        current = b.current_accent()
        for i, (swatch, source) in enumerate(b.ACCENTS):
            btn = QPushButton()
            btn.setFixedSize(44, 44)
            btn.setToolTip(swatch)
            btn.setAccessibleName(f"Accent {swatch}" + (", selected" if current == source else ""))
            border = "3px solid palette(highlight)" if current == source else "1px solid palette(mid)"
            btn.setStyleSheet(f"background:{swatch}; border:{border}; border-radius:22px;")
            btn.setEnabled(installed)
            btn.clicked.connect(lambda _=False, c=source: self.say(*b.set_accent(self.r, c)))
            grid.addWidget(btn, i // 7, i % 7)
        v.addLayout(grid)
        v.addStretch()
        return w

    # ------------------------------------------------------------------ desktop
    def _desktop(self) -> QWidget:
        w, v = _page("Desktop", "Show files and folders from ~/Desktop on the desktop, or keep it "
                     "clean. Plasma's panels restart for a moment; your layout is backed up first.")
        state = b.desktop_icons_on(self.r)
        cb = QCheckBox("Desktop icons")
        cb.setChecked(bool(state))
        cb.setEnabled(state is not None)
        cb.toggled.connect(lambda on: self.say(*b.set_desktop_icons(self.r, on)))
        v.addWidget(cb)
        v.addStretch()
        return w


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("nyarch-customize-kde")
    app.setDesktopFileName("nyarch-customize-kde")
    win = Window()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
