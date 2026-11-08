"""Local MCP server (stdio) exposing the tubes as tools.

Start it with `gvm mcp` (same config discovery and --patch/--driver/--device options as
the CLI). Static tools return once the look is set; effects run in the background until
`stop_effect`, another lighting tool, or their `seconds` run out.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from . import animations
from .bd45r import CCT_MAX_K, CCT_MIN_K
from .colors import NAMED, parse_color
from .config import FixtureConfig
from .controller import Controller

INSTRUCTIONS = f"""\
Controls GVM BD45R 48" RGB LED tubes over DMX. Call rig_info first to learn the tube names
and segment counts. Tubes keep their last look until changed. Colours accept a name
({", ".join(NAMED)}), #rrggbb, "r,g,b" or "hue:DEG[,SAT]". Intensities are 0-100 %,
colour temperature {CCT_MIN_K}-{CCT_MAX_K} K. Segment 1 is the operator's left end of a tube.
Effects run in the background until stop_effect or another lighting call."""

Fixtures = Annotated[list[str] | None, Field(description="tube names or numbers; omit for all tubes")]
Segments = Annotated[list[int] | None, Field(description="segment numbers (1 = operator's left); omit for whole tube")]
Intensity = Annotated[float, Field(ge=0, le=100, description="brightness in percent")]


def build_server(ctl: Controller):
    from mcp.server.mcpserver import MCPServer

    server = MCPServer("gvm-lights", instructions=INSTRUCTIONS)

    def status() -> dict[str, Any]:
        return {"running_effect": ctl.running(), "last_error": ctl.last_error}

    @server.tool()
    def rig_info() -> dict[str, Any]:
        """Describe the tubes (names, DMX channels, mode, segments), the adapter and any running effect."""
        return {
            "config": str(ctl.config.source or "set by configure_rig / --patch"),
            "adapter": {"driver": ctl.config.driver, "device": ctl.config.device or "first device"},
            "fixtures": [
                {"name": f.name, "channels": [f.address, f.last_channel], "mode": f.mode.label,
                 "dmx_pixel": f.pixel, "segments": f.segments, "reverse": f.reverse}
                for f in ctl.layout()
            ],
            "effects": animations.describe(),
            **status(),
        }

    @server.tool()
    def set_white(intensity: Intensity = 100,
                  kelvin: Annotated[float, Field(ge=CCT_MIN_K, le=CCT_MAX_K)] = 5600,
                  green_magenta: Annotated[float, Field(ge=-50, le=50, description="-50 green .. 50 magenta")] = 0,
                  fixtures: Fixtures = None, segments: Segments = None) -> dict[str, Any]:
        """Set white light by colour temperature."""
        return {"set": ctl.white(intensity, kelvin, green_magenta, fixtures, segments), **status()}

    @server.tool()
    def set_color(color: Annotated[str, Field(description="name, #rrggbb, r,g,b or hue:DEG[,SAT]")],
                  intensity: Intensity = 100, fixtures: Fixtures = None, segments: Segments = None) -> dict[str, Any]:
        """Set a solid colour."""
        return {"set": ctl.color(parse_color(color), intensity, fixtures, segments), **status()}

    @server.tool()
    def set_hsi(hue: Annotated[float, Field(ge=0, le=360)],
                saturation: Annotated[float, Field(ge=0, le=100)] = 100,
                intensity: Intensity = 100, fixtures: Fixtures = None, segments: Segments = None) -> dict[str, Any]:
        """Set colour by hue (degrees) and saturation (percent)."""
        return {"set": ctl.hsi(hue, saturation, intensity, fixtures, segments), **status()}

    @server.tool()
    def set_intensity(intensity: Intensity, fixtures: Fixtures = None, segments: Segments = None) -> dict[str, Any]:
        """Change brightness only, keeping the current colour."""
        return {"set": ctl.dim(intensity, fixtures, segments), **status()}

    @server.tool()
    def paint(colors: Annotated[list[str], Field(min_length=1, description=
              "colour stops spread along each tube from segment 1; give exactly one per segment for per-pixel control")],
              intensity: Intensity = 100, fixtures: Fixtures = None) -> dict[str, Any]:
        """Paint a gradient (or exact per-pixel colours) along the tubes."""
        return {"set": ctl.paint([parse_color(c) for c in colors], intensity, fixtures), **status()}

    @server.tool()
    def lights_off(fixtures: Fixtures = None) -> dict[str, Any]:
        """Turn tubes off (stops any running effect)."""
        return {"off": ctl.off(fixtures), **status()}

    @server.tool()
    def start_effect(name: Annotated[str, Field(description=f"one of {animations.NAMES}; see rig_info for details")],
                     seconds: Annotated[float, Field(ge=0, description="run time; 0 = until stopped")] = 0,
                     speed: Annotated[float, Field(ge=1, le=10, description="5 = normal")] = 5,
                     intensity: Intensity = 100,
                     color: str | None = None, background: str | None = None,
                     colors: list[str] | None = None,
                     block: Annotated[int | None, Field(ge=1, le=33)] = None,
                     tail: Annotated[int | None, Field(ge=0, le=33)] = None,
                     wavelength: Annotated[float | None, Field(gt=0)] = None,
                     stagger: Annotated[float, Field(ge=0, description="cycle: seconds between tubes")] = 0,
                     fixtures: Fixtures = None) -> dict[str, Any]:
        """Start a software animation in the background (replaces any running effect)."""
        options = animations.Options(
            seconds=seconds, intensity=intensity, speed=speed,
            color=parse_color(color) if color else None,
            background=parse_color(background) if background else None,
            colors=[parse_color(c) for c in colors] if colors else None,
            block=block, tail=tail, wavelength=wavelength, stagger=stagger)
        ctl.start(name, options, fixtures)
        return {"started": name, **status()}

    @server.tool()
    def stop_effect() -> dict[str, Any]:
        """Stop the running effect (the tubes go dark)."""
        return {"stopped": ctl.stop(), **status()}

    @server.tool()
    def configure_rig(fixtures: Annotated[list[str] | None, Field(description=
                      "tube specs NAME:ADDRESS[:MODE[:PIXEL[:reverse]]], e.g. tube1:1:CCT&RGB:1:reverse")] = None,
                      driver: Annotated[str | None, Field(description="d2xx or serial")] = None,
                      device: Annotated[str | None, Field(description="FTDI serial number or COM port")] = None
                      ) -> dict[str, Any]:
        """Change the patch or adapter for this server session (the config file is not modified).

        Use this when a tube's DMX ADDR, DMX MODE or DMX PIXEL has been changed on the light.
        """
        ctl.stop()
        if fixtures is not None:
            specs = [FixtureConfig.parse(s) for s in fixtures]
            old, ctl.config.fixtures = ctl.config.fixtures, specs
            try:
                ctl.layout()
            except ValueError:
                ctl.config.fixtures = old
                raise
        if driver is not None:
            if driver not in ("d2xx", "serial"):
                raise ValueError("driver must be 'd2xx' or 'serial'")
            ctl.config.driver = driver
        if device is not None:
            ctl.config.device = device
        return rig_info()

    @server.tool()
    def set_dmx_channels(values: Annotated[dict[str, int], Field(description=
                         "absolute DMX channel (1-512) -> value (0-255)")]) -> dict[str, Any]:
        """Low-level: write raw DMX channel values."""
        ctl.raw({int(k): int(v) for k, v in values.items()})
        return {"written": len(values), **status()}

    return server


def serve(ctl: Controller) -> None:
    server = build_server(ctl)
    try:
        server.run("stdio")
    finally:
        ctl.stop()
