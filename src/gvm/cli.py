"""`gvm` command-line tool: control GVM BD45R tubes over DMX.

Static commands (white, color, paint, off, ...) send briefly and exit; the tubes keep
the look. Effects stream until they finish or Ctrl+C. `gvm mcp` runs the MCP server.
"""

from __future__ import annotations

import argparse
import cmd
import shlex
import sys
import time
from pathlib import Path

from . import animations
from .bd45r import EFFECTS, PIXEL_FX
from .colors import parse_color
from .config import TEMPLATE, FixtureConfig, RigConfig, find_config, user_config_path
from .controller import Controller

EXAMPLES = """\
examples:
  gvm init                                   write a starter config to your user folder
  gvm info                                   show the patch and where the config came from
  gvm white 100 5600                         both tubes 100% at 5600 K
  gvm white 40 3200 --gm 5 -f tube2          one tube, warm with a touch of magenta
  gvm color red --intensity 60
  gvm color "#ff8800" -f tube1 -s 1 -s 2     two pixels of tube 1
  gvm hsi 200 80                             hue 200 deg, 80% saturation
  gvm paint red yellow blue                  gradient along each tube
  gvm off
  gvm fx list                                effects and what they do
  gvm fx meteor --color cyan --speed 8 --seconds 10
  gvm fx table-pingpong --seconds 30
  gvm fx all                                 showcase every pixel effect
  gvm --patch tube1:1:CCT&RGB:1:reverse --patch tube2:232:CCT&RGB:1 white 50
  gvm mcp                                    run the MCP server (stdio)

docs: README.md and docs/SETUP.md
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gvm", description="Control GVM BD45R LED tubes over DMX512.",
                                     epilog=EXAMPLES, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = parser.add_argument_group("rig (override the config file)")
    g.add_argument("--config", type=Path,
                   help="rig file; default: $GVM_CONFIG, ./gvm.toml, then the per-user config")
    g.add_argument("--patch", action="append", metavar="NAME:ADDR[:MODE[:PIXEL[:reverse]]]",
                   help="define a tube, replacing the file's fixtures (repeatable)")
    g.add_argument("--driver", choices=["d2xx", "serial"], help="DMX driver")
    g.add_argument("--device", help="FTDI serial number (d2xx) or COM port (serial)")
    g.add_argument("--fps", type=float, help="DMX frame rate")
    g.add_argument("--state", type=Path, help="universe state file (default: per-user, or $GVM_STATE)")
    g.add_argument("--hold", type=float, default=0.3,
                   help="seconds to keep sending after a static command (default 0.3; the tubes "
                        "hold the look afterwards); 0 = until Ctrl+C")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    for command in _COMMANDS:
        command(sub)
    return parser


def _target_args(p: argparse.ArgumentParser, segments: bool = True) -> None:
    p.add_argument("-f", "--fixture", action="append", metavar="NAME",
                   help="tube name or number (repeatable; default all)")
    if segments:
        p.add_argument("-s", "--segment", action="append", type=int, metavar="N",
                       help="segment/pixel 1-33 when DMX PIXEL splits the tube (repeatable; default all)")


def _init(sub):
    p = sub.add_parser("init", help="write a starter gvm.toml")
    p.add_argument("--path", type=Path, help=f"where to write it (default: {user_config_path()})")
    p.add_argument("--force", action="store_true", help="overwrite an existing file")


def _info(sub):
    sub.add_parser("info", help="show the patch, config file and state file")


def _ports(sub):
    sub.add_parser("ports", help="list serial ports and FTDI adapters")


def _white(sub):
    p = sub.add_parser("white", aliases=["cct"], help="white light: INTENSITY%% [KELVIN 2700-10000]")
    p.add_argument("intensity", type=float)
    p.add_argument("kelvin", type=float, nargs="?", default=5600)
    p.add_argument("--gm", type=float, default=0, help="green/magenta -50 (green) .. 50 (magenta)")
    _target_args(p)


def _color(sub):
    p = sub.add_parser("color", help="colour: name, #rrggbb, r,g,b or hue:DEG")
    p.add_argument("color", type=parse_color)
    p.add_argument("--intensity", "-i", type=float, default=100)
    _target_args(p)


def _hsi(sub):
    p = sub.add_parser("hsi", help="colour by HUE degrees [SAT%%]")
    p.add_argument("hue", type=float)
    p.add_argument("sat", type=float, nargs="?", default=100)
    p.add_argument("--intensity", "-i", type=float, default=100)
    _target_args(p)


def _dim(sub):
    p = sub.add_parser("dim", help="change intensity only, keeping the colour")
    p.add_argument("intensity", type=float)
    _target_args(p)


def _off(sub):
    p = sub.add_parser("off", help="intensity to 0")
    _target_args(p, segments=False)


def _paint(sub):
    p = sub.add_parser("paint", help="spread colours along each tube (gradient; 33 colours = one per pixel)")
    p.add_argument("colors", type=parse_color, nargs="+")
    p.add_argument("--intensity", "-i", type=float, default=100)
    _target_args(p, segments=False)


def _fx(sub):
    p = sub.add_parser("fx", help="software effect; 'list' describes them, 'all' showcases the pixel effects")
    p.add_argument("name", choices=["list", "all", *animations.NAMES])
    p.add_argument("--seconds", type=float, default=None,
                   help="run time; default 0 = until Ctrl+C (6 per effect for 'all')")
    p.add_argument("--speed", type=float, default=5, help="1-10, 5 = normal")
    p.add_argument("--intensity", "-i", type=float, default=100)
    p.add_argument("--color", type=parse_color, help="main/foreground colour")
    p.add_argument("--bg", type=parse_color, help="background colour")
    p.add_argument("--colors", type=parse_color, nargs="+", help="colour list (rolling, table-pingpong)")
    p.add_argument("--block", type=int, help="block/band width in segments")
    p.add_argument("--tail", type=int, help="tail length in segments (meteor, table-pingpong)")
    p.add_argument("--wavelength", type=float, help="wave length in segments (wave)")
    p.add_argument("--stagger", type=float, default=0, help="seconds between tubes starting (cycle)")
    _target_args(p, segments=False)


def _ramp(sub):
    p = sub.add_parser("ramp", help="test: fade white up to --top%% and back down")
    p.add_argument("--top", type=float, default=50)
    p.add_argument("--seconds", type=float, default=4, help="duration of each fade")
    _target_args(p, segments=False)


def _hwfx(sub):
    p = sub.add_parser("hwfx", help="the tube's built-in effects (tube must be in EFFECT or PIXEL FX mode)")
    p.add_argument("name", choices=[*EFFECTS, *PIXEL_FX])
    p.add_argument("--intensity", "-i", type=float, default=100)
    p.add_argument("--speed", type=int, default=5, help="1-10")
    p.add_argument("--kelvin", type=float, default=5600, help="EFFECT: colour temperature")
    p.add_argument("--sat", type=float, default=100, help="EFFECT: saturation")
    p.add_argument("--right", action="store_true", help="PIXEL FX: run right")
    p.add_argument("--params", type=int, nargs=4, default=[0, 0, 0, 0], metavar="V",
                   help="PIXEL FX: raw values for channels 6-9 (docs/bd45r-dmx-channels.md)")
    _target_args(p, segments=False)


def _raw(sub):
    p = sub.add_parser("raw", help="set absolute DMX channels: CHANNEL=VALUE ...")
    p.add_argument("pairs", nargs="+", metavar="CH=VAL")


def _shell(sub):
    sub.add_parser("shell", help="interactive prompt")


def _mcp(sub):
    sub.add_parser("mcp", help="run the MCP server over stdio (for Claude and other MCP clients)")


_COMMANDS = [_init, _info, _ports, _white, _color, _hsi, _dim, _off, _paint, _fx, _ramp, _hwfx, _raw,
             _shell, _mcp]


def load_config(args: argparse.Namespace) -> RigConfig:
    """The rig file (if any), with --patch / --driver / --device / --fps applied on top."""
    path = find_config(args.config)
    if path:
        config = RigConfig.load(path)
    elif args.patch:
        config = RigConfig()
    else:
        raise ValueError("no config found; run `gvm init`, pass --config, set GVM_CONFIG, or use --patch")
    if args.patch:
        config.fixtures = [FixtureConfig.parse(spec) for spec in args.patch]
    if args.driver:
        config.driver = args.driver
    if args.device is not None:
        config.device = args.device
    if args.fps:
        config.fps = args.fps
    return config


def _options(args: argparse.Namespace, seconds: float) -> animations.Options:
    return animations.Options(seconds=seconds, intensity=args.intensity, speed=args.speed, color=args.color,
                              background=args.bg, colors=args.colors, block=args.block, tail=args.tail,
                              wavelength=args.wavelength, stagger=args.stagger)


def run(args: argparse.Namespace, ctl: Controller) -> None:
    """Apply one parsed command."""
    c = args.command
    fixtures = getattr(args, "fixture", None)
    segments = getattr(args, "segment", None)
    if c == "info":
        src = ctl.config.source or "command line (--patch)"
        print(f"config: {src}\nstate:  {ctl.state_path}\nadapter: {ctl.config.driver} "
              f"{ctl.config.device or '(first device)'} at {ctl.config.fps:g} fps")
        for i, f in enumerate(ctl.layout(), 1):
            print(f"{i}. {f.name}: channels {f.address}-{f.last_channel}, {f.mode.label}, DMX PIXEL {f.pixel} "
                  f"({f.segments} segment{'s' * (f.segments > 1)}){', reversed' if f.reverse else ''}")
    elif c in ("white", "cct"):
        ctl.white(args.intensity, args.kelvin, args.gm, fixtures, segments)
    elif c == "color":
        ctl.color(args.color, args.intensity, fixtures, segments)
    elif c == "hsi":
        ctl.hsi(args.hue, args.sat, args.intensity, fixtures, segments)
    elif c == "dim":
        ctl.dim(args.intensity, fixtures, segments)
    elif c == "off":
        ctl.off(fixtures)
    elif c == "paint":
        ctl.paint(args.colors, args.intensity, fixtures)
    elif c == "fx":
        if args.name == "list":
            for name, doc in animations.describe().items():
                print(f"  {name:15} {doc}")
        elif args.name == "all":
            for name in animations.PIXEL_EFFECTS:
                print(f"{name}...", flush=True)
                ctl.run_effect(name, _options(args, args.seconds or 6), fixtures)
        else:
            if not args.seconds:
                print("Running; press Ctrl+C to stop.", flush=True)
            ctl.run_effect(args.name, _options(args, args.seconds or 0), fixtures)
    elif c == "ramp":
        with ctl.session(hold=0.1) as rig:
            _ramp_run(rig.select(fixtures), args.top, args.seconds)
    elif c == "hwfx":
        with ctl.session() as rig:
            for f in rig.select(fixtures):
                if args.name in EFFECTS:
                    f.effect(args.name, args.intensity, args.speed, args.kelvin, args.sat)
                else:
                    f.pixel_fx(args.name, args.intensity, args.speed, args.right, params=tuple(args.params))
    elif c == "raw":
        ctl.raw({int(ch): int(v) for ch, v in (pair.split("=") for pair in args.pairs)})


def _ramp_run(fixtures, top: float, seconds: float) -> None:
    for f in fixtures:
        if "cct" in f.mode.channels:
            f.cct(0, 5600)  # neutral white so only intensity changes
    steps = max(1, int(seconds * 20))
    levels = [top * i / steps for i in range(steps + 1)]
    for level in levels + levels[::-1]:
        for f in fixtures:
            f.intensity(level)
        print(f"\rintensity {level:5.1f}%", end="", flush=True)
        time.sleep(seconds / steps)
    print()


class Shell(cmd.Cmd):
    intro = "gvm shell: type commands as on the command line (e.g. `white 40 3200`), `help`, or `quit`."
    prompt = "gvm> "

    def __init__(self, ctl: Controller, parser: argparse.ArgumentParser):
        super().__init__()
        self.ctl = ctl
        self.parser = parser

    def default(self, line: str) -> None:
        try:
            args = self.parser.parse_args(shlex.split(line))
            if args.command in ("shell", "mcp", "init", "ports"):
                print("not available inside the shell")
                return
            run(args, self.ctl)
        except SystemExit:
            pass  # argparse already printed the message
        except (ValueError, RuntimeError) as e:
            print(f"error: {e}")

    def do_help(self, arg: str) -> None:
        self.default(f"{arg} -h" if arg else "-h")

    def do_quit(self, arg: str) -> bool:
        return True

    do_exit = do_quit
    do_EOF = do_quit

    def emptyline(self) -> None:
        pass


def _write_init(args: argparse.Namespace) -> int:
    path = args.path or user_config_path()
    if path.exists() and not args.force:
        print(f"{path} already exists (use --force to overwrite)", file=sys.stderr)
        return 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(TEMPLATE, encoding="utf-8")
    print(f"wrote {path}\nedit it to match each tube's Set up menu (see docs/SETUP.md), then run `gvm info`")
    return 0


def _list_ports() -> int:
    from serial.tools import list_ports

    for port in list_ports.comports():
        print(f"{port.device}: {port.description} [{port.hwid}]")
    try:
        import ftd2xx

        for serial in ftd2xx.listDevices() or []:
            print(f"FTDI (d2xx) device: {serial.decode()}")
    except Exception as e:  # D2XX library missing or no devices
        print(f"FTDI (d2xx): {e}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "init":
        return _write_init(args)
    if args.command == "ports":
        return _list_ports()
    try:
        config = load_config(args)
        config.build_fixtures(None)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    ctl = Controller(config, args.state, settle_seconds=args.hold)
    if args.command == "mcp":
        from .mcp_server import serve

        serve(ctl)
        return 0
    try:
        if args.command == "shell":
            Shell(ctl, parser).cmdloop()
        else:
            run(args, ctl)
    except KeyboardInterrupt:
        pass
    except (ValueError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
