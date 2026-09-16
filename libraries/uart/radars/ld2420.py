"""Driver for the Hi-Link HLK-LD2420 radar module.

Implements command framing, REPORT mode and the 20 x 16 DEBUG Range-Doppler map.
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import List

from .base import RadarProtocolError, RadarUARTBase


class LD2420Mode(IntEnum):
    """Serial output modes supported by the LD2420."""
    DEBUG = 0x00
    REPORT = 0x04
    RUN = 0x64


class LD2420Parameter(IntEnum):
    """Common configuration parameter identifiers."""
    MIN_DISTANCE = 0x00
    MAX_DISTANCE = 0x01
    DELAY = 0x04


@dataclass(frozen=True)
class LD2420Report:
    """One LD2420 energy report."""
    result: int
    distance: int
    energy: List[int]

    @property
    def presence(self) -> bool:
        return self.result != 0


@dataclass(frozen=True)
class LD2420DebugMap:
    """20 x 16 Range-Doppler map."""
    values: List[List[int]]

    def __getitem__(self, item):
        return self.values[item]


class LD2420(RadarUARTBase):
    """HLK-LD2420 driver using a busio.UART-compatible interface."""

    REPORT_HEADER = b"\xF4\xF3\xF2\xF1"
    REPORT_FOOTER = b"\xF8\xF7\xF6\xF5"
    DEBUG_HEADER = b"\xAA\xBF\x10\x14"
    DEBUG_FOOTER = b"\xFD\xFC\xFB\xFA"

    def __init__(self, uart, *, debug=False, frame_timeout=1.0):
        super().__init__(uart, debug=debug, frame_timeout=frame_timeout)
        self.mode = LD2420Mode.RUN

    def enable_command_mode(self):
        """Enter command/configuration mode."""
        return self._require_success(self._command(0x00FF, self._u16(1)), "enable_command_mode")

    def disable_command_mode(self):
        """Leave command/configuration mode."""
        return self._require_success(self._command(0x00FE), "disable_command_mode")

    def get_version(self):
        """Read firmware version; returns ASCII when possible."""
        response = self._require_success(self._command(0x0000), "get_version")
        if len(response.data) < 2:
            return response.data
        length = self._from_u16(response.data[:2])
        raw = response.data[2:2 + length]
        try:
            return raw.decode("ascii")
        except UnicodeError:
            return raw

    def restart(self):
        """Restart the radar module."""
        return self._require_success(self._command(0x0068), "restart")

    def get_parameters(self, *parameters):
        """Read one or more uint32 configuration parameters."""
        if not parameters:
            raise ValueError("Debes indicar al menos un parámetro")
        payload = b"".join(self._u16(int(p)) for p in parameters)
        response = self._require_success(self._command(0x0008, payload), "get_parameters")
        if len(response.data) < 4 * len(parameters):
            raise RadarProtocolError("Respuesta de parámetros incompleta")
        return {p: self._from_u32(response.data[i*4:i*4+4]) for i, p in enumerate(parameters)}

    def set_parameters(self, parameters):
        """Write one or more parameter:value pairs."""
        if not parameters:
            raise ValueError("parameters no puede estar vacío")
        payload = bytearray()
        for parameter, value in parameters.items():
            payload += self._u16(int(parameter))
            payload += self._u32(int(value))
        return self._require_success(self._command(0x0007, payload), "set_parameters")

    def set_distance_range(self, minimum, maximum):
        """Set minimum/maximum active gates, both in range 0..15."""
        if not 0 <= minimum <= 15 or not 0 <= maximum <= 15:
            raise ValueError("minimum y maximum deben estar entre 0 y 15")
        if minimum > maximum:
            raise ValueError("minimum no puede ser mayor que maximum")
        return self.set_parameters({
            LD2420Parameter.MIN_DISTANCE: minimum,
            LD2420Parameter.MAX_DISTANCE: maximum,
        })

    def get_distance_range(self):
        """Return (minimum_gate, maximum_gate)."""
        values = self.get_parameters(LD2420Parameter.MIN_DISTANCE, LD2420Parameter.MAX_DISTANCE)
        return values[LD2420Parameter.MIN_DISTANCE], values[LD2420Parameter.MAX_DISTANCE]

    def set_delay(self, value):
        """Set delay/hold parameter in range 0..255."""
        if not 0 <= value <= 255:
            raise ValueError("value debe estar entre 0 y 255")
        return self.set_parameters({LD2420Parameter.DELAY: value})

    def get_delay(self):
        return self.get_parameters(LD2420Parameter.DELAY)[LD2420Parameter.DELAY]

    @staticmethod
    def _gate(gate):
        gate = int(gate)
        if not 0 <= gate <= 15:
            raise ValueError("gate debe estar entre 0 y 15")
        return gate

    @staticmethod
    def _threshold(value):
        value = int(value)
        if not 0 <= value <= 65536:
            raise ValueError("threshold debe estar entre 0 y 65536")
        return value

    def set_trigger(self, gate, value):
        return self.set_parameters({0x10 + self._gate(gate): self._threshold(value)})

    def get_trigger(self, gate):
        p = 0x10 + self._gate(gate)
        return self.get_parameters(p)[p]

    def set_hold(self, gate, value):
        return self.set_parameters({0x20 + self._gate(gate): self._threshold(value)})

    def get_hold(self, gate):
        p = 0x20 + self._gate(gate)
        return self.get_parameters(p)[p]

    def set_trigger_thresholds(self, values):
        values = list(values)
        if len(values) != 16:
            raise ValueError("Se requieren exactamente 16 thresholds")
        return self.set_parameters({0x10+i: self._threshold(v) for i, v in enumerate(values)})

    def set_hold_thresholds(self, values):
        values = list(values)
        if len(values) != 16:
            raise ValueError("Se requieren exactamente 16 thresholds")
        return self.set_parameters({0x20+i: self._threshold(v) for i, v in enumerate(values)})

    def set_mode(self, mode):
        """Set DEBUG, REPORT or RUN serial-output mode."""
        mode = LD2420Mode(mode)
        response = self._require_success(
            self._command(0x0012, self._u16(0x0000) + self._u32(mode)),
            "set_mode",
        )
        self.mode = mode
        return response

    def read_report(self):
        """Read one REPORT frame: result + distance + 16 uint16 gate energies."""
        self._wait_for_header(self.REPORT_HEADER)
        length = self._from_u16(self._read_exactly(2))
        if length != 0x23:
            raise RadarProtocolError(f"Longitud REPORT LD2420 inesperada: {length}")
        data = self._read_exactly(length)
        if self._read_exactly(4) != self.REPORT_FOOTER:
            raise RadarProtocolError("Footer REPORT LD2420 inválido")
        result = data[0]
        distance = self._from_u16(data[1:3])
        energy = [self._from_u16(data[3+2*i:5+2*i]) for i in range(16)]
        return LD2420Report(result, distance, energy)

    def read_debug_map(self):
        """Read one 20 x 16 DEBUG Range-Doppler map."""
        self._wait_for_header(self.DEBUG_HEADER)
        raw = self._read_exactly(20 * 16 * 4)
        if self._read_exactly(4) != self.DEBUG_FOOTER:
            raise RadarProtocolError("Footer DEBUG LD2420 inválido")
        values, idx = [], 0
        for _ in range(20):
            row = []
            for _ in range(16):
                row.append(self._from_u32(raw[idx:idx+4]))
                idx += 4
            values.append(row)
        return LD2420DebugMap(values)

    def readline(self):
        """Read one text line in RUN mode."""
        raw = self.uart.readline()
        if raw is None:
            return None
        try:
            return raw.decode("ascii").strip()
        except UnicodeError:
            return raw

    def read(self):
        """Homogeneous read method; return type depends on self.mode."""
        if self.mode == LD2420Mode.RUN:
            return self.readline()
        if self.mode == LD2420Mode.REPORT:
            return self.read_report()
        return self.read_debug_map()
