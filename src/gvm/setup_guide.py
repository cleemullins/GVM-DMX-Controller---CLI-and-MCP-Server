"""The physical setup checklist, generated for the current patch.

Shared by `gvm setup` and the MCP `light_setup_guide` tool so both always describe the
same settings as the config in use.
"""

from __future__ import annotations

from .bd45r import BD45R

MENU_STEPS = [
    "On the tube, press MODE until the Set up menu appears.",
    "Press TAB to move between items and + / - to change the value.",
    "Set CONTROL to DMX (in Master mode the tube ignores DMX; the GVM app stops working in DMX mode).",
    "Set DMX ADDR, DMX MODE and DMX PIXEL to the values below.",
    "Re-open the menu to confirm the values stuck.",
]

WIRING = [
    "Laptop USB -> DSD TECH SH-RS09B (FTDI 'Open DMX', female 3-pin XLR end)",
    "-> XLR-to-RJ45 DMX adapter (male XLR, ESTA-wired) -> tube 1 DMX IN",
    "-> tube 1 DMX OUT -> Cat5 patch cable -> tube 2 DMX IN (repeat for more tubes)",
    "-> last tube's DMX OUT: 120 ohm DMX terminator (resistor across RJ45 pins 1 and 2). Required.",
]

PINOUT = [
    {"signal": "Data +", "xlr_pin": 3, "rj45_pin": "1", "t568b": "white/orange"},
    {"signal": "Data -", "xlr_pin": 2, "rj45_pin": "2", "t568b": "orange"},
    {"signal": "Ground", "xlr_pin": 1, "rj45_pin": "7 (and 8)", "t568b": "white/brown (brown)"},
]

ORIENTATION = ("Multiple tubes: pixel 1 is at the end away from a tube's controls. Set reverse = true on "
               "tubes that should run the other way so effects flow across the rig (run `gvm fx chase` to "
               "check, or ask the agent to set it up from a description of the layout).")


def guide(fixtures: list[BD45R]) -> dict:
    return {
        "menu_steps": MENU_STEPS,
        "tubes": [{"name": f.name, "set_on_light": f.menu_settings(), "uses_channels": [f.address, f.last_channel],
                   "segments": f.segments, "reverse": f.reverse} for f in fixtures],
        "wiring": WIRING,
        "xlr_to_rj45_pinout": PINOUT,
        "orientation": ORIENTATION,
        "docs": "docs/SETUP.md",
    }


def render_text(fixtures: list[BD45R]) -> str:
    lines = ["Settings on each light", "======================", ""]
    lines += [f"{i}. {step}" for i, step in enumerate(MENU_STEPS, 1)]
    lines.append("")
    keys = ["CONTROL", "DMX ADDR", "DMX MODE", "DMX PIXEL"]
    width = max(10, *(len(f.name) for f in fixtures))
    lines.append(f"  {'':{width}}  " + "  ".join(f"{k:10}" for k in keys))
    for f in fixtures:
        s = f.menu_settings()
        lines.append(f"  {f.name:{width}}  " + "  ".join(f"{s.get(k, '-'):10}" for k in keys))
    lines.append("")
    for f in fixtures:
        lines.append(f"  {f.name}: channels {f.address}-{f.last_channel}, {f.segments} segment"
                     f"{'s' * (f.segments > 1)}, reverse = {str(f.reverse).lower()}")
    lines += ["", ORIENTATION, "", "Wiring", "======", ""]
    lines += [f"  {w}" for w in WIRING]
    lines += ["", "XLR-to-RJ45 adapter pinout (ANSI/ESTA E1.27-2)", ""]
    lines += [f"  {p['signal']:7} XLR {p['xlr_pin']}  ->  RJ45 {p['rj45_pin']:10} ({p['t568b']})" for p in PINOUT]
    lines += ["", "Full guide: docs/SETUP.md"]
    return "\n".join(lines)
