"""One administrator session per Checkup run: authenticate once, then reuse it."""

import json
import subprocess
import threading

from .util import helper_path

END = "\x1eEND"


class RootSession:
    """Talks to checkup-root, started once via pkexec (app) or sudo (terminal)."""

    _instances = {}

    @classmethod
    def get(cls, gui):
        if gui not in cls._instances:
            cls._instances[gui] = cls(gui)
        return cls._instances[gui]

    def __init__(self, gui):
        self.gui = gui
        self.proc = None
        self.lock = threading.Lock()
        self.last_rc = None
        self.refused = False

    def _start(self):
        if self.proc and self.proc.poll() is None:
            return True
        cmd = (["pkexec"] if self.gui else ["sudo"]) + [helper_path(), "serve"]
        try:
            self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                                         bufsize=1, errors="replace")
        except FileNotFoundError:
            self.proc = None
            return False
        first = self.proc.stdout.readline()
        if first.strip() != "READY":
            self.proc.wait()
            self.proc = None
            self.refused = True
            return False
        self.refused = False
        return True

    @property
    def active(self):
        return bool(self.proc and self.proc.poll() is None)

    def request(self, action, **fields):
        """Yield the helper's output lines; afterwards self.last_rc holds the exit code.
        Raises PermissionError if administrator access was refused."""
        with self.lock:
            if not self._start():
                raise PermissionError("Administrator access was refused or cancelled.")
            self.proc.stdin.write(json.dumps({"action": action, **fields}) + "\n")
            self.proc.stdin.flush()
            finished = False
            try:
                for line in self.proc.stdout:
                    line = line.rstrip("\n")
                    if line.startswith(END):
                        self.last_rc = int(line.split()[1])
                        finished = True
                        return
                    yield line
                self.proc = None
                self.last_rc = 1
                finished = True
                raise RuntimeError("The administrator helper stopped unexpectedly.")
            finally:
                if not finished and self.proc:   # caller stopped reading: skip to the end of this answer
                    for line in self.proc.stdout:
                        if line.startswith(END):
                            break

    def call(self, action, **fields):
        """Collect all output lines. Returns (exit code, lines)."""
        lines = list(self.request(action, **fields))
        return self.last_rc, lines

    def close(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()
        self.proc = None
