# CLAUDE.md

Guidance for AI agents working in this repo. Humans: start with [README.md](README.md) and
[docs/SETUP.md](docs/SETUP.md).

## What this is

A controller for **GVM PRO-BD45R** 48" RGB LED tubes over **DMX512**: a Python library, the `gvm`
CLI, and a local stdio **MCP server** (`gvm mcp`, registered as `gvm-lights`). It's usually used
together with a camera MCP server (Nikon) and edelkrone's motion-control MCP server / SDK. See
[Working with camera and motion servers](#working-with-camera-and-motion-servers).

Reference rig (the repo's `gvm.toml`):
- 2 tubes on one DMX line.
- Each tube's menu: CONTROL **DMX**, DMX MODE **CCT&RGB**, DMX PIXEL **1** (33 pixels each), DMX ADDR **1** and **232**.
- Adapter: DSD TECH SH-RS09B (FTDI FT232R "Open DMX"), driven through FTDI D2XX.

## Getting it working on a machine

Do these in order and confirm each before moving on.

1. **Python 3.11+**. Run `python --version`.
2. **Install:** `python -m pip install -e ".[test]"`, then `python -m pytest -q` (no hardware needed).
3. **Adapter:** `python -m gvm ports` should list a COM port and an `FTDI (d2xx) device`. If not,
   the cable is unplugged or the FTDI driver is missing.
4. **Physical setup (the user does this; you can't).** Show them `python -m gvm setup`, which
   prints each tube's required menu values, the wiring chain, the XLR-to-RJ45 pinout and the
   terminator. Ask them to confirm each tube's menu.
5. **Live test, one tube at a time:** `python -m gvm ramp --top 100 -f tube1`, then ask what they
   saw. Then `-f tube2`. Then `python -m gvm white 100 5600`.
6. **MCP:** `.mcp.json` runs `python -m gvm mcp`. Check that the `python` on PATH is the one with
   `gvm` installed (`python -c "import gvm"`). If `gvm` lives in a venv, register the server with
   that interpreter's full path (`claude mcp add ...`) rather than committing a machine-specific
   path to `.mcp.json`. Verify with `/mcp`, then call `rig_info`.

## Working with the user on the lights

- **You can't see the lights.** After anything that changes them, say exactly what you sent and
  what they should see, then ask, in plain chat, what actually happened.
- **One test at a time,** usually one tube at a time. Don't chain several visual tests before
  getting an answer.
- **The tubes hold their last look** when DMX stops. Static commands send briefly and exit.
- **Effects** (`gvm fx ...`, MCP `start_effect`) run until stopped. Always stop them (`stop_effect`,
  `lights_off`, Ctrl+C) and say when one is still running.
- **Only one program can open the adapter.** A running MCP effect makes CLI commands fail with
  "couldn't open the DMX adapter". Stop the effect first.

## When the lights misbehave

Check the hardware first, in this order. Every real failure so far has been hardware or menu
settings, not code.

| Symptom | Cause |
|---|---|
| Tubes ignore DMX or flicker randomly | XLR-to-RJ45 adapter not ESTA-wired (needs XLR 3 → RJ45 1, 2 → 2, 1 → 7/8). Have the user check with a meter (SETUP §2) |
| One tube ignores DMX but stays lit | That tube's CONTROL is `Master` |
| Setting one pixel lights a whole tube | That tube's DMX PIXEL is 33, not 1 |
| Tubes interfere | Overlapping DMX ADDR (`gvm info` shows each tube's channels) |
| Last tube glitches | Missing 120 Ω terminator in its DMX OUT |
| Effects run the wrong way on one tube | `reverse`: run `gvm fx chase --seconds 6`, ask which way it moved, flip that tube |

## Code map

| File | Role |
|---|---|
| `src/gvm/dmx.py` | `OpenDmx`: background thread resending the 512-channel universe (D2XX or COM port) |
| `src/gvm/bd45r.py` | `BD45R`: channel layout per DMX MODE / DMX PIXEL, value encoding, `menu_settings()` |
| `src/gvm/config.py` | `gvm.toml` loading, config discovery, `--patch` specs, overlap checks |
| `src/gvm/controller.py` | **The single entry point for the CLI and MCP**: opens the adapter per operation, saves/restores universe state, runs background effects |
| `src/gvm/animations.py` | Software effects. Add new ones to `PIXEL_EFFECTS` or `RIG_EFFECTS` |
| `src/gvm/setup_guide.py` | Light settings / wiring checklist (`gvm setup`, MCP `light_setup_guide`) |
| `src/gvm/cli.py`, `src/gvm/mcp_server.py` | Thin front ends over `Controller` |

Conventions:
- **Keep the CLI and MCP in step.** A new capability goes into `Controller` (or `animations`), then
  gets both a CLI command and an MCP tool.
- **Nothing in the MCP path may print to stdout**, since stdout carries the stdio protocol.
- **Light settings, wiring and pinouts appear in three places:** README "Settings on each light",
  `docs/SETUP.md` and `setup_guide.py`. Change them together.
- Tests must not need hardware (use the `FakeDmx` pattern in `tests/`). Run `python -m pytest -q`.
- **Don't commit machine-specific values** (adapter serial numbers, absolute paths) to `gvm.toml` or
  `.mcp.json`.
- Channel facts come from GVM's DMX table; see `docs/bd45r-dmx-channels.md`, including what has been
  verified on real tubes.

## Working with camera and motion servers

Each device has its own MCP server: this one (`gvm-lights`), the camera (Nikon), and edelkrone
(motion). Coordinate them like this:

- **Set the light first, then capture.** Static looks hold with no adapter connection, so they're
  stable during exposures.
- **Match the camera's white balance** to the tubes' kelvin when using white light.
- **Effects run in the background**, so a slider move or video recording can start right after
  `start_effect`. Stop the effect when the shot ends.
- **For frame-by-frame work** (turnarounds, time-lapse, stop-motion): change the light → move →
  wait for motion to settle → capture. Use static looks, not effects, between frames.
- **edelkrone moves real hardware.** Call its `get_sdk_info` first, follow its safety rules, and
  confirm move ranges with the user before the first run.
- Example combined prompts are in the README section
  [Using with a camera and motion control](README.md#using-with-a-camera-and-motion-control).
