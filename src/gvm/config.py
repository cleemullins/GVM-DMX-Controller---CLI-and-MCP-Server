"""Rig description (gvm.toml): the DMX adapter and each tube's patch.

The file is found in this order: an explicit path, $GVM_CONFIG, ./gvm.toml, then the
per-user file (%APPDATA%\\gvm\\gvm.toml on Windows, ~/.config/gvm/gvm.toml elsewhere).
"""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .bd45r import BD45R, Mode
from .dmx import OpenDmx

TEMPLATE = """\
# GVM DMX rig. Each [[fixture]] must match that tube's own Set up menu:
#   CONTROL = DMX, DMX ADDR = address, DMX MODE = mode, DMX PIXEL = pixel.
# See docs/SETUP.md for the full setup guide.
#
# mode:  CCT&RGB | CCT&HSI | CCT | RGB | HSI | EFFECT | PIXEL FX
# pixel: LEDs per group -> 33 (whole tube), 11 (3 segments), 3 (11 segments), 1 (33 segments)
# Channels used = segments x channels per segment (CCT&RGB 7, CCT&HSI 6, RGB 4, CCT/HSI 3,
# EFFECT 5, PIXEL FX 9), so CCT&RGB with pixel 1 uses 231 channels.
#
# The tube's own pixel 1 is at the end away from its controls. reverse = true flips that so
# segment 1 is on the operator's left for every tube.

# driver "d2xx" (FTDI library, recommended): device = adapter serial number, "" = first adapter.
# driver "serial" (Windows COM port fallback): device = "COM3".
driver = "d2xx"
device = ""
fps = 25

[[fixture]]
name = "tube1"
address = 1
mode = "CCT&RGB"
pixel = 1
reverse = false

[[fixture]]
name = "tube2"
address = 232
mode = "CCT&RGB"
pixel = 1
reverse = false
"""


def user_dir(kind: str) -> Path:
    """Per-user folder for 'config' or 'state' files."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA" if kind == "config" else "LOCALAPPDATA") or Path.home()
    else:
        default = "~/.config" if kind == "config" else "~/.local/state"
        base = os.environ.get("XDG_CONFIG_HOME" if kind == "config" else "XDG_STATE_HOME") or default
    return Path(base).expanduser() / "gvm"


def user_config_path() -> Path:
    return user_dir("config") / "gvm.toml"


def default_state_path() -> Path:
    return Path(os.environ["GVM_STATE"]) if os.environ.get("GVM_STATE") else user_dir("state") / "universe.bin"


def find_config(explicit: Path | None = None) -> Path | None:
    candidates = [explicit] if explicit else [
        Path(os.environ["GVM_CONFIG"]) if os.environ.get("GVM_CONFIG") else None,
        Path("gvm.toml"),
        user_config_path(),
    ]
    for path in candidates:
        if path and path.is_file():
            return path
    if explicit:
        raise FileNotFoundError(f"config file {explicit} not found")
    return None


@dataclass
class FixtureConfig:
    name: str
    address: int
    mode: Mode
    pixel: int = 33
    reverse: bool = False

    @classmethod
    def parse(cls, spec: str) -> "FixtureConfig":
        """NAME:ADDRESS[:MODE[:PIXEL[:reverse]]], e.g. "tube1:1:CCT&RGB:1:reverse"."""
        parts = spec.split(":")
        if len(parts) < 2 or len(parts) > 5 or (len(parts) == 5 and parts[4].lower() != "reverse"):
            raise ValueError(f"fixture {spec!r} should look like NAME:ADDRESS[:MODE[:PIXEL[:reverse]]]")
        return cls(
            name=parts[0],
            address=int(parts[1]),
            mode=Mode.parse(parts[2]) if len(parts) > 2 else Mode.CCT_RGB,
            pixel=int(parts[3]) if len(parts) > 3 else 33,
            reverse=len(parts) == 5,
        )

    def spec(self) -> str:
        return f"{self.name}:{self.address}:{self.mode.label}:{self.pixel}" + (":reverse" if self.reverse else "")


@dataclass
class RigConfig:
    driver: str = "d2xx"
    device: str = ""
    fps: float = 25.0
    fixtures: list[FixtureConfig] = field(default_factory=list)
    source: Path | None = None

    @classmethod
    def load(cls, path: Path) -> "RigConfig":
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        fixtures = [
            FixtureConfig(
                name=f["name"],
                address=int(f["address"]),
                mode=Mode.parse(f.get("mode", "CCT&RGB")),
                pixel=int(f.get("pixel", 33)),
                reverse=bool(f.get("reverse", False)),
            )
            for f in data.get("fixture", [])
        ]
        return cls(driver=data.get("driver", "d2xx"), device=data.get("device", ""),
                   fps=float(data.get("fps", 25)), fixtures=fixtures, source=path)

    def build_fixtures(self, dmx: OpenDmx | None) -> list[BD45R]:
        """BD45R objects for the patch (dmx may be None just to inspect the layout)."""
        fixtures = [BD45R(dmx, f.address, f.mode, f.pixel, f.name, f.reverse) for f in self.fixtures]
        _check_overlaps(fixtures)
        return fixtures


class Rig:
    """An open DMX connection plus the tubes patched on it."""

    def __init__(self, config: RigConfig, initial: bytes = b""):
        config.build_fixtures(None)  # validate before touching the adapter
        try:
            self.dmx = OpenDmx(config.device, config.fps, config.driver, initial)
        except Exception as e:
            raise RuntimeError(
                f"couldn't open the DMX adapter ({config.driver} {config.device or 'first device'}): {e}. "
                "Is it plugged in, and is another program (or a running gvm effect) using it?") from e
        self.fixtures = config.build_fixtures(self.dmx)

    def select(self, names: list[str] | None) -> list[BD45R]:
        """Fixtures by name or 1-based index; all of them when `names` is empty."""
        if not names:
            return list(self.fixtures)
        chosen = []
        for name in names:
            match = [f for i, f in enumerate(self.fixtures, 1) if f.name == name or str(i) == name]
            if not match:
                raise ValueError(f"no fixture {name!r}; have {[f.name for f in self.fixtures]}")
            chosen.extend(match)
        return chosen

    def close(self) -> None:
        self.dmx.close()


def _check_overlaps(fixtures: list[BD45R]) -> None:
    ordered = sorted(fixtures, key=lambda f: f.address)
    for a, b in zip(ordered, ordered[1:]):
        if b.address <= a.last_channel:
            raise ValueError(f"{a.name} (channels {a.address}-{a.last_channel}) overlaps {b.name} at {b.address}")
