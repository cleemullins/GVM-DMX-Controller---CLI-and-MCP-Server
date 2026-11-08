# Setup guide

Everything needed to get GVM PRO-BD45R tubes running from a Windows laptop over DMX:
hardware, wiring and pinouts, the settings on each light, software install, first tests,
connecting the MCP server, and troubleshooting.

Contents

1. [What you need](#1-what-you-need)
2. [Wiring and pinouts](#2-wiring-and-pinouts)
3. [Settings on each tube](#3-settings-on-each-tube)
4. [Pixel order and `reverse`](#4-pixel-order-and-reverse)
5. [Install the software](#5-install-the-software)
6. [Configure the rig (`gvm.toml`)](#6-configure-the-rig-gvmtoml)
7. [First tests](#7-first-tests)
8. [Connect the MCP server](#8-connect-the-mcp-server)
9. [Troubleshooting](#9-troubleshooting)
10. [Reference](#10-reference)

---

## 1. What you need

| Item | Used here | Notes |
|---|---|---|
| Lights | 2 × GVM PRO-BD45R 48" RGB tubes | 33 pixels each; DMX IN and DMX OUT are RJ45 jacks |
| USB-to-DMX interface | DSD TECH SH-RS09B, 3 m: [the one used here (Amazon)](https://www.amazon.com/dp/B0F2MQZCWR), [maker's page](https://www.deshide.com/product-details_SH-RS09B.html) | FTDI FT232R "Open DMX" type; the laptop generates the DMX timing. DMX end is a **female** 3-pin XLR |
| XLR-to-RJ45 adapter | **must be wired for DMX (ESTA)**, see §2. Examples: [SIRS-E](https://sirs-e.us/products/rj45-xlr-female-male-dmx-cable) (choose **Male, 3 PIN**), [Event Horizon XLR-M to RJ45](https://eventhorizon-srv.com/shop/dmx-3pin-xlrm-rj45-cable-p-3545) (choose pinout **ESTA Standard (Pinout A)**) | Required pinout: XLR 3 → RJ45 1 (Data+), XLR 2 → RJ45 2 (Data−), XLR 1 → RJ45 7/8 (ground). **Male** XLR to mate with the SH-RS09B. Generic "audio" adapters are wired differently and do not work. Check with a meter |
| Cat5/Cat6 patch cable | tube 1 DMX OUT → tube 2 DMX IN | Any standard straight-through Ethernet cable |
| **DMX terminator (required)** | in the **last** tube's DMX OUT. [The one used here (Amazon)](https://www.amazon.com/dp/B07RVDK77Y) | 120 Ω across Data+ / Data−, RJ45 pins 1 and 2 (see below) |
| Laptop | Windows 11, Python 3.11+ | FTDI driver (installed automatically by Windows for the SH-RS09B) |

### The terminator is required

DMX is a 120 Ω bus, and the far end must be terminated. Without it the signal reflects back down
the line, and the last tube can flicker, glitch or ignore commands. The tubes' jacks are RJ45, so
use an **RJ45 DMX terminator**, or make one: solder a **120 Ω, ¼ W resistor between pins 1 and 2**
of an RJ45 plug (a patch cable cut a few cm from the plug works), insulate it, and plug it into the
last tube's DMX OUT. Only the last device in the chain gets a terminator.

## 2. Wiring and pinouts

### The chain

```
Laptop USB ─ SH-RS09B ─ XLR ─ [XLR→RJ45 DMX adapter] ─ RJ45 ─▶ Tube 1 DMX IN
                                                              Tube 1 DMX OUT ─ Cat5 ─▶ Tube 2 DMX IN
                                                                                     Tube 2 DMX OUT ─ 120 Ω terminator
```

- Always go into **DMX IN** and out of **DMX OUT**; the signal is one-way.
- Put the terminator on the **last** tube only.
- More tubes: keep daisy-chaining OUT → IN, terminator on the last.

### 3-pin XLR (DMX)

| XLR pin | Signal |
|---|---|
| 1 | Ground / shield (common) |
| 2 | Data − |
| 3 | Data + |

Pin numbers are moulded into the connector face. The SH-RS09B ends in a **female** 3-pin XLR, so
the adapter needs a **male** XLR.

### RJ45 (DMX over Cat5, ANSI/ESTA E1.27-2)

Hold the plug with the **gold contacts facing you, clip at the back, cable hanging down**:
pin 1 is on the left, pin 8 on the right.

| RJ45 pin | T568B wire colour | DMX signal | Connects to XLR pin |
|---|---|---|---|
| 1 | white/orange | Data + | **3** |
| 2 | orange | Data − | **2** |
| 3 | white/green | (Data 2 +, unused) | – |
| 6 | green | (Data 2 −, unused) | – |
| 7 | white/brown | Common (ground) | **1** |
| 8 | brown | Common for Data 2 (optional) | 1 (optional) |
| 4, 5 | blue pair | unused | – |

### Checking an adapter with a multimeter

1. Unplug the adapter from everything. Set the meter to continuity (beep) or the lowest Ω range.
2. Probe **XLR pin 3** and touch RJ45 contacts 1–8 in turn (a straightened paper clip helps reach
   the recessed contacts). It must beep on **pin 1** only.
3. **XLR pin 2** must beep on **RJ45 pin 2**; **XLR pin 1** on **RJ45 pin 7** (and optionally 8).

Many adapters sold as "DMX" for LED-strip controllers or audio snakes are wired differently. One
that was tested for this project mapped XLR 1/2/3 to RJ45 1/6/7. With it, tube 1 flickered at
random and ignored commands, because its data pins were floating. If no ready-made adapter shows
its pinout, build one: a male 3-pin XLR (screw-terminal "solderless" types are fine) and half a
Cat5 patch cable, wired per the table above.

## 3. Settings on each tube

On the tube: press **MODE** until the **Set up** menu appears, press **TAB** to move between items,
and **+ / −** to change the value.

| Menu item | What it does | Set to |
|---|---|---|
| CONTROL | `Master` = app / buttons, `DMX` = DMX only (the app no longer works) | **DMX** |
| DMX ADDR | First DMX channel the tube listens to (1–512) | see the table below |
| DMX MODE | Channel layout | **CCT&RGB** |
| DMX PIXEL | LEDs per controllable group: 33, 11, 3 or 1 | **1** |

`gvm setup` prints these values for whatever config is in use. In Claude, the MCP
`light_setup_guide` tool returns the same information.

### Recommended setup (used by this project)

| | Tube 1 | Tube 2 |
|---|---|---|
| CONTROL | DMX | DMX |
| DMX MODE | CCT&RGB | CCT&RGB |
| DMX PIXEL | 1 | 1 |
| DMX ADDR | **1** | **232** |
| Channels used | 1–231 | 232–462 |

**Why this layout:** with DMX PIXEL 1 every one of the 33 pixels has its own intensity, colour
temperature, green/magenta, white↔colour crossfade and RGB. That gives plain white, solid colours,
gradients and every software effect, so **the menus never need changing again**. The tube's own
built-in EFFECT / PIXEL FX modes are replaced by software versions (`gvm fx ...`).

### Working out addresses

Each tube uses *segments × channels-per-segment* channels starting at its DMX ADDR. The next
tube's address must be past the end of the previous one.

| DMX PIXEL | Segments | CCT&RGB (7/seg) | CCT&HSI (6) | RGB (4) | CCT or HSI (3) |
|---|---|---|---|---|---|
| 33 | 1 | 7 | 6 | 4 | 3 |
| 11 | 3 | 21 | 18 | 12 | 9 |
| 3 | 11 | 77 | 66 | 44 | 33 |
| 1 | 33 | **231** | 198 | 132 | 99 |

EFFECT mode uses 5 channels and PIXEL FX 9, always for the whole tube. Example: two tubes at
CCT&RGB / DMX PIXEL 1 → tube 1 at 1 (1–231), tube 2 at 232 (232–462). A third tube does not fit in
the same 512-channel universe at DMX PIXEL 1. Use DMX PIXEL 3 (77 channels each) for up to 6 tubes.

Some menu changes only take effect after moving to the next item: re-open the menu to confirm.

## 4. Multiple tubes: pixel order and `reverse`

This only matters with more than one tube. The tube numbers its pixels from the **end away from
the control panel** (pixel 1) to the **control end** (pixel 33). How the tubes are mounted decides
which way effects travel on each one. Setting `reverse` on some tubes makes effects flow across the
rig the way you want: in the same direction along a row, from one tube into the next, or around
tubes facing each other (`table-pingpong`).

The easiest way is to let the agent do it. Describe the layout, e.g. *"my tubes face each other
across a table; make effects travel around it"*. It runs a chase, asks which way it moves on each
tube, and sets `reverse` to match. By hand: run `gvm fx chase --seconds 6`, then set `reverse = true`
on any tube where the block runs the wrong way.

## 5. Install the software

1. **Python 3.11 or newer** from python.org or the Microsoft Store.
2. **FTDI driver**: Windows installs it automatically when the SH-RS09B is plugged in. It shows up
   in Device Manager as *USB Serial Port (COMx)*, and the D2XX library this project uses comes
   with it. Otherwise, get the "VCP driver" setup from ftdichip.com.
3. **This package**, from the project folder:

   ```bash
   python -m pip install -e .
   ```

   This installs `pyserial`, `ftd2xx` and the MCP SDK, and creates the `gvm` command.
4. **Put `gvm` on your PATH** (optional). pip prints a warning naming the Scripts folder, for example
   `C:\Users\<you>\AppData\Local\Python\pythoncore-3.15-64\Scripts`. Add that folder to your user
   PATH (Settings → System → About → Advanced system settings → Environment Variables), or keep
   using `python -m gvm` instead of `gvm`.
5. Check that the adapter is seen:

   ```bash
   gvm ports
   ```

   You should see the COM port and an `FTDI (d2xx) device: <serial>` line.

## 6. Configure the rig (`gvm.toml`)

`gvm` looks for its config in this order:

1. `--config PATH`
2. the `GVM_CONFIG` environment variable
3. `gvm.toml` in the current folder (this repo has one for the rig above)
4. the per-user file `%APPDATA%\gvm\gvm.toml`. `gvm init` writes a starter one there.

```toml
driver = "d2xx"        # or "serial" (then device = "COM3")
device = "BH011A6L"    # FTDI serial number from `gvm ports`; "" = first adapter
fps = 25

[[fixture]]
name = "tube1"
address = 1
mode = "CCT&RGB"
pixel = 1
reverse = true         # flip pixel order (§4)

[[fixture]]
name = "tube2"
address = 232
mode = "CCT&RGB"
pixel = 1
reverse = false
```

Every value can also be given on the command line, or to the MCP server at start-up, overriding
the file:

```bash
gvm --patch tube1:1:CCT&RGB:1:reverse --patch tube2:232:CCT&RGB:1 --device BH011A6L info
```

`gvm info` shows what is in effect: config source, state file, adapter, and each tube's channels.

The last DMX values are kept in `%LOCALAPPDATA%\gvm\universe.bin` (override with `GVM_STATE`), so
each command changes only what it targets, even when the CLI and the MCP server take turns.

## 7. First tests

Run these one at a time and watch the tubes:

| Command | Expect |
|---|---|
| `gvm ramp --top 100 -f tube1` | tube 1 fades up to full and back down |
| `gvm white 100 5600` | both tubes full white, end to end, no dark sections |
| `gvm color red -s 1 -f tube1` | one red pixel at your left end of tube 1 (otherwise fix `reverse`) |
| `gvm paint red blue` | red on your left fading to blue on your right, on both tubes |
| `gvm fx chase --seconds 6` | a white block runs left → right on both tubes |
| `gvm fx all` | all six pixel effects, 6 s each |
| `gvm off` | both dark |

## 8. Connect the MCP server

The README's [Using the MCP server](../README.md#using-the-mcp-server) section is the full guide:
prerequisites, Claude Code, Claude Desktop and other clients, checking the connection, example
requests, behaviour and troubleshooting. The essentials:

The server runs locally over stdio: the MCP client starts `gvm mcp` itself, and no network port
is opened.

**Claude Code, this project only.** The repo's `.mcp.json` registers it automatically when Claude
Code is opened in this folder (approve it when asked):

```json
{ "mcpServers": { "gvm-lights": { "command": "python", "args": ["-m", "gvm", "mcp"] } } }
```

**Claude Code, any folder.** Make sure a per-user config exists (`gvm init`, then edit it, or copy
this repo's `gvm.toml` to `%APPDATA%\gvm\gvm.toml`), then:

```bash
claude mcp add --scope user gvm-lights -- python -m gvm mcp
```

**Claude Desktop.** Settings → Developer → Edit Config, and add to `claude_desktop_config.json`:

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

The server takes the same rig options as the CLI (`--config`, `--patch`, `--driver`, `--device`)
before `mcp`. While connected, the `configure_rig` tool can change the patch for that session
without editing the file.

Only one program can use the adapter at a time. Static changes hold it for a fraction of a second,
but a running effect holds it until it stops: stop effects (`stop_effect`) before using the CLI, or
the CLI reports the adapter as busy.

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Tubes ignore everything; tube 1 flickers at random | XLR-to-RJ45 adapter not wired to ESTA | Check with a meter (§2); use or build a correct adapter |
| Last tube glitches or flickers, first is fine | Missing or wrong terminator | 120 Ω across RJ45 pins 1-2 in the last tube's DMX OUT (§1) |
| One tube ignores DMX but stays lit | That tube's CONTROL is still `Master` | Set CONTROL = DMX |
| A whole tube shows one colour when a single pixel was set | That tube's DMX PIXEL is 33, not 1 | Set DMX PIXEL = 1 (and check DMX ADDR) |
| Two tubes copy each other / interfere | Overlapping addresses | Use the address table in §3; `gvm info` lists each tube's channels |
| Effects run backwards on one tube | Pixel order | Toggle that tube's `reverse` (§4) |
| `couldn't open the DMX adapter` | Unplugged, or another program (a running effect, QLC+, ...) is using it | Stop the other program or effect; check `gvm ports` |
| `no config found` | No gvm.toml where `gvm` looks | `gvm init`, or `--config`, or run from this folder |
| `needs DMX PIXEL below 33` | Pixel effects need individual segments | Set DMX PIXEL = 1 (or 3/11) and update `gvm.toml` |
| One tube looks dimmer at the same setting | Power source (battery vs adapter) or unit variance | Compare on the same supply; trim with `-f` and a lower intensity on the brighter tube |
| `gvm` is not recognised | Scripts folder not on PATH | Use `python -m gvm`, or add the folder to PATH (§5) |

## 10. Reference

- Channel layouts, effect values and what was verified on the real tubes:
  [docs/bd45r-dmx-channels.md](bd45r-dmx-channels.md)
- GVM PRO-BD45R DMX channel table:
  <https://gvmled.com/wp-content/uploads/2025/12/GVM-PRO-BD45R-DMX%E9%80%9A%E9%81%93%E8%A1%A8%E3%80%90%E8%8B%B1%E6%96%87%E3%80%91V1-CP.pdf>
- GVM PRO-BD25R / BD45R user manual:
  <https://gvmled.com/wp-content/uploads/2025/12/%E6%A3%92%E7%81%AFGVM-PRO-BD25R-BD45R%E8%AF%B4%E6%98%8E%E4%B9%A6%E3%80%90%E8%8B%B1%E6%96%87%E3%80%91V0.pdf>
- DMX over Cat5 wiring (ANSI E1.27-2), Pathway:
  <https://pathway.acuitybrands.com/-/media/abl/pathway/files/resources/reference-guides/pathway-dmx-wiring-guide.pdf>
