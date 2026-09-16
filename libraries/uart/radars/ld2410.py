"""Driver for the Hi-Link HLK-LD2410 / LD2410B / LD2410C style protocol.

LD2410S and LD2410D use different protocols and are intentionally not aliases of
this class.
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import List, Optional

from .base import RadarProtocolError, RadarUARTBase


class LD2410Mode(IntEnum):
    BASIC = 0
    ENGINEERING = 1


class LD2410TargetState(IntEnum):
    NONE = 0x00
    MOVING = 0x01
    STATIONARY = 0x02
    BOTH = 0x03


@dataclass(frozen=True)
class LD2410Report:
    """Basic cyclic target report."""
    state: LD2410TargetState
    moving_distance_cm: int
    moving_energy: int
    stationary_distance_cm: int
    stationary_energy: int
    detection_distance_cm: int

    @property
    def presence(self):
        return self.state != LD2410TargetState.NONE

    @property
    def moving(self):
        return self.state in (LD2410TargetState.MOVING, LD2410TargetState.BOTH)

    @property
    def stationary(self):
        return self.state in (LD2410TargetState.STATIONARY, LD2410TargetState.BOTH)


@dataclass(frozen=True)
class LD2410EngineeringReport(LD2410Report):
    """Engineering report with per-gate energies."""
    max_moving_gate: int
    max_stationary_gate: int
    moving_gate_energy: List[int]
    stationary_gate_energy: List[int]
    light: Optional[int] = None
    out_pin: Optional[int] = None


class LD2410(RadarUARTBase):
    """HLK-LD2410 driver using a busio.UART-compatible object."""

    REPORT_HEADER = b"\xF4\xF3\xF2\xF1"
    REPORT_FOOTER = b"\xF8\xF7\xF6\xF5"

    def __init__(self, uart, *, debug=False, frame_timeout=1.0):
        super().__init__(uart, debug=debug, frame_timeout=frame_timeout)
        self.mode = LD2410Mode.BASIC

    def enable_command_mode(self):
        return self._require_success(self._command(0x00FF, self._u16(1)), "enable_command_mode")

    def disable_command_mode(self):
        return self._require_success(self._command(0x00FE), "disable_command_mode")

    def get_version(self):
        """Return parsed firmware fields when the ACK contains the common 8-byte layout."""
        response = self._require_success(self._command(0x00A0), "get_version")
        data = response.data
        if len(data) >= 8:
            return {
                "type": self._from_u16(data[0:2]),
                "major": data[2],
                "minor": data[3],
                "bugfix": self._from_u32(data[4:8]),
                "raw": data,
            }
        return data

    def restart(self):
        return self._require_success(self._command(0x00A3), "restart")

    def enable_engineering_mode(self):
        response = self._require_success(self._command(0x0062), "enable_engineering_mode")
        self.mode = LD2410Mode.ENGINEERING
        return response

    def disable_engineering_mode(self):
        response = self._require_success(self._command(0x0063), "disable_engineering_mode")
        self.mode = LD2410Mode.BASIC
        return response

    def set_mode(self, mode):
        """Select BASIC or ENGINEERING cyclic reports."""
        mode = LD2410Mode(mode)
        return self.enable_engineering_mode() if mode == LD2410Mode.ENGINEERING else self.disable_engineering_mode()

    def set_distance_range(self, max_moving_gate, max_stationary_gate, timeout_s):
        """Configure maximum moving/static gates and no-target timeout."""
        if not 0 <= max_moving_gate <= 8:
            raise ValueError("max_moving_gate debe estar entre 0 y 8")
        if not 0 <= max_stationary_gate <= 8:
            raise ValueError("max_stationary_gate debe estar entre 0 y 8")
        if not 0 <= timeout_s <= 0xFFFF:
            raise ValueError("timeout_s debe caber en uint16")
        data = (
            self._u16(0x0000) + self._u32(max_moving_gate)
            + self._u16(0x0001) + self._u32(max_stationary_gate)
            + self._u16(0x0002) + self._u32(timeout_s)
        )
        return self._require_success(self._command(0x0060, data), "set_distance_range")

    def set_gate_sensitivity(self, gate, moving, stationary):
        """Set moving/static sensitivity (0..100) for one gate 0..8."""
        if not 0 <= gate <= 8:
            raise ValueError("gate debe estar entre 0 y 8")
        if not 0 <= moving <= 100 or not 0 <= stationary <= 100:
            raise ValueError("moving y stationary deben estar entre 0 y 100")
        data = (
            self._u16(0x0000) + self._u32(gate)
            + self._u16(0x0001) + self._u32(moving)
            + self._u16(0x0002) + self._u32(stationary)
        )
        return self._require_success(self._command(0x0064, data), "set_gate_sensitivity")

    def set_trigger(self, gate, value):
        """Compatibility alias: apply the same sensitivity to moving/static channels."""
        return self.set_gate_sensitivity(gate, value, value)

    def set_hold(self, gate, value):
        """Compatibility alias; LD2410 has moving/static sensitivity, not trigger/hold pairs."""
        return self.set_gate_sensitivity(gate, value, value)

    def read_parameters(self):
        """Return raw configuration parameter bytes from command 0x0061."""
        return self._require_success(self._command(0x0061), "read_parameters").data

    def read_report(self):
        """Parse one BASIC (0x0D) or ENGINEERING (0x23) cyclic report."""
        self._wait_for_header(self.REPORT_HEADER)
        length = self._from_u16(self._read_exactly(2))
        if length not in (0x0D, 0x23):
            raise RadarProtocolError(f"Longitud de frame LD2410 inesperada: {length}")
        payload = self._read_exactly(length)
        if self._read_exactly(4) != self.REPORT_FOOTER:
            raise RadarProtocolError("Footer LD2410 inválido")
        if len(payload) < 13 or payload[1] != 0xAA:
            raise RadarProtocolError("Payload/report head LD2410 inválido")

        report_type = payload[0]
        try:
            state = LD2410TargetState(payload[2])
        except ValueError as exc:
            raise RadarProtocolError(f"Estado objetivo desconocido: {payload[2]}") from exc

        common = dict(
            state=state,
            moving_distance_cm=self._from_u16(payload[3:5]),
            moving_energy=payload[5],
            stationary_distance_cm=self._from_u16(payload[6:8]),
            stationary_energy=payload[8],
            detection_distance_cm=self._from_u16(payload[9:11]),
        )

        if report_type == 0x02:
            self.mode = LD2410Mode.BASIC
            return LD2410Report(**common)

        if report_type != 0x01 or length != 0x23:
            raise RadarProtocolError(f"Tipo de reporte LD2410 no soportado: 0x{report_type:02X}")

        self.mode = LD2410Mode.ENGINEERING
        return LD2410EngineeringReport(
            **common,
            max_moving_gate=payload[11],
            max_stationary_gate=payload[12],
            moving_gate_energy=list(payload[13:22]),
            stationary_gate_energy=list(payload[22:31]),
            light=payload[31] if len(payload) > 31 else None,
            out_pin=payload[32] if len(payload) > 32 else None,
        )

    def read(self):
        """Read one cyclic report; the frame identifies BASIC vs ENGINEERING."""
        return self.read_report()
