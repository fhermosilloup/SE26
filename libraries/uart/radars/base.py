"""Common UART infrastructure for Hi-Link LD24xx radar drivers.

Drivers receive an already configured ``busio.UART`` object. This keeps the
protocol layer independent from the board/SoC and makes the same driver usable
with CircuitPython or Blinka.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CommandResponse:
    """Decoded acknowledgement returned by a radar command."""

    command: int
    ack_word: int
    status: int
    data: bytes
    raw: bytes

    @property
    def success(self) -> bool:
        """Return True when the command acknowledgement reports success."""
        return self.status == 0


class RadarProtocolError(RuntimeError):
    """Raised when a frame is malformed or does not match the protocol."""


class RadarTimeoutError(TimeoutError):
    """Raised when a complete radar frame is not received before timeout."""


class RadarUARTBase:
    """Base class shared by the LD24xx UART drivers.

    Args:
        uart: A ``busio.UART``-compatible object.
        debug: Print command frames in hexadecimal when True.
        frame_timeout: Maximum protocol-level read timeout in seconds.
    """

    COMMAND_HEADER = b"\xFD\xFC\xFB\xFA"
    COMMAND_FOOTER = b"\x04\x03\x02\x01"

    def __init__(self, uart, *, debug: bool = False, frame_timeout: float = 1.0):
        if uart is None:
            raise ValueError("uart no puede ser None")
        if frame_timeout <= 0:
            raise ValueError("frame_timeout debe ser mayor que 0")
        self.uart = uart
        self.debug = bool(debug)
        self.frame_timeout = float(frame_timeout)

    @staticmethod
    def _u16(value: int) -> bytes:
        """Encode an unsigned 16-bit integer in little-endian format."""
        value = int(value)
        if not 0 <= value <= 0xFFFF:
            raise ValueError("El valor debe caber en uint16")
        return value.to_bytes(2, "little", signed=False)

    @staticmethod
    def _u32(value: int) -> bytes:
        """Encode an unsigned 32-bit integer in little-endian format."""
        value = int(value)
        if not 0 <= value <= 0xFFFFFFFF:
            raise ValueError("El valor debe caber en uint32")
        return value.to_bytes(4, "little", signed=False)

    @staticmethod
    def _from_u16(data: bytes) -> int:
        if len(data) != 2:
            raise ValueError("Se requieren exactamente 2 bytes")
        return int.from_bytes(data, "little", signed=False)

    @staticmethod
    def _from_u32(data: bytes) -> int:
        if len(data) != 4:
            raise ValueError("Se requieren exactamente 4 bytes")
        return int.from_bytes(data, "little", signed=False)

    def _print_hex(self, label: str, data: bytes) -> None:
        if self.debug:
            print(label, " ".join(f"{byte:02X}" for byte in data))

    def clear(self) -> None:
        """Discard pending received bytes when the backend supports it."""
        reset = getattr(self.uart, "reset_input_buffer", None)
        if callable(reset):
            reset()
            return
        waiting = getattr(self.uart, "in_waiting", 0)
        if waiting:
            self.uart.read(waiting)

    def _read_exactly(self, size: int, *, timeout: Optional[float] = None) -> bytes:
        """Read exactly size bytes or raise RadarTimeoutError."""
        if size < 0:
            raise ValueError("size no puede ser negativo")
        if size == 0:
            return b""
        deadline = time.monotonic() + (self.frame_timeout if timeout is None else timeout)
        data = bytearray()
        while len(data) < size:
            if time.monotonic() >= deadline:
                raise RadarTimeoutError(
                    f"Se esperaban {size} bytes y se recibieron {len(data)}"
                )
            chunk = self.uart.read(size - len(data))
            if chunk:
                data.extend(chunk)
        return bytes(data)

    def _wait_for_header(self, header: bytes, *, timeout: Optional[float] = None) -> bytes:
        """Consume the stream until header is found."""
        if not header:
            raise ValueError("header no puede estar vacío")
        deadline = time.monotonic() + (self.frame_timeout if timeout is None else timeout)
        matched = 0
        while matched < len(header):
            if time.monotonic() >= deadline:
                raise RadarTimeoutError(f"No se encontró el header {header.hex(' ')}")
            raw = self.uart.read(1)
            if not raw:
                continue
            value = raw[0]
            if value == header[matched]:
                matched += 1
            else:
                matched = 1 if value == header[0] else 0
        return header

    def _build_command(self, command: int, data: bytes = b"") -> bytes:
        """Build a standard Hi-Link command frame."""
        payload = self._u16(command) + bytes(data)
        return self.COMMAND_HEADER + self._u16(len(payload)) + payload + self.COMMAND_FOOTER

    def _read_command_response(self) -> CommandResponse:
        """Read and decode a standard Hi-Link ACK frame."""
        self._wait_for_header(self.COMMAND_HEADER)
        length_raw = self._read_exactly(2)
        length = self._from_u16(length_raw)
        if length < 4:
            raise RadarProtocolError(f"ACK demasiado corto: {length} bytes")
        payload = self._read_exactly(length)
        footer = self._read_exactly(4)
        if footer != self.COMMAND_FOOTER:
            raise RadarProtocolError(f"Footer ACK inválido: {footer.hex(' ')}")
        raw = self.COMMAND_HEADER + length_raw + payload + footer
        self._print_hex("RX:", raw)
        ack_word = self._from_u16(payload[0:2])
        status = self._from_u16(payload[2:4])
        return CommandResponse(
            command=ack_word & 0x00FF,
            ack_word=ack_word,
            status=status,
            data=payload[4:],
            raw=raw,
        )

    def _command(self, command: int, data: bytes = b"", *, clear_input: bool = True,
                 expect_response: bool = True):
        """Send a command and optionally wait for its ACK."""
        frame = self._build_command(command, data)
        if clear_input:
            self.clear()
        self._print_hex("TX:", frame)
        written = self.uart.write(frame)
        if written is not None and written != len(frame):
            raise RadarProtocolError(f"UART escribió {written} de {len(frame)} bytes")
        if not expect_response:
            return None
        return self._read_command_response()

    @staticmethod
    def _require_success(response: CommandResponse, operation: str) -> CommandResponse:
        if not response.success:
            raise RadarProtocolError(
                f"{operation}: el radar respondió status=0x{response.status:04X}"
            )
        return response

    def enable_command_mode(self):
        raise NotImplementedError

    def disable_command_mode(self):
        raise NotImplementedError

    def get_version(self):
        raise NotImplementedError

    def restart(self):
        raise NotImplementedError

    def read(self):
        """Read one model-specific measurement/report object."""
        raise NotImplementedError
