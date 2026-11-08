"""Animations generated on the laptop and streamed to the tubes.

Two kinds:
- per-tube pixel effects (software versions of the tube's PIXEL FX), drawn by a renderer
  `(t, n) -> n RGB colours` and shown identically on every selected tube;
- rig effects that coordinate several tubes (colour cycle, chase, table ping pong).

Every animation takes `speed` 1-10 (5 = normal, like the tube's own SPD), runs for
`seconds` (0 or less = until `stop` is set) and leaves the tubes dark when it ends.
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from typing import Callable

from .bd45r import BD45R
from .colors import RGB, gradient, hue_rgb, mix, scale

Renderer = Callable[[float, int], list[RGB]]
_FRAME_SECONDS = 1 / 25
BLACK: RGB = (0, 0, 0)
PALETTE: list[RGB] = [(255, 0, 0), (0, 255, 0), (0, 80, 255), (255, 160, 0), (255, 0, 200), (0, 255, 255)]


@dataclass
class Options:
    """Effect settings; None means the effect's own default."""

    seconds: float = 0
    intensity: float = 100
    speed: float = 5
    color: RGB | None = None
    background: RGB | None = None
    colors: list[RGB] | None = None
    block: int | None = None
    tail: int | None = None
    wavelength: float | None = None
    stagger: float = 0

    @property
    def k(self) -> float:
        if not 1 <= self.speed <= 10:
            raise ValueError(f"speed {self.speed} is outside 1..10")
        return self.speed / 5


# ---- per-tube pixel effects -------------------------------------------------

def _rolling(o: Options) -> Renderer:
    colors = o.colors or [hue_rgb(0), hue_rgb(120), hue_rgb(240)]
    block, rate = o.block or 4, 8 * o.k

    def render(t, n):
        offset = int(rate * t)
        return [colors[((i - offset) // block) % len(colors)] for i in range(n)]
    return render


def _rainbow(o: Options) -> Renderer:
    rate = 0.4 * o.k
    return lambda t, n: [hue_rgb(360 * (i / n - rate * t)) for i in range(n)]


def _meteor(o: Options) -> Renderer:
    color, tail, rate, gap = o.color or hue_rgb(240), o.tail or 10, 20 * o.k, 12

    def render(t, n):
        head = rate * t % (n + tail + gap)
        out = []
        for i in range(n):
            behind = head - i
            out.append(scale(color, (1 - behind / (tail + 1)) ** 2) if 0 <= behind <= tail else BLACK)
        return out
    return render


def _wave(o: Options) -> Renderer:
    fg, bg = o.color or hue_rgb(0), o.background or hue_rgb(120)
    wavelength, rate = o.wavelength or 11, 0.8 * o.k
    return lambda t, n: [mix(bg, fg, (1 + math.sin(2 * math.pi * (i / wavelength - rate * t))) / 2)
                         for i in range(n)]


def _pingpong(o: Options) -> Renderer:
    fg, bg = o.color or hue_rgb(180), o.background or hue_rgb(30, v=0.35)
    block, rate = o.block or 4, 25 * o.k

    def render(t, n):
        travel = max(1, n - block)
        p = rate * t % (2 * travel)
        start = round(p if p <= travel else 2 * travel - p)
        return [fg if start <= i < start + block else bg for i in range(n)]
    return render


def _blockgame(o: Options) -> Renderer:
    fg, bg = o.color or hue_rgb(60), o.background or hue_rgb(240, v=0.35)
    block, rate = o.block or 3, 40 * o.k

    def render(t, n):
        blocks = n // block
        # Block k falls n - (k+1)*block segments before landing on the stack at segment 1.
        durations = [(n - (k + 1) * block) / rate + 0.15 for k in range(blocks)]
        tt = t % (sum(durations) + 0.6)
        out = [bg] * n
        for k, d in enumerate(durations):
            if tt >= d:
                out[k * block : (k + 1) * block] = [fg] * block
                tt -= d
            else:
                pos = max(k * block, round(n - block - rate * tt))
                out[pos : min(n, pos + block)] = [fg] * (min(n, pos + block) - pos)
                break
        return out
    return render


PIXEL_EFFECTS: dict[str, tuple[Callable[[Options], Renderer], str]] = {
    "rolling": (_rolling, "bands of `colors` scrolling along the tube (block = band width)"),
    "rainbow": (_rainbow, "the hue wheel spread along the tube, scrolling"),
    "blockgame": (_blockgame, "`color` blocks drop and stack over `background`, then reset"),
    "pingpong": (_pingpong, "a `color` block bounces end to end over `background`"),
    "wave": (_wave, "sine waves of `color` rolling through `background` (wavelength in segments)"),
    "meteor": (_meteor, "a `color` meteor with a fading tail (tail in segments)"),
}


def _run_renderer(fixtures: list[BD45R], render: Renderer, o: Options, stop: threading.Event) -> None:
    begin = time.perf_counter()
    end = math.inf if o.seconds <= 0 else o.seconds
    while not stop.is_set() and (t := time.perf_counter() - begin) < end:
        for f in fixtures:
            f.paint(o.intensity, render(t, f.segments))
        stop.wait(_FRAME_SECONDS)


# ---- rig effects ------------------------------------------------------------

def _cycle(fixtures: list[BD45R], o: Options, stop: threading.Event) -> None:
    """Whole tubes sweep the hue wheel; tube i starts i*stagger seconds after the first."""
    period = 20 / o.k
    begin = time.perf_counter()
    end = math.inf if o.seconds <= 0 else o.seconds
    while not stop.is_set() and (now := time.perf_counter() - begin) < end:
        for i, f in enumerate(fixtures):
            elapsed = now - i * o.stagger
            if elapsed >= 0:
                f.rgb(o.intensity, *hue_rgb(360 * elapsed / period))
            else:
                f.intensity(0)
        stop.wait(_FRAME_SECONDS)


def _chase(fixtures: list[BD45R], o: Options, stop: threading.Event) -> None:
    """A block of `block` segments runs from segment 1 to the last on every tube, repeating."""
    color, width = o.color or (255, 255, 255), o.block or 3
    n = max(f.segments for f in fixtures)
    step = 6 / o.k / (n + width)
    begin = time.perf_counter()
    end = math.inf if o.seconds <= 0 else o.seconds
    head = 0
    while not stop.is_set() and time.perf_counter() - begin < end:
        for f in fixtures:
            f.paint(o.intensity, [color if head - width < i <= head else BLACK for i in range(f.segments)])
        head = (head + 1) % (n + width)
        stop.wait(step)


def _table_pingpong(fixtures: list[BD45R], o: Options, stop: threading.Event) -> None:
    """A ball runs along tube 1, then back along tube 2, ... bouncing from tube to tube.

    With each tube's `reverse` matching how it is mounted, it circles tubes that face each
    other. Colour steps through `colors` every 3 seconds.
    """
    palette, tail = o.colors or PALETTE, o.tail if o.tail is not None else 4
    if o.color:
        palette = [o.color]
    path = []
    for i, f in enumerate(fixtures):
        order = range(1, f.segments + 1) if i % 2 == 0 else range(f.segments, 0, -1)
        path.extend((f, s) for s in order)
    step = 1.5 / o.k / max(f.segments for f in fixtures)
    for f in fixtures:
        f.rgb(0, 0, 0, 0)
    lit: set = set()
    begin = time.perf_counter()
    end = math.inf if o.seconds <= 0 else o.seconds
    pos = 0
    while not stop.is_set() and (now := time.perf_counter() - begin) < end:
        color = palette[int(now / 3) % len(palette)]
        want = {}
        for k in range(tail + 1):
            want.setdefault(path[(pos - k) % len(path)], o.intensity * (1 - k / (tail + 1)))
        for f, s in lit - want.keys():
            f.rgb(0, 0, 0, 0, segment=s)
        for (f, s), level in want.items():
            f.rgb(level, *color, segment=s)
        lit = set(want)
        pos = (pos + 1) % len(path)
        stop.wait(step)


RIG_EFFECTS: dict[str, tuple[Callable[[list[BD45R], Options, threading.Event], None], str]] = {
    "cycle": (_cycle, "whole tubes sweep red -> green -> blue -> red; `stagger` delays each next tube"),
    "chase": (_chase, "a `color` block (block = width) runs from segment 1 to the end on every tube"),
    "table-pingpong": (_table_pingpong, "a ball bounces from tube to tube, changing colour (set `reverse` to match the layout)"),
}

NAMES = [*PIXEL_EFFECTS, *RIG_EFFECTS]


def describe() -> dict[str, str]:
    return {name: doc for name, (_, doc) in (PIXEL_EFFECTS | RIG_EFFECTS).items()}


def run(name: str, fixtures: list[BD45R], options: Options, stop: threading.Event | None = None) -> None:
    """Run animation `name` in the calling thread; dark tubes afterwards."""
    stop = stop or threading.Event()
    if not fixtures:
        raise ValueError("no fixtures selected")
    try:
        if name in PIXEL_EFFECTS:
            if any(f.segments == 1 for f in fixtures):
                raise ValueError(f"{name} needs DMX PIXEL below 33 (individual segments)")
            _run_renderer(fixtures, PIXEL_EFFECTS[name][0](options), options, stop)
        elif name in RIG_EFFECTS:
            RIG_EFFECTS[name][0](fixtures, options, stop)
        else:
            raise ValueError(f"unknown animation {name!r}; expected one of {NAMES}")
    finally:
        for f in fixtures:
            f.rgb(0, 0, 0, 0) if "r" in f.mode.channels else f.intensity(0)


def preview(name: str, options: Options, n: int = 33, t: float = 1.0) -> list[RGB]:
    """One frame of a pixel effect, for tests."""
    return PIXEL_EFFECTS[name][0](options)(t, n)


__all__ = ["NAMES", "Options", "describe", "gradient", "preview", "run"]
