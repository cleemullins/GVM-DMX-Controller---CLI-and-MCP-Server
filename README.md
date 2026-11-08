# GVM DMX Controller: CLI and MCP Server

Control **GVM PRO-BD45R** 48" RGB LED tube lights over **DMX512** from a laptop, with a
command-line tool (`gvm`) and a local **MCP server** so Claude (or any MCP client) can run the
lights: "make the tubes warm white at 40%", "run a slow cyan meteor", "paint a sunset gradient".

- White light 2700–10000 K with green/magenta, solid colours (names, hex, RGB, hue), HSI
- **Per-pixel control**: each tube is 33 individually addressable pixels
- Gradients and exact per-pixel painting
- Software versions of all six GVM pixel effects (rolling, rainbow, blockgame, pingpong, wave,
  meteor), plus rig effects across tubes (colour cycle, chase, table ping pong)
- Works with cheap FTDI "Open DMX" USB cables (tested with the DSD TECH SH-RS09B)
- The tubes hold their last look, so static commands set it and exit. Effects stream until stopped.
- Every rig setting (adapter, addresses, modes, pixel layout, orientation) comes from a config file
  **or** command-line options / MCP tool parameters

> **New here? Read the [setup guide](docs/SETUP.md) first.** It covers the wiring, the XLR-to-RJ45
> pinout (the most common reason nothing works), the settings on each tube, install, first tests,
> connecting Claude, and troubleshooting.
>
> GVM's own documents: the **[BD45R DMX channel table (PDF)][gvm-dmx]** and the
> **[BD25R / BD45R user manual (PDF)][gvm-manual]**. Cable pinouts: **[Wiring and pinouts](#wiring-and-pinouts)**.
> More under [Reference documents](#reference-documents).

## Contents

- [How it fits together](#how-it-fits-together)
- [Wiring and pinouts](#wiring-and-pinouts)
- [Quick start](#quick-start)
- [CLI reference](#cli-reference)
- [MCP server](#mcp-server)
- [Configuration](#configuration)
- [Effects](#effects)
- [Python library](#python-library)
- [Development](#development)
- [Project layout](#project-layout)
- [Reference documents](#reference-documents)

## How it fits together

```
 Claude / MCP client ──stdio──▶ gvm mcp ─┐
                                         ├─▶ Controller ─▶ FTDI D2XX ─▶ USB-DMX cable ─▶ XLR→RJ45 ─▶ Tube 1 ─▶ Tube 2 ─▶ terminator
 You ─────────────────────────▶ gvm ... ─┘        │
                                                  └─ universe state file (last values of all 512 channels)
```

- **Open DMX adapter:** the SH-RS09B is a bare USB-to-RS485 bridge, so this software generates
  the DMX signal itself (break, mark-after-break, 512 slots at 250 kbaud, about 25 frames/s).
- **The tubes hold their last values** when DMX stops, so a static command opens the adapter, sends
  briefly and closes it again.
- **Shared state:** the last universe is saved to a state file and restored on the next command,
  so the CLI and the MCP server can take turns, and changing one tube never resets another.

## Wiring and pinouts

```
Laptop USB ─ USB-DMX cable (XLR) ─ XLR→RJ45 DMX adapter ─▶ Tube 1 DMX IN
                                   Tube 1 DMX OUT ─ Cat5 ─▶ Tube 2 DMX IN ─ Tube 2 DMX OUT ─ terminator
```

The tubes' DMX jacks are RJ45, so the XLR end of the USB cable needs an adapter, and **the adapter
must be wired to the DMX-over-Cat5 standard (ANSI/ESTA E1.27-2)**. Many "XLR to RJ45" adapters
(audio types, and some sold for LED-strip controllers) use other pins. With one of those, the tubes
flicker or ignore DMX.

| Signal | 3-pin XLR | RJ45 pin | T568B wire colour |
|---|---|---|---|
| Data + | 3 | **1** | white/orange |
| Data − | 2 | **2** | orange |
| Common / ground | 1 | **7** (and optionally 8) | white/brown (brown) |

RJ45 pins are numbered 1–8 left to right with the gold contacts facing you, the clip at the back
and the cable hanging down. The full details are in the setup guide:
[wiring and pinouts](docs/SETUP.md#2-wiring-and-pinouts), including how to
[check an adapter with a multimeter](docs/SETUP.md#checking-an-adapter-with-a-multimeter), how to
build one, and connector genders. The standard itself is in the
[ANSI E1.27-2 wiring guide (PDF)][e127].

## Quick start

Hardware, wiring and tube settings are covered step by step in [docs/SETUP.md](docs/SETUP.md). In
short, set each tube's **Set up** menu to:

| | Tube 1 | Tube 2 |
|---|---|---|
| CONTROL | DMX | DMX |
| DMX MODE | CCT&RGB | CCT&RGB |
| DMX PIXEL | 1 | 1 |
| DMX ADDR | 1 | 232 |

Then install the software. It needs Python 3.11+ and the FTDI driver, which Windows installs
automatically for the cable.

```bash
git clone https://github.com/cleemullins/GVM-DMX-Controller---CLI-and-MCP-Server.git gvm
cd gvm
python -m pip install -e .
```

Check the adapter is seen and the patch looks right:

```bash
gvm ports
```

```bash
gvm info
```

Then try the lights:

```bash
gvm white 100 5600
```

```bash
gvm fx all
```

If `gvm` isn't found, use `python -m gvm` instead, or add Python's Scripts folder to PATH (see
[setup §5](docs/SETUP.md#5-install-the-software)).

## CLI reference

```
gvm [rig options] COMMAND [command options]
```

| Command | What it does | Example |
|---|---|---|
| `init` | Write a starter config to `%APPDATA%\gvm\gvm.toml` | `gvm init` |
| `info` | Show config source, state file, adapter, each tube's channels | `gvm info` |
| `ports` | List COM ports and FTDI adapters | `gvm ports` |
| `white` (`cct`) | White: intensity %, kelvin, `--gm` | `gvm white 40 3200 --gm 5` |
| `color` | Solid colour: name, `#rrggbb`, `r,g,b`, `hue:DEG[,SAT]` | `gvm color "#ff8800" -i 60` |
| `hsi` | Hue (°) and saturation (%) | `gvm hsi 200 80 -i 50` |
| `dim` | Intensity only, keep colour | `gvm dim 25` |
| `off` | Intensity to 0 | `gvm off -f tube2` |
| `paint` | Gradient along each tube (33 colours = one per pixel) | `gvm paint red yellow blue` |
| `fx` | Software effect; `fx list` describes them, `fx all` showcases them | `gvm fx meteor --color cyan --speed 8` |
| `ramp` | Test: fade white up and down | `gvm ramp --top 100 -f tube1` |
| `hwfx` | The tube's **built-in** effects (tube must be in EFFECT / PIXEL FX mode) | `gvm hwfx candle` |
| `raw` | Write absolute DMX channels | `gvm raw 1=255 2=128` |
| `shell` | Interactive prompt | `gvm shell` |
| `mcp` | Run the MCP server over stdio | `gvm mcp` |

**Targeting:** `-f/--fixture NAME` (repeatable; default all tubes) and `-s/--segment N`
(repeatable; 1–33, segment 1 = the operator's left).

**Rig options** override the config file. Put them before the command:

| Option | Meaning |
|---|---|
| `--config PATH` | Config file (default: `$GVM_CONFIG`, `./gvm.toml`, then per-user) |
| `--patch NAME:ADDR[:MODE[:PIXEL[:reverse]]]` | Define a tube, replacing the file's fixtures (repeatable) |
| `--driver d2xx\|serial` | DMX driver (`serial` uses the COM port) |
| `--device ID` | FTDI serial number (d2xx) or COM port (serial) |
| `--fps N` | DMX frame rate |
| `--state PATH` | Universe state file (default `%LOCALAPPDATA%\gvm\universe.bin` or `$GVM_STATE`) |
| `--hold S` | Seconds to send after a static command (default 0.3); `0` = until Ctrl+C |

```bash
gvm --patch "tube1:1:CCT&RGB:1:reverse" --patch "tube2:232:CCT&RGB:1" white 50
```

```bash
gvm --driver serial --device COM3 info
```

Run `gvm --help` or `gvm COMMAND --help` for every option.

## MCP server

`gvm mcp` runs a local MCP server over **stdio**: the client starts it as a subprocess, and no
network port is opened. It takes the same rig options as the CLI, e.g. `gvm --config PATH mcp`.

**Claude Code in this folder:** the repo's [`.mcp.json`](.mcp.json) registers it. Approve the
`gvm-lights` server when Claude Code asks.

**Claude Code anywhere:** make a per-user config first (`gvm init`, then edit it, or copy
`gvm.toml` to `%APPDATA%\gvm\gvm.toml`), then:

```bash
claude mcp add --scope user gvm-lights -- python -m gvm mcp
```

**Claude Desktop:** add to `claude_desktop_config.json` (Settings → Developer → Edit Config):

```json
{
  "mcpServers": {
    "gvm-lights": {
      "command": "python",
      "args": ["-m", "gvm", "--config", "C:\\git\\gvm\\gvm.toml", "mcp"]
    }
  }
}
```

### Tools

| Tool | Parameters | Does |
|---|---|---|
| `rig_info` | – | Tubes (names, channels, mode, segments, reverse), adapter, effect list, running effect |
| `set_white` | `intensity`, `kelvin`, `green_magenta`, `fixtures`, `segments` | White light |
| `set_color` | `color`, `intensity`, `fixtures`, `segments` | Solid colour |
| `set_hsi` | `hue`, `saturation`, `intensity`, `fixtures`, `segments` | Colour by hue |
| `set_intensity` | `intensity`, `fixtures`, `segments` | Brightness only |
| `paint` | `colors` (stops, or one per segment), `intensity`, `fixtures` | Gradient / per-pixel colours |
| `lights_off` | `fixtures` | Off (stops any effect) |
| `start_effect` | `name`, `seconds` (0 = until stopped), `speed` 1–10, `intensity`, `color`, `background`, `colors`, `block`, `tail`, `wavelength`, `stagger`, `fixtures` | Background animation |
| `stop_effect` | – | Stop the running animation |
| `configure_rig` | `fixtures` (`NAME:ADDR[:MODE[:PIXEL[:reverse]]]` specs), `driver`, `device` | Change the patch for this session (file untouched) |
| `set_dmx_channels` | `values` {channel: value} | Raw DMX |

Static tools return as soon as the look is set. `start_effect` returns immediately and the
animation keeps running until `stop_effect`, another lighting tool, or its `seconds` run out.

Only one program can use the adapter at a time: while an MCP effect runs, CLI commands report the
adapter as busy.

## Configuration

`gvm.toml` (this repo's copy describes the reference rig: two tubes facing each other):

```toml
driver = "d2xx"        # "d2xx" (FTDI library, recommended) or "serial"
device = ""            # FTDI serial (from `gvm ports`) or COM port; "" = first adapter
fps = 25

[[fixture]]
name = "tube1"
address = 1            # = the tube's DMX ADDR
mode = "CCT&RGB"       # = DMX MODE: CCT&RGB | CCT&HSI | CCT | RGB | HSI | EFFECT | PIXEL FX
pixel = 1              # = DMX PIXEL: 33 (whole tube) | 11 | 3 | 1 (33 pixels)
reverse = true         # true if the tube's controls are on the operator's left

[[fixture]]
name = "tube2"
address = 232
mode = "CCT&RGB"
pixel = 1
reverse = false
```

Lookup order: `--config`, `$GVM_CONFIG`, `./gvm.toml`, `%APPDATA%\gvm\gvm.toml`
(`~/.config/gvm/gvm.toml` on Linux/macOS). See [setup §3](docs/SETUP.md#3-settings-on-each-tube)
for working out addresses for other layouts.

## Effects

`gvm fx list` / the `rig_info` tool lists them. All take `speed` 1–10 (5 = normal) and `seconds`
(0 = until stopped). Pixel effects need DMX PIXEL below 33.

| Effect | Kind | Options |
|---|---|---|
| `rolling` | pixel | `colors`, `block` (band width) |
| `rainbow` | pixel | – |
| `blockgame` | pixel | `color`, `background`, `block` |
| `pingpong` | pixel | `color`, `background`, `block` |
| `wave` | pixel | `color`, `background`, `wavelength` |
| `meteor` | pixel | `color`, `tail` |
| `cycle` | rig | `stagger` (seconds between tubes) |
| `chase` | rig | `color`, `block` |
| `table-pingpong` | rig | `colors` or `color`, `tail`. A ball circles between tubes facing each other |

```bash
gvm fx wave --color red --bg green --wavelength 8 --seconds 20
```

```bash
gvm fx cycle --stagger 10 --seconds 30
```

## Python library

```python
from pathlib import Path
from gvm import Controller, RigConfig
from gvm.animations import Options

ctl = Controller(RigConfig.load(Path("gvm.toml")))
ctl.white(60, 4300)
ctl.color((255, 0, 128), 40, fixtures=["tube2"])
ctl.paint([(255, 0, 0), (0, 0, 255)])
ctl.start("meteor", Options(color=(0, 255, 255), speed=7))   # background thread
ctl.stop()
```

The lower layers are `gvm.dmx.OpenDmx` (raw universe output) and `gvm.bd45r.BD45R` (the tube's
channel map). The channel chart is in [docs/bd45r-dmx-channels.md](docs/bd45r-dmx-channels.md).

## Development

```bash
python -m pip install -e ".[test]"
```

```bash
python -m pytest
```

The tests don't need hardware. CI runs them on every push (see `.github/workflows/tests.yml`).

## Project layout

| Path | Contents |
|---|---|
| `src/gvm/dmx.py` | DMX512 output through an FTDI Open DMX adapter (D2XX or COM port) |
| `src/gvm/bd45r.py` | BD45R channel layouts and value encoding |
| `src/gvm/config.py` | `gvm.toml` loading, config discovery, patch validation |
| `src/gvm/controller.py` | Shared engine for the CLI and MCP: sessions, saved state, background effects |
| `src/gvm/animations.py` | Software pixel and rig effects |
| `src/gvm/colors.py` | Colour parsing and gradients |
| `src/gvm/cli.py` | The `gvm` command |
| `src/gvm/mcp_server.py` | The MCP server |
| `docs/SETUP.md` | Setup guide: wiring, pinouts, tube settings, install, MCP, troubleshooting |
| `docs/bd45r-dmx-channels.md` | DMX channel reference and what was verified on real tubes |
| `gvm.toml` | Reference rig config |

## Reference documents

| Document | What's in it |
|---|---|
| [GVM PRO-BD45R DMX Channel Table V1 (PDF)][gvm-dmx] | Official channel layout for all 28 DMX modes: CCT&RGB, CCT&HSI, CCT, RGB, HSI at each DMX PIXEL setting, EFFECT and PIXEL FX values |
| [GVM PRO-BD25R / BD45R User Manual (PDF)][gvm-manual] | Controls and menus (Set up → CONTROL, DMX ADDR, DMX MODE, DMX PIXEL), modes, specifications, app pairing |
| [docs/bd45r-dmx-channels.md](docs/bd45r-dmx-channels.md) | This project's condensed version of the channel table, plus what was verified on real tubes |
| [docs/SETUP.md](docs/SETUP.md) | This project's setup guide |
| [docs/SETUP.md § Wiring and pinouts](docs/SETUP.md#2-wiring-and-pinouts) | XLR and RJ45 pinouts, the wiring chain, testing and building an adapter |
| [ANSI E1.27-2 DMX-over-Cat5 wiring guide (Pathway, PDF)][e127] | The RJ45 pinout the XLR-to-RJ45 adapter must follow |

[gvm-dmx]: https://gvmled.com/wp-content/uploads/2025/12/GVM-PRO-BD45R-DMX%E9%80%9A%E9%81%93%E8%A1%A8%E3%80%90%E8%8B%B1%E6%96%87%E3%80%91V1-CP.pdf
[gvm-manual]: https://gvmled.com/wp-content/uploads/2025/12/%E6%A3%92%E7%81%AFGVM-PRO-BD25R-BD45R%E8%AF%B4%E6%98%8E%E4%B9%A6%E3%80%90%E8%8B%B1%E6%96%87%E3%80%91V0.pdf
[e127]: https://pathway.acuitybrands.com/-/media/abl/pathway/files/resources/reference-guides/pathway-dmx-wiring-guide.pdf

## License

[MIT](LICENSE) © 2026 Chris Mullins. GVM and BD45R are trademarks of their owner; this project is
not affiliated with or endorsed by GVM.
