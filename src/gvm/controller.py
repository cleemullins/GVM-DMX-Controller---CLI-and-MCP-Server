"""The one place the CLI and the MCP server go through to drive the tubes.

The tubes hold their last values when DMX stops, so the adapter is opened only while
something is being sent: a static change opens it, sends a few frames and closes it again.
The universe is saved to a small state file after every change and restored on the next
open, so changing one tube never resets the others, whichever tool made the change.

Animations need continuous output; `start` runs one in a background thread (the MCP
server's case) and `stop` ends it. Only one thing can use the adapter at a time.
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from . import animations
from .bd45r import BD45R
from .colors import RGB, gradient
from .config import Rig, RigConfig, default_state_path
from .dmx import DMX_CHANNELS


class Controller:
    def __init__(self, config: RigConfig, state_path: Path | None = None, settle_seconds: float = 0.3):
        self.config = config
        self.state_path = state_path or default_state_path()
        self.settle_seconds = settle_seconds
        self._lock = threading.Lock()
        self._effect: tuple[str, threading.Thread, threading.Event] | None = None
        self.last_error: str | None = None

    # ---- state ---------------------------------------------------------------

    def load_state(self) -> bytes:
        try:
            return self.state_path.read_bytes()[:DMX_CHANNELS]
        except OSError:
            return b""

    def save_state(self, data: bytes) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(self.state_path)

    # ---- sessions ------------------------------------------------------------

    @contextmanager
    def session(self, hold: float | None = None, stop_running: bool = True) -> Iterator[Rig]:
        """Open the adapter with the saved universe, yield the rig, send for `hold` s, save, close.

        Stops any background animation first (unless called from it). hold=None uses
        settle_seconds; hold<=0 keeps sending until KeyboardInterrupt (CLI use).
        """
        if stop_running:
            self.stop()
        hold = self.settle_seconds if hold is None else hold
        with self._lock:
            rig = Rig(self.config, self.load_state())
            try:
                yield rig
                if hold <= 0:
                    try:
                        while True:
                            time.sleep(1)
                    except KeyboardInterrupt:
                        pass
                else:
                    time.sleep(hold)
            finally:
                self.save_state(rig.dmx.snapshot())
                rig.close()

    def layout(self) -> list[BD45R]:
        """The patched fixtures, without opening the adapter."""
        return self.config.build_fixtures(None)

    # ---- static looks ----------------------------------------------------------

    def _apply(self, fixtures: list[str] | None, segments: list[int] | None, action) -> list[str]:
        with self.session() as rig:
            chosen = rig.select(fixtures)
            for f in chosen:
                for seg in segments or [None]:
                    action(f, seg)
            return [f.name for f in chosen]

    def white(self, intensity: float, kelvin: float = 5600, gm: float = 0,
              fixtures: list[str] | None = None, segments: list[int] | None = None) -> list[str]:
        return self._apply(fixtures, segments, lambda f, s: f.cct(intensity, kelvin, gm, s))

    def color(self, rgb: RGB, intensity: float = 100,
              fixtures: list[str] | None = None, segments: list[int] | None = None) -> list[str]:
        return self._apply(fixtures, segments, lambda f, s: f.rgb(intensity, *rgb, segment=s))

    def hsi(self, hue: float, sat: float = 100, intensity: float = 100,
            fixtures: list[str] | None = None, segments: list[int] | None = None) -> list[str]:
        return self._apply(fixtures, segments, lambda f, s: f.hsi(intensity, hue, sat, s))

    def dim(self, intensity: float, fixtures: list[str] | None = None,
            segments: list[int] | None = None) -> list[str]:
        return self._apply(fixtures, segments, lambda f, s: f.intensity(intensity, s))

    def off(self, fixtures: list[str] | None = None) -> list[str]:
        return self._apply(fixtures, None, lambda f, s: f.off())

    def paint(self, stops: list[RGB], intensity: float = 100, fixtures: list[str] | None = None) -> list[str]:
        """Spread colour stops along each tube (one colour per segment if counts match)."""
        return self._apply(fixtures, None, lambda f, s: f.paint(intensity, gradient(stops, f.segments)))

    def raw(self, values: dict[int, int]) -> None:
        with self.session() as rig:
            for channel, value in values.items():
                rig.dmx.set(channel, value)

    # ---- animations ------------------------------------------------------------

    def run_effect(self, name: str, options: animations.Options, fixtures: list[str] | None = None,
                   stop: threading.Event | None = None) -> None:
        """Run an animation in this thread until it ends, `stop` is set, or Ctrl+C."""
        stop = stop or threading.Event()
        with self.session(hold=0.1, stop_running=False) as rig:
            try:
                animations.run(name, rig.select(fixtures), options, stop)
            except KeyboardInterrupt:
                stop.set()

    def start(self, name: str, options: animations.Options, fixtures: list[str] | None = None) -> None:
        """Start an animation in the background (replacing any running one)."""
        if name not in animations.NAMES:
            raise ValueError(f"unknown effect {name!r}; expected one of {animations.NAMES}")
        self.layout()  # surface patch errors now rather than in the thread
        self.stop()
        stop = threading.Event()

        def target():
            try:
                self.run_effect(name, options, fixtures, stop)
            except Exception as e:  # reported through status()
                self.last_error = f"{name}: {e}"

        self.last_error = None
        thread = threading.Thread(target=target, name=f"gvm-effect-{name}", daemon=True)
        self._effect = (name, thread, stop)
        thread.start()

    def stop(self) -> str | None:
        """Stop the background animation, if any; returns its name."""
        effect, self._effect = self._effect, None
        if not effect:
            return None
        name, thread, stop = effect
        stop.set()
        if thread is not threading.current_thread():
            thread.join()
        return name

    def running(self) -> str | None:
        if self._effect and self._effect[1].is_alive():
            return self._effect[0]
        return None
