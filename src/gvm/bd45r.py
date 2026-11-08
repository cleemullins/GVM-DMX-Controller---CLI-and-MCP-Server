"""Channel layout and value encoding for the GVM PRO-BD45R tube light.

Source: GVM-PRO-BD45R DMX Channel Table V1 (see docs/bd45r-dmx-channels.md).
Every channel in the table is 8-bit and spans its full range linearly over
0-255, e.g. CCT 0 = 2700 K and 255 = 10000 K.
"""

from __future__ import annotations

from enum import Enum

from .dmx import DMX_CHANNELS, OpenDmx

CCT_MIN_K = 2700
CCT_MAX_K = 10000
TUBE_PIXELS = 33

EFFECTS = [
    "off", "lightning", "cct loop", "candle", "bad bulb", "tv", "paparazzi",
    "explosion", "pulsing", "disco", "cop car", "party", "hue loop",
]
# Channel 5 of EFFECT mode is CCT for these effects and saturation for SAT_EFFECTS.
CCT_EFFECTS = {"lightning", "candle", "bad bulb", "tv", "paparazzi", "explosion", "pulsing"}
SAT_EFFECTS = {"disco", "party", "hue loop"}

PIXEL_FX = ["rolling", "rainbow", "blockgame", "pingpong", "wave", "meteor"]


class Mode(Enum):
    """DMX MODE menu setting -> channel names for one controllable segment."""

    CCT_RGB = ("CCT&RGB", ("int", "cct", "gm", "xfade", "r", "g", "b"))
    CCT_HSI = ("CCT&HSI", ("int", "cct", "gm", "xfade", "hue", "sat"))
    CCT = ("CCT", ("int", "cct", "gm"))
    RGB = ("RGB", ("int", "r", "g", "b"))
    HSI = ("HSI", ("int", "hue", "sat"))
    EFFECT = ("EFFECT", ("int", "effect", "stop", "speed", "param"))
    PIXEL_FX = ("PIXEL FX", ("int", "fx", "run", "speed", "dir", "p1", "p2", "p3", "p4"))

    def __init__(self, label: str, channels: tuple[str, ...]):
        self.label = label
        self.channels = channels

    @classmethod
    def parse(cls, text: str) -> "Mode":
        key = text.strip().upper().replace(" ", "").replace("_", "").replace("&", "")
        for mode in cls:
            if mode.label.replace(" ", "").replace("&", "") == key or mode.name.replace("_", "") == key:
                return mode
        raise ValueError(f"unknown DMX mode {text!r}; expected one of {[m.label for m in cls]}")


# DMX PIXEL menu value (LEDs per group) -> number of independently controlled segments.
PIXEL_SEGMENTS = {33: 1, 11: 3, 3: 11, 1: 33}


def percent(value: float) -> int:
    return _scale(value, 0, 100)


def kelvin(value: float) -> int:
    return _scale(value, CCT_MIN_K, CCT_MAX_K)


def green_magenta(value: float) -> int:
    return _scale(value, -50, 50)


def hue(value: float) -> int:
    return _scale(value, 0, 360)


def speed(value: int) -> int:
    """Speed 1-10 -> the middle of its 10-wide band."""
    if not 1 <= value <= 10:
        raise ValueError(f"speed {value} is outside 1..10")
    return (value - 1) * 10 + 5


def _scale(value: float, low: float, high: float) -> int:
    if not low <= value <= high:
        raise ValueError(f"{value} is outside {low}..{high}")
    return round((value - low) * 255 / (high - low))


class BD45R:
    """One tube, patched at `address` with the DMX MODE / DMX PIXEL set on the light."""

    def __init__(self, dmx: OpenDmx, address: int, mode: Mode = Mode.CCT_RGB, pixel: int = 33, name: str = "",
                 reverse: bool = False):
        if mode in (Mode.EFFECT, Mode.PIXEL_FX):
            pixel = 33  # effect modes always address the whole tube
        if pixel not in PIXEL_SEGMENTS:
            raise ValueError(f"DMX PIXEL must be one of {sorted(PIXEL_SEGMENTS)}, not {pixel}")
        self.dmx = dmx
        self.address = address
        self.mode = mode
        self.pixel = pixel
        self.name = name or f"BD45R@{address}"
        # The tube numbers its pixels from the end away from the controls; `reverse`
        # flips segment numbering so segment 1 can be whichever end suits the room.
        self.reverse = reverse
        if address < 1 or self.last_channel > DMX_CHANNELS:
            raise ValueError(f"{self.name} needs channels {address}..{self.last_channel}, beyond 1..{DMX_CHANNELS}")

    def menu_settings(self) -> dict[str, str]:
        """What the tube's own Set up menu must show for this patch to work."""
        settings = {"CONTROL": "DMX", "DMX ADDR": str(self.address), "DMX MODE": self.mode.label}
        if self.mode not in (Mode.EFFECT, Mode.PIXEL_FX):
            settings["DMX PIXEL"] = str(self.pixel)
        return settings

    @property
    def segments(self) -> int:
        return PIXEL_SEGMENTS[self.pixel]

    @property
    def footprint(self) -> int:
        return self.segments * len(self.mode.channels)

    @property
    def last_channel(self) -> int:
        return self.address + self.footprint - 1

    def channel(self, name: str, segment: int = 1) -> int:
        """Absolute DMX channel of `name` within `segment` (1-based)."""
        if name not in self.mode.channels:
            raise ValueError(f"{self.mode.label} mode has no {name!r} channel")
        if not 1 <= segment <= self.segments:
            raise ValueError(f"segment {segment} is outside 1..{self.segments}")
        if self.reverse:
            segment = self.segments + 1 - segment
        width = len(self.mode.channels)
        return self.address + (segment - 1) * width + self.mode.channels.index(name)

    def write(self, segment: int | None = None, **values: int) -> None:
        """Write raw 0-255 values by channel name to one segment, or all when segment is None."""
        targets = range(1, self.segments + 1) if segment is None else [segment]
        for seg in targets:
            for name, value in values.items():
                self.dmx.set(self.channel(name, seg), value)

    def cct(self, intensity: float, temperature: float = 5600, gm: float = 0, segment: int | None = None) -> None:
        values = dict(int=percent(intensity), cct=kelvin(temperature), gm=green_magenta(gm))
        if "xfade" in self.mode.channels:
            values["xfade"] = 0
        self.write(segment, **values)

    def rgb(self, intensity: float, r: int, g: int, b: int, segment: int | None = None) -> None:
        values = dict(int=percent(intensity), r=r, g=g, b=b)
        if "xfade" in self.mode.channels:
            values["xfade"] = 255
        self.write(segment, **values)

    def hsi(self, intensity: float, h: float, sat: float = 100, segment: int | None = None) -> None:
        values = dict(int=percent(intensity), hue=hue(h), sat=percent(sat))
        if "xfade" in self.mode.channels:
            values["xfade"] = 255
        self.write(segment, **values)

    def paint(self, intensity: float, colors: list[tuple[int, int, int]]) -> None:
        """One RGB colour per segment, in segment order (len(colors) must equal self.segments)."""
        if len(colors) != self.segments:
            raise ValueError(f"{self.name} has {self.segments} segments, got {len(colors)} colours")
        for seg, (r, g, b) in enumerate(colors, 1):
            self.rgb(intensity, r, g, b, segment=seg)

    def intensity(self, value: float, segment: int | None = None) -> None:
        self.write(segment, int=percent(value))

    def off(self) -> None:
        self.write(None, int=0)

    def effect(self, name: str, intensity: float = 100, spd: int = 5,
               temperature: float = 5600, sat: float = 100, running: bool = True) -> None:
        name = name.lower()
        if name not in EFFECTS:
            raise ValueError(f"unknown effect {name!r}; expected one of {EFFECTS}")
        if name in CCT_EFFECTS:
            param = kelvin(temperature)
        elif name in SAT_EFFECTS:
            param = percent(sat)
        else:
            param = 0
        # Channel 3 in EFFECT mode: 0-127 loop, 128-255 stop.
        self.write(None, int=percent(intensity), effect=EFFECTS.index(name) * 10 + 5,
                   stop=0 if running else 255, speed=speed(spd), param=param)

    def pixel_fx(self, name: str, intensity: float = 100, spd: int = 5, right: bool = False,
                 running: bool = True, params: tuple[int, int, int, int] = (0, 0, 0, 0)) -> None:
        """Pixel effect; `params` are raw values for channels 6-9, whose meaning depends on the effect."""
        name = name.lower()
        if name not in PIXEL_FX:
            raise ValueError(f"unknown pixel effect {name!r}; expected one of {PIXEL_FX}")
        p1, p2, p3, p4 = params
        # Channel 3 in PIXEL FX mode: 0-127 stop, 128-255 run (the reverse of EFFECT mode).
        self.write(None, int=percent(intensity), fx=PIXEL_FX.index(name) * 10 + 5,
                   run=255 if running else 0, speed=speed(spd), dir=255 if right else 0,
                   p1=p1, p2=p2, p3=p3, p4=p4)
