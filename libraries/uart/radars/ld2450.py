"""Driver for the Hi-Link HLK-LD2450 multi-target tracking radar."""

import math
from dataclasses import dataclass
from enum import IntEnum
from typing import List

from .base import RadarProtocolError, RadarUARTBase


class LD2450TrackingMode(IntEnum):
    SINGLE = 0x0001
    MULTI = 0x0002


@dataclass(frozen=True)
class LD2450Target:
    """One decoded target slot."""
    x_mm: int
    y_mm: int
    speed_cm_s: int
    resolution_mm: int

    @property
    def exists(self):
        return any((self.x_mm, self.y_mm, self.speed_cm_s, self.resolution_mm))

    @property
    def distance_mm(self):
        return math.hypot(self.x_mm, self.y_mm)

    @property
    def angle_deg(self):
        """Angle where 0 degrees points along +Y."""
        return math.degrees(math.atan2(self.x_mm, self.y_mm))


@dataclass(frozen=True)
class LD2450Report:
    """One tracking report containing three target slots."""
    targets: List[LD2450Target]

    @property
    def active_targets(self):
        return [target for target in self.targets if target.exists]

    @property
    def count(self):
        return len(self.active_targets)

    @property
    def presence(self):
        return self.count > 0


class LD2450(RadarUARTBase):
    """HLK-LD2450 driver. Default module baud rate is normally 256000."""

    REPORT_HEADER = b"\xAA\xFF\x03\x00"
    REPORT_FOOTER = b"\x55\xCC"

    def enable_command_mode(self):
        return self._require_success(self._command(0x00FF, self._u16(1)), "enable_command_mode")

    def disable_command_mode(self):
        return self._require_success(self._command(0x00FE), "disable_command_mode")

    def get_version(self):
        """Return raw firmware-version payload from command 0x00A0."""
        return self._require_success(self._command(0x00A0), "get_version").data

    def restart(self):
        """Reset/restart the module (command 0x00A2 in the LD2450 protocol)."""
        return self._require_success(self._command(0x00A2), "restart")

    def set_single_target(self):
        return self._require_success(self._command(0x0080), "set_single_target")

    def set_multi_target(self):
        return self._require_success(self._command(0x0090), "set_multi_target")

    def set_mode(self, mode):
        """Homogeneous alias for selecting SINGLE or MULTI tracking."""
        mode = LD2450TrackingMode(mode)
        return self.set_single_target() if mode == LD2450TrackingMode.SINGLE else self.set_multi_target()

    def get_mode(self):
        response = self._require_success(self._command(0x0091), "get_mode")
        if len(response.data) < 2:
            raise RadarProtocolError("Respuesta get_mode incompleta")
        return LD2450TrackingMode(self._from_u16(response.data[:2]))

    @staticmethod
    def _decode_signed_magnitude(raw):
        """Decode LD2450 sign/magnitude: bit15=1 positive, bit15=0 negative."""
        magnitude = raw & 0x7FFF
        if magnitude == 0:
            return 0
        return magnitude if raw & 0x8000 else -magnitude

    def _parse_target(self, raw):
        if len(raw) != 8:
            raise ValueError("Un target LD2450 ocupa exactamente 8 bytes")
        return LD2450Target(
            x_mm=self._decode_signed_magnitude(self._from_u16(raw[0:2])),
            y_mm=self._decode_signed_magnitude(self._from_u16(raw[2:4])),
            speed_cm_s=self._decode_signed_magnitude(self._from_u16(raw[4:6])),
            resolution_mm=self._from_u16(raw[6:8]),
        )

    def read_targets(self):
        """Read one 30-byte frame: header + 3x8-byte targets + footer."""
        self._wait_for_header(self.REPORT_HEADER)
        payload = self._read_exactly(24)
        if self._read_exactly(2) != self.REPORT_FOOTER:
            raise RadarProtocolError("Footer LD2450 inválido")
        return LD2450Report([
            self._parse_target(payload[i*8:(i+1)*8]) for i in range(3)
        ])

    def read(self):
        """Read one multi-target tracking report."""
        return self.read_targets()
