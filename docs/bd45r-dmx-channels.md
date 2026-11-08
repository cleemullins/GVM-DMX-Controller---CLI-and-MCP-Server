# GVM PRO-BD45R DMX channels

Condensed from the official *GVM-PRO-BD45R DMX Channel Table V1*
(<https://gvmled.com/wp-content/uploads/2025/12/GVM-PRO-BD45R-DMX%E9%80%9A%E9%81%93%E8%A1%A8%E3%80%90%E8%8B%B1%E6%96%87%E3%80%91V1-CP.pdf>)
and the PRO-BD25R/BD45R user manual
(<https://gvmled.com/wp-content/uploads/2025/12/%E6%A3%92%E7%81%AFGVM-PRO-BD25R-BD45R%E8%AF%B4%E6%98%8E%E4%B9%A6%E3%80%90%E8%8B%B1%E6%96%87%E3%80%91V0.pdf>).

## Verified on the real tubes (2026-11-07)

DSD TECH SH-RS09B through FTDI D2XX, both tubes at DMX PIXEL 33:

- **CCT&RGB:** intensity ramps 0-100%, CCT white at 5600 K, RGB hue sweep (`gvm fx cycle`), on both tubes.
- **PIXEL FX (built-in, `gvm hwfx`):** all six effects (Rainbow, Meteor, Wave, BlockGame, PingPong, Rolling with COLORS=HSI),
  speed 1-10, direction left/right, single-colour and foreground/background HUE/SAT parameters.
- **CCT&RGB, DMX PIXEL 1** (tube 1 at 1, tube 2 at 232): all 66 pixels at 100% / 5600 K light evenly.
- **Signal loss:** the tubes hold the last values received when DMX stops.
- **Pixel order:** pixel 1 is at the end away from the control panel; pixel 33 is at the control end.
- Not tested yet: EFFECT mode, CCT&HSI.
- The XLR-to-RJ45 adapter must follow the ESTA pinout (see README); an audio-wired one made the tubes flicker
  or ignore DMX.

## Setting up the light

In the light's **Set up** menu (press MODE until it appears, TAB moves between items, +/- changes them):

| Item | Meaning |
|---|---|
| CONTROL | `Master` (app/buttons) or `DMX`. Must be `DMX`; the app cannot control the light then. |
| DMX ADDR | Start channel, 1-512. |
| DMX MODE | Which channel layout below (CCT&RGB, CCT&HSI, CCT, RGB, HSI, EFFECT, PIXEL FX). |
| DMX PIXEL | LEDs per controllable group: 33, 11, 3 or 1. |

The tube has 33 pixels, so DMX PIXEL picks how many independent **segments** the layout repeats for:

| DMX PIXEL | Segments | CCT&RGB | CCT&HSI | RGB | CCT | HSI |
|---|---|---|---|---|---|---|
| 33 | 1 | 7 ch | 6 ch | 4 ch | 3 ch | 3 ch |
| 11 | 3 | 21 | 18 | 12 | 9 | 9 |
| 3 | 11 | 77 | 66 | 44 | 33 | 33 |
| 1 | 33 | 231 | 198 | 132 | 99 | 99 |

EFFECT (5 ch) and PIXEL FX (9 ch) always control the whole tube.

## Per-segment layouts

All channels are 8-bit, 0-255 across the stated range.

| Mode | Channels (in order, repeated per segment) |
|---|---|
| CCT&RGB | INT 0-100%, CCT 2700-10000 K, GM -50..50, CCT<->RGB crossfade, R, G, B |
| CCT&HSI | INT, CCT, GM, CCT<->HSI crossfade, HUE 0-360°, SAT 0-100% |
| CCT | INT, CCT, GM |
| RGB | INT, R, G, B |
| HSI | INT, HUE, SAT |

The crossfade channel blends between the white (CCT) and colour halves of the layout.

## EFFECT

| Ch | Function | Values |
|---|---|---|
| 1 | Intensity | 0-255 = 0-100% |
| 2 | Effect type | 0-9 Off, 10 Lightning, 20 CCT Loop, 30 Candle, 40 Bad Bulb, 50 TV, 60 Paparazzi, 70 Explosion, 80 Pulsing, 90 Disco, 100 Cop Car, 110 Party, 120-129 Hue Loop, 130-255 reserved (each band 10 wide) |
| 3 | Loop / stop | 0-127 loop, 128-255 stop |
| 4 | Speed | 0-9 = 1 … 90-99 = 10, 100-255 reserved |
| 5 | Parameter | CCT for Lightning, Candle, Bad Bulb, TV, Paparazzi, Explosion, Pulsing; SAT for Disco, Party, Hue Loop; unused for CCT Loop |

## PIXEL FX

| Ch | Function | Values |
|---|---|---|
| 1 | Intensity | 0-100% |
| 2 | Effect | 0-9 Rolling, 10 Rainbow, 20 BlockGame, 30 PingPong, 40 Wave, 50 Meteor, 60+ reserved |
| 3 | Status | 0-127 stop, 128-255 run (note: opposite sense to EFFECT ch 3) |
| 4 | Speed | as EFFECT ch 4 |
| 5 | Direction | 0-127 left, 128-255 right |
| 6-9 | Effect parameters | see below |

| Effect | Ch 6 | Ch 7 | Ch 8 | Ch 9 |
|---|---|---|---|---|
| Rolling | Colours: 0-4 CCT, 5-9 HSI, then 5-wide bands for 2…33 colours (165-169 = 33) | Rolling pixels: 5-wide bands for 1…33 (160-164 = 33) | CCT (Colours=CCT) / HUE (HSI) / HUE min (2-33) | GM (CCT) / SAT (HSI) / HUE max (2-33) |
| Rainbow | – | – | – | – |
| BlockGame, PingPong, Wave | Foreground HUE | Foreground SAT | Background HUE | Background SAT |
| Meteor | HUE | SAT | – | – |
