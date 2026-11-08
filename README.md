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

> **New here?** Set each tube's menu first ([Settings on each light](#settings-on-each-light)), then
> read the [setup guide](docs/SETUP.md). It covers the wiring, the XLR-to-RJ45 pinout (the most
> common reason nothing works), install, first tests, connecting Claude, and troubleshooting.
>
> GVM's own documents: the **[BD45R DMX channel table (PDF)][gvm-dmx]** and the
> **[BD25R / BD45R user manual (PDF)][gvm-manual]**. Cable pinouts: **[Wiring and pinouts](#wiring-and-pinouts)**.
> More under [Reference documents](#reference-documents).

## Settings on each light

**Nothing works until each tube's own menu matches the software's patch.** On each BD45R, press
**MODE** until the **Set up** menu appears, press **TAB** to move between items and **+ / −** to
change them:

| Set up menu item | Tube 1 | Tube 2 | Why |
|---|---|---|---|
| **CONTROL** | **DMX** | **DMX** | In `Master` mode the tube ignores DMX. In DMX mode the GVM app stops working |
| **DMX ADDR** | **1** | **232** | Each tube uses 231 channels (1–231 and 232–462), so they mustn't overlap |
| **DMX MODE** | **CCT&RGB** | **CCT&RGB** | Per pixel: intensity, colour temperature, green/magenta, white↔colour crossfade, R, G, B |
| **DMX PIXEL** | **1** | **1** | Every one of the 33 pixels is controlled separately. All effects run in software, so the menus never need changing again |

### Using more than one tube

With more than one tube, effects can play across the whole rig, not just along each tube: a chase
that runs from one tube into the next, colors that travel down a row of tubes, or a ping-pong ball
that bounces between two tubes facing each other. For that, the software needs to know which way
each tube is mounted. Each tube's pixel order can be flipped with `reverse` (in `gvm.toml`, or
`:reverse` in a `--patch` spec).

You don't have to work this out yourself. Describe your layout to the agent, for example:

> "My two tubes face each other across a table. Set them up so effects travel around the table."

It runs a test pattern, asks what you see, and sets `reverse` for each tube to match.

**The software shows the same settings for the config in use**, so they can't drift apart:

- `gvm setup` prints the exact menu values per tube, the wiring chain, the adapter pinout and the
  terminator. `gvm info` adds a `set on the light:` line under each tube.
- The MCP server's `rig_info` tool includes `set_on_light` for each tube, and its
  `light_setup_guide` tool returns the full checklist, so Claude can walk you through it.

Other layouts (other modes, fewer pixels, more tubes) are in
[setup §3](docs/SETUP.md#3-settings-on-each-tube), including how to work out addresses.

| Symptom | Setting to check |
|---|---|
| A tube ignores everything but stays lit | CONTROL is still `Master` |
| Setting one pixel lights the whole tube | DMX PIXEL is 33, not 1 |
| Tubes copy each other or interfere | DMX ADDR overlaps (tube 2 must be 232) |
| Effects run the wrong way on one tube | `reverse` for that tube, or ask the agent to fix it |
| Tubes flicker or ignore DMX entirely | the XLR-to-RJ45 adapter's pinout, or a missing terminator (see [Wiring and pinouts](#wiring-and-pinouts)) |

## Contents

- [Settings on each light](#settings-on-each-light)
- [How it fits together](#how-it-fits-together)
- [Wiring and pinouts](#wiring-and-pinouts)
- [Quick start](#quick-start)
- [CLI reference](#cli-reference)
- [Using the MCP server](#using-the-mcp-server)
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

### Parts

| Part | Example | What to check |
|---|---|---|
| USB-to-DMX cable | **DSD TECH SH-RS09B, 3 m** ([the one used here, Amazon][dsd-amazon], [maker's page][dsd-official]) | FTDI FT232R "Open DMX" type. Its DMX end is a **female** 3-pin XLR |
| XLR-to-RJ45 DMX adapter | [SIRS-E RJ45-to-XLR DMX adapter][sirs-adapter]: choose **Male, 3 PIN** (RJ45-XLRM3-MK2), or [Event Horizon 3-pin XLR-M to RJ45][eh-adapter-m]: choose pinout **"ESTA Standard (Pinout A)"** | **Must be ESTA-wired: XLR 3 → RJ45 1 (Data+), XLR 2 → RJ45 2 (Data−), XLR 1 → RJ45 7/8 (ground).** Needs a **male** XLR to mate with the SH-RS09B. Check it with a meter before use (see below) |
| Cat5/Cat6 patch cable | any straight-through Ethernet cable | tube 1 DMX OUT → tube 2 DMX IN |
| **DMX terminator (required)** | [the one used here (Amazon)][terminator], or make one (below) | **120 Ω across Data+ and Data−** in the **last tube's DMX OUT**. RJ45 type, since the tube's jacks are RJ45 |

> **Don't skip the terminator.** DMX is a 120 Ω bus. Without a terminator at the far end, the
> signal reflects back down the cable, and the last tube can flicker, glitch or ignore commands,
> especially on longer runs. To make one, wire a 120 Ω, ¼ W resistor between **pins 1 and 2** of an
> RJ45 plug (or of a short patch cable cut off near the plug), and plug it into the last tube's
> DMX OUT. A 3-pin XLR terminator (120 Ω between XLR pins 2 and 3) only works if that end of the
> chain is XLR.

> **Adapter warning.** Sellers rarely publish pinouts, and many "XLR to RJ45" or "DMX" adapters
> (audio types, LED-strip controllers) are wired differently. One tested for this project mapped
> XLR 1/2/3 to RJ45 1/6/7, and the tubes only flickered. SIRS-E lists RJ45 pin 1 Data+ (white/orange),
> pin 2 Data− (orange) and pins 7/8 ground, matching XLR pins 3/2/1 by wire colour. Event Horizon
> builds to the pinout you select. Neither has been tested with these tubes, so check any adapter
> with a meter, or build one from the table below.

### Pinouts

```
Laptop USB ─ USB-DMX cable (XLR) ─ XLR→RJ45 DMX adapter ─▶ Tube 1 DMX IN
                                   Tube 1 DMX OUT ─ Cat5 ─▶ Tube 2 DMX IN ─ Tube 2 DMX OUT ─ 120 Ω terminator
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

1. Wire it up ([Wiring and pinouts](#wiring-and-pinouts)): USB cable → ESTA XLR-to-RJ45 adapter →
   tube 1 IN, tube 1 OUT → tube 2 IN, terminator in tube 2 OUT.
2. Set each tube's menu ([Settings on each light](#settings-on-each-light)): CONTROL **DMX**, DMX
   MODE **CCT&RGB**, DMX PIXEL **1**, DMX ADDR **1** and **232**.
3. Install the software. It needs Python 3.11+ and the FTDI driver, which Windows installs
automatically for the cable.

```bash
git clone https://github.com/cleemullins/GVM-DMX-Controller---CLI-and-MCP-Server.git gvm
cd gvm
python -m pip install -e .
```

Check the adapter is seen, and compare the settings the software expects with each tube's menu:

```bash
gvm ports
```

```bash
gvm setup
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

4. Connect Claude or another assistant: see [Using the MCP server](#using-the-mcp-server).

## CLI reference

```
gvm [rig options] COMMAND [command options]
```

| Command | What it does | Example |
|---|---|---|
| `setup` (`settings`) | Print the menu settings each tube needs (CONTROL / DMX ADDR / DMX MODE / DMX PIXEL), wiring, pinout, terminator | `gvm setup` |
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
(repeatable; 1–33).

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

## Using the MCP server

The MCP server lets Claude, or any other MCP-capable assistant, run the lights in plain language:
"set both tubes to 3200 K at 40%", "make tube 2 deep blue", "run a slow cyan meteor", "paint a
sunset gradient", "stop the effect". It runs **locally over stdio**: your MCP client starts
`gvm mcp` as a subprocess on your computer and talks to it over stdin/stdout. No network port is
opened, and nothing leaves the machine except what the assistant itself sends.

### 1. Before you start

1. **The lights work from the CLI.** Wiring, tube settings and install are done (see
   [Quick start](#quick-start)), and `gvm white 50 5600` lights both tubes. If the CLI can't drive
   the lights, the MCP server can't either.
2. **Find the Python that has `gvm` installed.** MCP clients often don't share your terminal's
   PATH, so use the full path to `python.exe` in client configs. To print it:

   ```bash
   python -c "import sys; print(sys.executable)"
   ```

   It looks like `C:\Users\<you>\AppData\Local\Python\pythoncore-3.15-64\python.exe`.
3. **Make the config findable.** The client starts the server in a folder of its choosing, so
   `./gvm.toml` may not be found. Either pass `--config` in the client config (as in the examples
   below), or put the config in the per-user location that `gvm` always checks:

   ```bash
   gvm init
   ```

   This writes `%APPDATA%\gvm\gvm.toml`. Edit it to match your tubes, or copy this repo's
   `gvm.toml` over it.
4. **Check the server starts.** This prints nothing and waits for a client; stop it with Ctrl+C.
   An error here, such as a missing config or a bad patch, is the same one a client would hit.

   ```bash
   python -m gvm mcp
   ```

### 2. Connect it to your assistant

The server is the command `python -m gvm [rig options] mcp`. Every client below just needs that
command and its arguments. Rig options (`--config`, `--patch`, `--driver`, `--device`) go
**before** `mcp`.

**Claude Code, in this repo.** Nothing to do: the repo's [`.mcp.json`](.mcp.json) declares the
`gvm-lights` server. Open Claude Code in this folder and approve the server when asked. It uses
`python` from your PATH and `./gvm.toml`.

**Claude Code, in any folder.** Register it once for your user (with a per-user config, step 1.3):

```bash
claude mcp add --scope user gvm-lights -- python -m gvm mcp
```

Use the full `python.exe` path instead of `python` if it isn't on your PATH, and add
`--config C:\path\to\gvm.toml` before `mcp` to pin a config.

**Claude Desktop.** Settings → Developer → **Edit Config** opens `claude_desktop_config.json`
(`%APPDATA%\Claude\` on Windows, `~/Library/Application Support/Claude/` on macOS). Add the server,
save, and **fully quit and reopen** Claude Desktop:

```json
{
  "mcpServers": {
    "gvm-lights": {
      "command": "C:\\Users\\<you>\\AppData\\Local\\Python\\pythoncore-3.15-64\\python.exe",
      "args": ["-m", "gvm", "--config", "C:\\git\\gvm\\gvm.toml", "mcp"]
    }
  }
}
```

**Other MCP clients** (VS Code, Cursor, Windsurf, Zed, and others) take the same command and
arguments in their own config file. For example, VS Code's `.vscode/mcp.json`:

```json
{
  "servers": {
    "gvm-lights": {
      "type": "stdio",
      "command": "C:\\path\\to\\python.exe",
      "args": ["-m", "gvm", "--config", "C:\\git\\gvm\\gvm.toml", "mcp"]
    }
  }
}
```

Any client that supports **stdio** MCP servers works. The server needs no environment variables or
API keys.

**Without an assistant.** The [MCP Inspector](https://github.com/modelcontextprotocol/inspector)
lets you call the tools by hand in a browser (needs Node.js):

```bash
npx @modelcontextprotocol/inspector python -m gvm mcp
```

### 3. Check it's connected

- **Claude Code:** run `/mcp`. `gvm-lights` should show as connected, with its 12 tools.
- **Claude Desktop:** the tools/connectors menu in the chat box should list `gvm-lights`.
- Then ask: **"What lights do you have?"** The assistant should call `rig_info` and report two tubes
  with 33 segments each, plus the menu settings each tube needs.

### 4. Things to ask

| Ask | The assistant uses |
|---|---|
| "Set both tubes to 100% at 5600 K." | `set_white` |
| "Make tube 2 warm, 3200 K at 30%, and leave tube 1 alone." | `set_white` with `fixtures` |
| "Turn tube 1 red and tube 2 blue." | `set_color` twice |
| "Dim everything to 20%." | `set_intensity` |
| "Light just the first five pixels of tube 1 in orange." | `set_color` with `segments: [1,2,3,4,5]` |
| "Paint a sunset gradient across both tubes." | `paint` with colour stops |
| "Run a slow cyan meteor." / "Do the table ping pong for 30 seconds." | `start_effect` |
| "Stop the effect." / "Lights off." | `stop_effect` / `lights_off` |
| "Tube 2 isn't responding. What should its menu say?" | `rig_info` / `light_setup_guide` |
| "I moved tube 2 to address 300." | `configure_rig` |

Colours can be names (`red`, `amber`, `teal`, …), `#rrggbb`, `r,g,b` or `hue:DEG[,SAT]`.
Intensities are 0–100 %. Segments are numbered 1–33 along each tube.

### 5. How it behaves

- **Static tools** (`set_white`, `set_color`, `set_hsi`, `set_intensity`, `paint`, `lights_off`)
  return as soon as the look is set. The tubes keep it after that, even when the server stops.
- **Effects run in the background.** `start_effect` returns immediately, and the animation keeps
  going until `stop_effect`, another lighting tool, its `seconds` running out, or the client
  closing the server. Then the tubes go dark.
- **One adapter, one user at a time.** A running effect holds the USB-DMX adapter, so stop it
  before using the `gvm` CLI or other DMX software, or they report the adapter as busy. Static
  changes hold it for only a fraction of a second.
- **Shared state.** The last values of all 512 channels are saved per user, so the MCP server and
  the CLI can take turns without resetting each other's tubes.
- **The patch can change mid-session.** If a tube's DMX ADDR, DMX MODE or DMX PIXEL is changed on
  the light, tell the assistant: it calls `configure_rig` for that session. Update `gvm.toml` to
  make the change permanent.

### 6. Tools

| Tool | Parameters | Does |
|---|---|---|
| `rig_info` | – | Tubes (names, channels, mode, segments, reverse, **`set_on_light`** menu values), adapter, effect list, running effect |
| `light_setup_guide` | – | Menu steps, the CONTROL / DMX ADDR / DMX MODE / DMX PIXEL values per tube, wiring, adapter pinout, terminator, orientation |
| `set_white` | `intensity`, `kelvin`, `green_magenta`, `fixtures`, `segments` | White light |
| `set_color` | `color`, `intensity`, `fixtures`, `segments` | Solid colour |
| `set_hsi` | `hue`, `saturation`, `intensity`, `fixtures`, `segments` | Colour by hue |
| `set_intensity` | `intensity`, `fixtures`, `segments` | Brightness only |
| `paint` | `colors` (stops, or one per segment), `intensity`, `fixtures` | Gradient / per-pixel colours |
| `lights_off` | `fixtures` | Off (stops any effect) |
| `start_effect` | `name`, `seconds` (0 = until stopped), `speed` 1–10, `intensity`, `color`, `background`, `colors`, `block`, `tail`, `wavelength`, `stagger`, `fixtures` | Background animation (see [Effects](#effects)) |
| `stop_effect` | – | Stop the running animation |
| `configure_rig` | `fixtures` (`NAME:ADDR[:MODE[:PIXEL[:reverse]]]` specs), `driver`, `device` | Change the patch for this session (file untouched) |
| `set_dmx_channels` | `values` {channel: value} | Raw DMX |

`fixtures` takes tube names or numbers (omit for all), and `segments` takes 1–33 (omit for the
whole tube).

### 7. Troubleshooting the MCP server

| Problem | Fix |
|---|---|
| Server shows as failed / disconnected | Run the client's exact command in a terminal (step 1.4) to see the error |
| `python` not found, or `No module named gvm` | Use the full path to the `python.exe` that ran `pip install -e .` (step 1.2) |
| `no config found` | Add `--config C:\path\to\gvm.toml` before `mcp`, or run `gvm init` (step 1.3) |
| Tools work but the lights don't change | Same checks as the CLI: try `gvm white 50`, then see [Settings on each light](#settings-on-each-light) and [Wiring and pinouts](#wiring-and-pinouts) |
| `couldn't open the DMX adapter` | A CLI command, another server instance or other DMX software has it. Stop that, or call `stop_effect` |
| New tools don't appear after updating | Restart the client (Claude Desktop: fully quit) so it restarts the server |

## Configuration

`gvm.toml` (this repo's copy is set up for two tubes):

```toml
driver = "d2xx"        # "d2xx" (FTDI library, recommended) or "serial"
device = ""            # FTDI serial (from `gvm ports`) or COM port; "" = first adapter
fps = 25

[[fixture]]
name = "tube1"
address = 1            # = the tube's DMX ADDR
mode = "CCT&RGB"       # = DMX MODE: CCT&RGB | CCT&HSI | CCT | RGB | HSI | EFFECT | PIXEL FX
pixel = 1              # = DMX PIXEL: 33 (whole tube) | 11 | 3 | 1 (33 pixels)
reverse = true         # flip pixel order (see "Using more than one tube")

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
| `table-pingpong` | rig | `colors` or `color`, `tail`. A ball bounces from tube to tube |

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
| `src/gvm/setup_guide.py` | Light settings / wiring checklist for `gvm setup` and `light_setup_guide` |
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
[dsd-official]: https://www.deshide.com/product-details_SH-RS09B.html
[dsd-amazon]: https://www.amazon.com/dp/B0F2MQZCWR
[terminator]: https://www.amazon.com/dp/B07RVDK77Y
[sirs-adapter]: https://sirs-e.us/products/rj45-xlr-female-male-dmx-cable
[eh-adapter-m]: https://eventhorizon-srv.com/shop/dmx-3pin-xlrm-rj45-cable-p-3545
[e127]: https://pathway.acuitybrands.com/-/media/abl/pathway/files/resources/reference-guides/pathway-dmx-wiring-guide.pdf

## License

[MIT](LICENSE) © 2026 Chris Mullins. GVM and BD45R are trademarks of their owner; this project is
not affiliated with or endorsed by GVM.
