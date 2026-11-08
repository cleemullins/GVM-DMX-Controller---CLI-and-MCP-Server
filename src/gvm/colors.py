"""Colour parsing shared by the CLI and the MCP server."""

from __future__ import annotations

import colorsys

RGB = tuple[int, int, int]

NAMED: dict[str, RGB] = {
    "off": (0, 0, 0), "black": (0, 0, 0), "white": (255, 255, 255),
    "red": (255, 0, 0), "orange": (255, 100, 0), "amber": (255, 150, 0), "yellow": (255, 220, 0),
    "lime": (150, 255, 0), "green": (0, 255, 0), "teal": (0, 255, 150), "cyan": (0, 255, 255),
    "sky": (0, 150, 255), "blue": (0, 0, 255), "purple": (130, 0, 255), "violet": (180, 0, 255),
    "magenta": (255, 0, 255), "pink": (255, 60, 150),
}


def hue_rgb(h: float, s: float = 1.0, v: float = 1.0) -> RGB:
    """Hue in degrees, saturation and value 0-1 -> 0-255 RGB."""
    r, g, b = colorsys.hsv_to_rgb((h / 360) % 1.0, s, v)
    return round(r * 255), round(g * 255), round(b * 255)


def parse_color(text: str) -> RGB:
    """'red', '#ff8800', 'ff8800', '255,136,0', or 'hue:240' / 'hue:240,50' (saturation %)."""
    t = text.strip().lower()
    if t in NAMED:
        return NAMED[t]
    if t.startswith("hue:"):
        parts = t[4:].split(",")
        sat = float(parts[1]) / 100 if len(parts) > 1 else 1.0
        return hue_rgb(float(parts[0]), sat)
    if "," in t:
        values = tuple(int(v) for v in t.split(","))
        if len(values) == 3 and all(0 <= v <= 255 for v in values):
            return values
    hexa = t.removeprefix("#")
    if len(hexa) == 6:
        try:
            return int(hexa[0:2], 16), int(hexa[2:4], 16), int(hexa[4:6], 16)
        except ValueError:
            pass
    raise ValueError(f"can't read colour {text!r}; use a name ({', '.join(NAMED)}), #rrggbb, r,g,b or hue:DEG")


def mix(a: RGB, b: RGB, k: float) -> RGB:
    return tuple(round(x + (y - x) * k) for x, y in zip(a, b))


def scale(c: RGB, k: float) -> RGB:
    return tuple(round(v * k) for v in c)


def gradient(stops: list[RGB], n: int) -> list[RGB]:
    """`n` colours spread evenly through `stops` (one stop fills all n)."""
    if len(stops) == 1 or n == 1:
        return [stops[0]] * n
    out = []
    for i in range(n):
        pos = i / (n - 1) * (len(stops) - 1)
        j = min(int(pos), len(stops) - 2)
        out.append(mix(stops[j], stops[j + 1], pos - j))
    return out
