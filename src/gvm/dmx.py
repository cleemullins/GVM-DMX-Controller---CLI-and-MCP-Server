"""DMX512 output through an FTDI-based "Open DMX" style USB adapter.

These adapters are a bare USB-to-RS485 bridge, so the computer has to generate
the DMX signal itself: a break, a mark-after-break, then the start code and up
to 512 channel slots at 250 kbaud 8N2, repeated continuously. A background
thread keeps resending the current universe so fixtures never see signal loss.

Two drivers are supported: FTDI's D2XX library (the default, and what most DMX
software uses, since it gives tight break timing) and the Windows COM port via
pyserial as a fallback.
"""

from __future__ import annotations

import threading
import time

DMX_CHANNELS = 512
_BAUD = 250_000
_SLOT_SECONDS = 11 / _BAUD  # 1 start + 8 data + 2 stop bits
_BREAK_SECONDS = 0.0002  # DMX needs >= 88 us; the OS sleeps at least this long


class _D2xxLink:
    def __init__(self, device: str):
        import ftd2xx

        # `device` is an FTDI serial number (e.g. "BH011A6L"); empty opens the first adapter.
        self._dev = ftd2xx.openEx(device.encode()) if device else ftd2xx.open(0)
        self._dev.resetDevice()
        self._dev.setBaudRate(_BAUD)
        self._dev.setDataCharacteristics(8, 2, 0)  # 8 bits, 2 stop bits, no parity
        self._dev.setFlowControl(0, 0, 0)
        self._dev.clrRts()
        self._dev.purge(3)
        self._dev.setLatencyTimer(2)

    def send(self, data: bytes) -> None:
        self._dev.setBreakOn()
        time.sleep(_BREAK_SECONDS)
        self._dev.setBreakOff()
        self._dev.write(data)

    def close(self) -> None:
        self._dev.close()


class _SerialLink:
    def __init__(self, port: str):
        import serial

        self._serial = serial.Serial(port, baudrate=_BAUD, bytesize=8, parity="N", stopbits=2,
                                     timeout=0, write_timeout=1)

    def send(self, data: bytes) -> None:
        self._serial.break_condition = True
        time.sleep(_BREAK_SECONDS)
        self._serial.break_condition = False
        self._serial.write(data)

    def close(self) -> None:
        self._serial.close()


class OpenDmx:
    """One DMX universe sent continuously through an Open DMX adapter.

    driver "d2xx": `device` is the adapter's FTDI serial number ("" = first adapter).
    driver "serial": `device` is a COM port such as "COM3".
    """

    def __init__(self, device: str = "", fps: float = 25.0, driver: str = "d2xx", initial: bytes = b""):
        if driver == "d2xx":
            self._link = _D2xxLink(device)
        elif driver == "serial":
            self._link = _SerialLink(device)
        else:
            raise ValueError(f"unknown DMX driver {driver!r}; expected 'd2xx' or 'serial'")
        # Slot 0 is the start code, which is 0 for ordinary dimmer data. `initial` restores
        # channels 1.. from a previous session so untouched fixtures keep their look.
        self._frame = bytearray(DMX_CHANNELS + 1)
        initial = initial[:DMX_CHANNELS]
        self._frame[1 : 1 + len(initial)] = initial
        self._lock = threading.Lock()
        # Never restart before the previous frame's slots have left the wire.
        self._interval = max(1.0 / fps, len(self._frame) * _SLOT_SECONDS + 0.002)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="dmx-output", daemon=True)
        self._thread.start()

    def set(self, channel: int, value: int) -> None:
        self.set_many(channel, [value])

    def set_many(self, start: int, values) -> None:
        """Set consecutive channels beginning at `start` (1-based)."""
        values = bytes(values)  # raises ValueError for anything outside 0-255
        if start < 1 or start + len(values) - 1 > DMX_CHANNELS:
            raise ValueError(f"channels {start}..{start + len(values) - 1} are outside 1..{DMX_CHANNELS}")
        with self._lock:
            self._frame[start : start + len(values)] = values

    def get(self, channel: int) -> int:
        if not 1 <= channel <= DMX_CHANNELS:
            raise ValueError(f"channel {channel} is outside 1..{DMX_CHANNELS}")
        with self._lock:
            return self._frame[channel]

    def snapshot(self) -> bytes:
        """Current values of channels 1-512."""
        with self._lock:
            return bytes(self._frame[1:])

    def blackout(self) -> None:
        with self._lock:
            self._frame[1:] = bytes(DMX_CHANNELS)

    def wait_frames(self, count: int = 3) -> None:
        """Sleep long enough for `count` frames to go out with the current values."""
        time.sleep(count * self._interval)

    @property
    def frame_seconds(self) -> float:
        return self._interval

    def close(self) -> None:
        self._stop.set()
        self._thread.join()
        self._link.close()

    def __enter__(self) -> "OpenDmx":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _run(self) -> None:
        while not self._stop.is_set():
            started = time.perf_counter()
            with self._lock:
                data = bytes(self._frame)
            self._link.send(data)
            self._stop.wait(max(0.0, self._interval - (time.perf_counter() - started)))
