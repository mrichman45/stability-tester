"""Checkup desktop app: My Setup (laptop-specific auto-config), Stability (any computer), Guide."""

import re
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPalette, QPen
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QGroupBox,
                               QHBoxLayout, QHeaderView, QInputDialog, QLabel, QListWidget, QListWidgetItem,
                               QMainWindow, QMessageBox, QProgressBar, QPushButton, QRadioButton, QSplitter,
                               QTabWidget, QTextBrowser, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from . import guide, runner
from .checks import FAIL, INFO, OK, SKIP, WARN, Context, run_checks
from .machine import detect, profiles
from .stability import StabilityOptions, StabilityRun

STATUS = {OK: ("✔", "#2e9d4f"), WARN: ("⚠", "#d08a00"), FAIL: ("✖", "#d33f3f"),
          SKIP: ("–", "#888888"), INFO: ("ℹ", "#2f7fd0")}
STAGES = {"cpu": "CPU stress test", "gpu": "GPU stress test", "admin": "Waiting for your password…",
          "ram": "RAM test", "disks": "Checking disk health", "log": "Checking the system log",
          "health": "Testing this laptop's profile",
          "done": "Finished", "idle": ""}


def html_escape(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Bridge(QObject):
    """Carries results from worker threads back to the window."""
    checks_done = Signal(object)
    sample = Signal(object)
    stage = Signal(str, int, int)
    result = Signal(object)
    stability_done = Signal(object)


def start_in_terminal(parent, plan, title, on_finished):
    """Run a plan's script in a visible terminal window; call on_finished(exit_status or None)."""
    script, status = runner.write_script(plan, title)
    cmd = runner.terminal_command(script)
    if not cmd:
        QMessageBox.warning(parent, "No terminal found",
                            f"Couldn't find a terminal app. Run this yourself:\n\nbash {script}")
        on_finished(None)
        return None
    if cmd[0] == "konsole":
        cmd.insert(1, "--nofork")
    proc = QProcess(parent)
    proc.finished.connect(lambda *_: on_finished(runner.read_status(status)))
    proc.start(cmd[0], cmd[1:])
    return proc


# ---------------------------------------------------------------- graph

class Graph(QWidget):
    WINDOW = 300  # samples kept (10 minutes at one every 2 s)

    def __init__(self):
        super().__init__()
        self.cpu, self.gpu = [], []
        self.setMinimumHeight(190)

    def clear(self):
        self.cpu, self.gpu = [], []
        self.update()

    def add(self, cpu, gpu):
        self.cpu.append(cpu if cpu else None)
        self.gpu.append(gpu)
        self.cpu, self.gpu = self.cpu[-self.WINDOW:], self.gpu[-self.WINDOW:]
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        text = self.palette().color(QPalette.Text)
        r = self.rect().adjusted(44, 12, -12, -22)
        lo, hi = 30, 105

        def y(v):
            return r.bottom() - (min(max(v, lo), hi) - lo) / (hi - lo) * r.height()

        grid = QColor(text)
        grid.setAlpha(50)
        for t in (40, 60, 80, 100):
            p.setPen(QPen(grid, 1, Qt.DashLine if t != 100 else Qt.SolidLine))
            p.drawLine(r.left(), int(y(t)), r.right(), int(y(t)))
            p.setPen(text)
            p.drawText(4, int(y(t)) + 5, f"{t}°C")

        n = max(len(self.cpu), 60)

        def draw(series, color):
            p.setPen(QPen(QColor(color), 2))
            prev = None
            for i, v in enumerate(series):
                pt = None if v is None else (r.left() + i * r.width() / (n - 1), y(v))
                if pt and prev:
                    p.drawLine(int(prev[0]), int(prev[1]), int(pt[0]), int(pt[1]))
                prev = pt

        draw(self.cpu, "#e0533d")
        draw(self.gpu, "#3d9be0")
        p.setPen(QColor("#e0533d"))
        p.drawText(r.right() - 150, r.top() + 14, "● CPU")
        p.setPen(QColor("#3d9be0"))
        p.drawText(r.right() - 80, r.top() + 14, "● GPU")
        p.end()


# ---------------------------------------------------------------- My Setup

class ChooseFixesDialog(QDialog):
    def __init__(self, parent, label, todo, manual):
        super().__init__(parent)
        self.setWindowTitle(f"Set up {label}")
        self.resize(640, 480)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"<b>Apply these fixes from the guide?</b> Untick anything you don't want."))
        self.list = QListWidget()
        for c, r in todo:
            item = QListWidgetItem(f"{c.title} — {r.fix.summary}")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            item.setToolTip(r.detail + ("\n\n" + "\n".join("$ " + l for l in r.fix.script) if r.fix.script else ""))
            self.list.addItem(item)
        lay.addWidget(self.list)
        if manual:
            lay.addWidget(QLabel("<b>Can't be automated (you'll get a reminder afterwards):</b><br>"
                                 + "<br>".join(f"• {html_escape(c.title)}" for c, _ in manual)))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Continue")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.todo = todo

    def chosen(self):
        return [t for i, t in enumerate(self.todo) if self.list.item(i).checkState() == Qt.Checked]


class SetupTab(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.results = []
        self.pending_fixed_by = {}
        self.remind_manual = False
        self.proc = None
        self.bridge = Bridge()
        self.bridge.checks_done.connect(self.on_checks_done)

        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.machine_label = QLabel()
        change = QPushButton("Change laptop…")
        change.clicked.connect(self.change_machine)
        self.btn_check = QPushButton(QIcon.fromTheme("view-refresh"), "Check again")
        self.btn_check.clicked.connect(self.run_checks)
        self.btn_setup = QPushButton(QIcon.fromTheme("run-build"), "Set up this laptop")
        self.btn_setup.setToolTip("Apply every fix from the guide that belongs on this laptop, in one go")
        self.btn_setup.clicked.connect(self.setup_all)
        f = self.btn_setup.font()
        f.setBold(True)
        self.btn_setup.setFont(f)
        top.addWidget(self.machine_label)
        top.addWidget(change)
        top.addStretch()
        top.addWidget(self.btn_check)
        top.addWidget(self.btn_setup)
        lay.addLayout(top)

        self.summary = QLabel()
        self.summary.setWordWrap(True)
        lay.addWidget(self.summary)

        split = QSplitter()
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["", "Check", "Result"])
        self.tree.setRootIsDecorated(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.currentItemChanged.connect(lambda *_: self.show_detail())
        split.addWidget(self.tree)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.detail = QTextBrowser()
        rl.addWidget(self.detail)
        row = QHBoxLayout()
        self.btn_fix = QPushButton(QIcon.fromTheme("tools-wizard"), "Fix")
        self.btn_fix.clicked.connect(self.fix_selected)
        self.btn_ignore = QPushButton("Ignore")
        self.btn_ignore.clicked.connect(self.toggle_ignore)
        self.btn_guide = QPushButton(QIcon.fromTheme("help-contents"), "Open in guide")
        self.btn_guide.clicked.connect(self.open_guide)
        for b in (self.btn_fix, self.btn_ignore, self.btn_guide):
            row.addWidget(b)
        rl.addLayout(row)
        split.addWidget(right)
        split.setSizes([560, 420])
        lay.addWidget(split)
        self.update_machine_label()
        self.show_detail()

    # ----- laptop profile
    def update_machine_label(self):
        m = self.win.machine
        how = f" <span style='color:gray'>(recognised by {html_escape(m.detected_by)})</span>" if m.detected_by else ""
        self.machine_label.setText(f"<b>{html_escape(m.label)}</b>{how}")

    def change_machine(self):
        profs = profiles()
        ids = list(profs)
        labels = [profs[i]["label"] for i in ids] + ["Detect automatically", "None of these (general checks only)"]
        current = ids.index(self.win.machine.id) if self.win.machine.id in ids else len(ids)
        choice, ok = QInputDialog.getItem(self, "Which laptop is this?",
                                          "Checkup applies the guide's fixes for this laptop:", labels, current, False)
        if not ok:
            return
        idx = labels.index(choice)
        self.win.cfg["machine"] = ids[idx] if idx < len(ids) else ("" if idx == len(ids) else "none")
        guide.save_config(self.win.cfg)
        self.win.machine = detect(self.win.cfg["machine"])
        self.update_machine_label()
        self.win.stability_tab.refresh_laptop()
        self.win.guide_tab.reload()
        self.run_checks()

    # ----- running checks
    def set_busy(self, busy, text=""):
        for b in (self.btn_check, self.btn_setup, self.btn_fix, self.btn_ignore):
            b.setEnabled(not busy)
        if text:
            self.summary.setText(text)
        if not busy:
            self.show_detail()

    def run_checks(self):
        self.set_busy(True, "Checking… (you may be asked for your password to read Secure Boot and drive status)")
        machine, ignored = self.win.machine, list(self.win.cfg.get("ignored", []))

        def work():
            try:
                res = run_checks(Context(machine, gui=True, cfg=self.win.cfg), ignored)
            except Exception as e:
                res = e
            self.bridge.checks_done.emit(res)

        threading.Thread(target=work, daemon=True).start()

    def on_checks_done(self, res):
        if isinstance(res, Exception):
            self.set_busy(False, f"Checking failed: {res}")
            return
        self.results = res
        self.tree.clear()
        for i, (c, r) in enumerate(res):
            sym, color = STATUS[r.status]
            item = QTreeWidgetItem([sym, c.title, r.detail])
            item.setForeground(0, QColor(color))
            item.setData(0, Qt.UserRole, i)
            item.setToolTip(2, r.detail)
            self.tree.addTopLevelItem(item)

        added = []
        if self.win.machine.id not in ("unknown", "none"):
            items = [(c.id, c.title, r.status, r.detail, c.guide) for c, r in res]
            added = guide.record(self.win.cfg, self.win.machine, items, self.pending_fixed_by)
        self.pending_fixed_by = {}
        counts = {s: sum(1 for _, r in res if r.status == s) for s in (OK, WARN, FAIL)}
        fixable = sum(1 for _, r in res if r.status in (FAIL, WARN) and r.fix)
        text = f"✔ {counts[OK]} fine   ⚠ {counts[WARN]} warnings   ✖ {counts[FAIL]} problems"
        if fixable:
            text += f" — {fixable} can be fixed automatically: press <b>Set up this laptop</b>."
        elif not counts[FAIL] and not counts[WARN]:
            text += " — everything from the guide is in place."
        if added:
            text += "<br>Added to the guide's fix log: " + ", ".join(html_escape(a) for a in added)
            self.win.guide_tab.reload()
        self.set_busy(False, text)
        if self.tree.topLevelItemCount():
            self.tree.setCurrentItem(self.tree.topLevelItem(0))
        if self.remind_manual:
            self.remind_manual = False
            self.show_manual_reminders()

    # ----- details
    def current(self):
        item = self.tree.currentItem()
        if not item:
            return None, None
        try:
            idx = int(item.data(0, Qt.UserRole))
        except (TypeError, ValueError):
            return None, None
        return self.results[idx] if 0 <= idx < len(self.results) else (None, None)

    def show_detail(self):
        c, r = self.current()
        if not c:
            self.detail.setHtml("<p style='color:gray'>Select a check to see details.</p>")
            for b in (self.btn_fix, self.btn_ignore, self.btn_guide):
                b.setEnabled(False)
            return
        sym, color = STATUS[r.status]
        html = [f"<h3>{html_escape(c.title)}</h3>",
                f"<p><span style='color:{color}'>{sym}</span> {html_escape(r.detail)}</p>"]
        if r.manual:
            html.append(f"<p><b>To do by hand:</b> {html_escape(r.manual)}</p>")
        if r.fix and r.status in (FAIL, WARN):
            html.append(f"<p><b>Fix:</b> {html_escape(r.fix.summary)}</p>")
            if r.fix.script:
                html.append("<pre>" + html_escape("\n".join("$ " + l for l in r.fix.script)) + "</pre>")
            if r.fix.python:
                html.append("<p>Checkup edits your config file directly (a backup is saved first).</p>")
            if r.fix.danger:
                html.append(f"<p style='color:#d33f3f'><b>Note:</b> {html_escape(r.fix.danger)}</p>")
            if r.fix.after:
                html.append(f"<p><b>Afterwards:</b> {html_escape(r.fix.after)}</p>")
        if c.preference:
            html.append("<p style='color:gray'>This is a choice you made. Use <b>Ignore</b> if you change your mind.</p>")
        self.detail.setHtml("".join(html))
        self.btn_fix.setEnabled(bool(r.fix) and r.status in (FAIL, WARN))
        self.btn_guide.setEnabled(True)
        self.btn_ignore.setEnabled(True)
        self.btn_ignore.setText("Stop ignoring" if c.id in self.win.cfg.get("ignored", []) else "Ignore")

    def toggle_ignore(self):
        c, _ = self.current()
        if not c:
            return
        ignored = set(self.win.cfg.get("ignored", []))
        ignored.symmetric_difference_update({c.id})
        self.win.cfg["ignored"] = sorted(ignored)
        guide.save_config(self.win.cfg)
        self.run_checks()

    def open_guide(self):
        c, _ = self.current()
        if c:
            self.win.tabs.setCurrentWidget(self.win.guide_tab)
            self.win.guide_tab.jump(c.guide)

    # ----- fixing
    def fix_selected(self):
        c, r = self.current()
        if c and r.fix:
            self.apply([(c, r)], f"Fixing: {c.title}")

    def setup_all(self):
        todo = [(c, r) for c, r in self.results if r.status in (FAIL, WARN) and r.fix]
        manual = [(c, r) for c, r in self.results if r.status in (FAIL, WARN, INFO) and r.manual and not r.fix]
        if not todo:
            QMessageBox.information(self, "Nothing to apply", "Everything from the guide that can be automated is already in place.")
            if manual:
                self.show_manual_reminders()
            return
        dlg = ChooseFixesDialog(self, self.win.machine.label, todo, manual)
        if dlg.exec() and dlg.chosen():
            self.remind_manual = True
            self.apply(dlg.chosen(), f"Setting up {self.win.machine.label}")

    def apply(self, chosen, title):
        plan = runner.build_plan(chosen)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("Confirm")
        box.setText(f"Apply {len(plan.items)} fix{'es' if len(plan.items) != 1 else ''}?")
        info = "Commands that need your password run in a terminal window so you can watch them."
        if plan.dangers:
            info += "\n\n" + "\n".join("⚠ " + d for d in plan.dangers)
        box.setInformativeText(info)
        box.setDetailedText(plan.describe() + ("\n\n" + "\n\n".join(plan.previews) if plan.previews else ""))
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.Yes if not plan.dangers else QMessageBox.No)
        box.exec()
        if box.standardButton(box.clickedButton()) != QMessageBox.Yes:
            self.remind_manual = False
            return

        notes, errors = runner.run_python_steps(plan)
        if errors:
            QMessageBox.warning(self, "Some edits failed", "\n".join(errors))
        self.pending_fixed_by.update(plan.fixed_by)
        if self.win.machine.id != "unknown":
            guide.remember_fixes(self.win.machine, plan.fixed_by)
        if not plan.script:
            self.run_checks()
            return
        self.set_busy(True, "Running the fixes in the terminal window… Checkup will check again when it closes.")

        def finished(status):
            msg = {None: "The terminal window closed before the fixes finished.",
                   0: None}.get(status, "A step failed. The terminal window showed which one.")
            if msg:
                QMessageBox.information(self, "Fixes", msg)
            self.run_checks()

        self.proc = start_in_terminal(self, plan, title, finished)

    def show_manual_reminders(self):
        manual = [(c, r) for c, r in self.results if r.status in (FAIL, WARN, INFO) and r.manual and not r.fix]
        if manual:
            QMessageBox.information(self, "Still to do by hand",
                                    "\n\n".join(f"• {c.title}: {r.manual}" for c, r in manual))


# ---------------------------------------------------------------- Stability

class StabilityTab(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.run = None
        self.bridge = Bridge()
        self.bridge.sample.connect(self.on_sample)
        self.bridge.stage.connect(self.on_stage)
        self.bridge.result.connect(self.on_result)
        self.bridge.stability_done.connect(self.on_done)

        lay = QVBoxLayout(self)
        intro = QLabel("Stress-tests the processor, graphics, memory and disks, and checks the system log for hardware "
                       "errors. Works on any computer. Plug laptops in first.<br>On one of our laptops it also tests that laptop's "
                       "profile: that every fix from the guide still <i>works</i>, which shows what an update broke.")
        intro.setWordWrap(True)
        lay.addWidget(intro)

        opts = QGroupBox("Test")
        ol = QHBoxLayout(opts)
        self.quick = QRadioButton("Quick (about 15 min)")
        self.full = QRadioButton("Full (about 45 min)")
        self.quick.setChecked(True)
        ol.addWidget(self.quick)
        ol.addWidget(self.full)
        ol.addSpacing(20)
        self.parts = {}
        for key, label in (("cpu", "CPU"), ("gpu", "GPU"), ("ram", "RAM"), ("disk", "Disks")):
            cb = QCheckBox(label)
            cb.setChecked(True)
            self.parts[key] = cb
            ol.addWidget(cb)
        self.health_cb = QCheckBox()
        self.health_cb.setChecked(True)
        ol.addWidget(self.health_cb)
        self.refresh_laptop()
        ol.addStretch()
        self.btn_start = QPushButton(QIcon.fromTheme("media-playback-start"), "Start")
        self.btn_stop = QPushButton(QIcon.fromTheme("media-playback-stop"), "Stop")
        self.btn_stop.setEnabled(False)
        self.btn_start.clicked.connect(self.start)
        self.btn_stop.clicked.connect(self.stop)
        ol.addWidget(self.btn_start)
        ol.addWidget(self.btn_stop)
        lay.addWidget(opts)

        row = QHBoxLayout()
        self.stage_label = QLabel("Ready.")
        self.live = QLabel()
        row.addWidget(self.stage_label)
        row.addStretch()
        row.addWidget(self.live)
        lay.addLayout(row)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        lay.addWidget(self.progress)
        self.graph = Graph()
        lay.addWidget(self.graph)

        self.results = QTreeWidget()
        self.results.setHeaderLabels(["", "Test", "Result"])
        self.results.setRootIsDecorated(False)
        self.results.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.results.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        lay.addWidget(self.results)

        bottom = QHBoxLayout()
        self.overall = QLabel()
        self.btn_report = QPushButton(QIcon.fromTheme("document-open"), "Open report")
        self.btn_report.setEnabled(False)
        self.btn_report.clicked.connect(self.open_report)
        self.btn_reapply = QPushButton(QIcon.fromTheme("tools-wizard"), "Reapply fixes")
        self.btn_reapply.setToolTip("Re-run the guide's fixes for the health tests that failed")
        self.btn_reapply.setEnabled(False)
        self.btn_reapply.clicked.connect(self.reapply)
        bottom.addWidget(self.overall)
        bottom.addStretch()
        bottom.addWidget(self.btn_reapply)
        bottom.addWidget(self.btn_report)
        lay.addLayout(bottom)

    def refresh_laptop(self):
        m = self.win.machine
        known = m.id != "unknown"
        short = m.label.split(" (")[0] if known else ""
        self.health_cb.setText(f"Test {short} profile" if known else "")
        self.health_cb.setToolTip("Checks that every fix in this laptop's profile still works after updates: "
                                  + ", ".join(dict.fromkeys(m.health + m.checks)) if known else "")
        self.health_cb.setVisible(known)

    def start(self):
        opts = StabilityOptions.quick() if self.quick.isChecked() else StabilityOptions()
        opts.do_health = self.health_cb.isVisible() and self.health_cb.isChecked()
        opts.do_cpu, opts.do_gpu = self.parts["cpu"].isChecked(), self.parts["gpu"].isChecked()
        opts.do_ram, opts.do_disk = self.parts["ram"].isChecked(), self.parts["disk"].isChecked()
        self.results.clear()
        self.graph.clear()
        self.overall.setText("")
        self.btn_report.setEnabled(False)
        self.btn_reapply.setEnabled(False)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.run = StabilityRun(opts, gui=True, on_sample=self.bridge.sample.emit, on_stage=self.bridge.stage.emit,
                                on_result=self.bridge.result.emit, machine=self.win.machine, cfg=self.win.cfg)
        run = self.run

        def work():
            try:
                run.run()
            finally:
                self.bridge.stability_done.emit(run)

        threading.Thread(target=work, daemon=True).start()

    def stop(self):
        if self.run:
            self.run.cancel()
            self.stage_label.setText("Stopping…")
            self.btn_stop.setEnabled(False)

    def on_sample(self, s):
        self.graph.add(s.get("cpu_temp"), s.get("gpu_temp"))
        text = f"CPU {s['cpu_temp']}°C · {s['cpu_mhz']} MHz"
        if s.get("gpu_temp") is not None:
            text += f"   GPU {s['gpu_temp']:.0f}°C"
            if s.get("gpu_mhz"):
                text += f" · {s['gpu_mhz']:.0f} MHz"
            if s.get("gpu_w"):
                text += f" · {s['gpu_w']:.0f} W"
        self.live.setText(text)

    def on_stage(self, name, left, total):
        label = STAGES.get(name, name)
        if total:
            self.progress.setRange(0, total)
            self.progress.setValue(total - left)
            label += f" — {left // 60}:{left % 60:02d} left"
        else:
            self.progress.setRange(0, 0)  # busy
        self.stage_label.setText(label)

    def on_result(self, r):
        sym, color = STATUS[r.status]
        item = QTreeWidgetItem([sym, r.title, r.detail])
        item.setForeground(0, QColor(color))
        item.setToolTip(2, r.detail)
        self.results.addTopLevelItem(item)

    def on_done(self, run):
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_report.setEnabled(bool(run.report_path))
        overall = run.overall()
        words = {OK: "Stable.", WARN: "Stable, with warnings worth a look.", FAIL: "Problems found."}[overall]
        reapply = run.needs_reapply()
        if reapply:
            words += f" {len(reapply)} fix{'es' if len(reapply) != 1 else ''} from the guide need reapplying."
        self.btn_reapply.setEnabled(bool(reapply))
        self.overall.setText(f"<b style='color:{STATUS[overall][1]}'>{words}</b>")
        self.stage_label.setText("Stopped." if run._cancel.is_set() else "Finished.")
        m = self.win.machine
        if m.id not in ("unknown", "none") and run.results:
            added = guide.record(self.win.cfg, m, [(f"stability-{r.id}", f"Stability: {r.title}", r.status, r.detail, "")
                                                    for r in run.results])
            if added:
                self.win.guide_tab.reload()

    def reapply(self):
        if self.run and self.run.needs_reapply():
            self.win.tabs.setCurrentWidget(self.win.setup_tab)
            self.win.setup_tab.apply(self.run.needs_reapply(), f"Reapplying fixes on {self.win.machine.label}")

    def open_report(self):
        if self.run and self.run.report_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.run.report_path)))


# ---------------------------------------------------------------- Guide

class GuideTab(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.proc = None
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        self.path_label = QLabel()
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(self.path_label)
        row.addStretch()
        for text, icon, slot in (("Reload", "view-refresh", self.reload),
                                 ("Open in editor", "document-edit", self.open_editor),
                                 ("Sync with GitHub", "folder-sync", self.sync),
                                 ("Choose file…", "document-open", self.choose)):
            b = QPushButton(QIcon.fromTheme(icon), text)
            b.clicked.connect(slot)
            row.addWidget(b)
        lay.addLayout(row)
        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(self.on_link)
        lay.addWidget(self.browser)
        self.reload()

    def path(self):
        return guide.guide_path(self.win.cfg, self.win.machine)

    def reload(self):
        p = self.path()
        self.path_label.setText(f"<span style='color:gray'>{html_escape(str(p))}</span>")
        text = Path(p).read_text(errors="replace")
        text = re.sub(r'^<a id="[^"]+"></a>\s*$', "", text, flags=re.M)
        text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
        self.browser.setMarkdown(text)

    def jump(self, anchor):
        title = guide.headings(self.path()).get(anchor)
        if not title:
            return
        doc = self.browser.document()
        cursor = doc.find(title)
        if not cursor.isNull():
            self.browser.setTextCursor(cursor)
            self.browser.ensureCursorVisible()

    def on_link(self, url):
        if url.scheme() in ("", "file") and url.fragment():
            self.jump(url.fragment())
        else:
            QDesktopServices.openUrl(url)

    def open_editor(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path())))

    def choose(self):
        f, _ = QFileDialog.getOpenFileName(self, "Choose the guide file", str(Path.home()), "Markdown (*.md)")
        if f:
            self.win.cfg.setdefault("guide_paths", {})[self.win.machine.id] = f
            guide.save_config(self.win.cfg)
            self.reload()

    def sync(self):
        lines = guide.sync_script(self.path())
        if not lines:
            QMessageBox.information(self, "Not a git repository",
                                    "This guide isn't inside a git clone, so it can't be synced. Clone the "
                                    "stability-tester repo to ~/stability-tester and Checkup will use its guides.")
            return
        plan = runner.Plan(items=[], script=lines)
        self.proc = start_in_terminal(self, plan, "Syncing the guide with GitHub", lambda status: self.reload())


# ---------------------------------------------------------------- window

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = guide.load_config()
        self.machine = detect(self.cfg.get("machine", ""))
        self.setWindowTitle("Checkup")
        self.setWindowIcon(QIcon.fromTheme("utilities-system-monitor"))
        self.resize(1050, 720)
        self.tabs = QTabWidget()
        self.guide_tab = GuideTab(self)
        self.setup_tab = SetupTab(self)
        self.stability_tab = StabilityTab(self)
        self.tabs.addTab(self.setup_tab, QIcon.fromTheme("configure"), "My Setup")
        self.tabs.addTab(self.stability_tab, QIcon.fromTheme("speedometer"), "Stability")
        self.tabs.addTab(self.guide_tab, QIcon.fromTheme("help-contents"), "Guide")
        self.setCentralWidget(self.tabs)
        if self.machine.id == "unknown" and self.cfg.get("machine") != "none":
            QTimer.singleShot(0, self.setup_tab.change_machine)
        else:
            QTimer.singleShot(0, self.setup_tab.run_checks)

    def closeEvent(self, event):
        run = self.stability_tab.run
        if run and run.stage not in ("done", "idle"):
            if QMessageBox.question(self, "Stop the test?", "A stability test is running. Stop it and quit?") != QMessageBox.Yes:
                event.ignore()
                return
            run.cancel()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Checkup")
    app.setDesktopFileName("checkup")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
