"""Hi-Link LD2450 driver, serial protocol V1.03 (2023-10-17).

Use alongside the supplied base.py, in the same Python package as ld2420.py.
CPython/Blinka/pyserial; dataclasses/enum/contextlib are not native CircuitPython.
The caller owns the UART. Configure a short, finite UART read timeout (e.g.
0.02 s); the base cannot interrupt a blocking backend read. Not thread-safe.
Configuration commands may discard pending tracking reports, as in base.py.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from enum import IntEnum
from math import atan2, degrees, hypot
from typing import Tuple

from .base import RadarProtocolError, RadarUARTBase


class LD2450Command(IntEnum):
    SINGLE_TARGET_TRACKING = 0x0080
    MULTI_TARGET_TRACKING = 0x0090
    GET_TRACKING_MODE = 0x0091
    READ_FIRMWARE_VERSION = 0x00A0
    SET_BAUDRATE = 0x00A1
    RESTORE_FACTORY_SETTINGS = 0x00A2
    RESTART = 0x00A3
    SET_BLUETOOTH = 0x00A4
    READ_MAC_ADDRESS = 0x00A5
    GET_ZONE_CONFIGURATION = 0x00C1
    SET_ZONE_CONFIGURATION = 0x00C2
    END_CONFIGURATION = 0x00FE
    ENABLE_CONFIGURATION = 0x00FF


class LD2450TrackingMode(IntEnum):
    SINGLE = 1
    MULTI = 2


class LD2450ZoneMode(IntEnum):
    DISABLED = 0
    INCLUDE = 1
    EXCLUDE = 2


@dataclass(frozen=True)
class LD2450ConfigurationInfo:
    protocol_version: int
    buffer_size: int


@dataclass(frozen=True)
class LD2450Target:
    """A report slot, NOT a persistent identity. Speed is NOT a velocity vector.

    resolution_mm is range gate size, not measurement error or confidence.
    angle_deg is atan2(x, y): zero along +Y, positive toward +X.
    """

    slot: int
    x_mm: int
    y_mm: int
    speed_cm_s: int
    resolution_mm: int
    present: bool

    @property
    def distance_mm(self) -> float:
        return hypot(self.x_mm, self.y_mm)

    @property
    def angle_deg(self) -> float:
        return degrees(atan2(self.x_mm, self.y_mm))


@dataclass(frozen=True)
class LD2450Report:
    """Exactly three slots; only active_targets should be treated as detections."""

    targets: Tuple[LD2450Target, ...]

    @property
    def active_targets(self) -> Tuple[LD2450Target, ...]:
        return tuple(target for target in self.targets if target.present)

    @property
    def target_count(self) -> int:
        return len(self.active_targets)

    @property
    def presence(self) -> bool:
        return bool(self.active_targets)


def _integer(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{name} debe ser entero entre {low} y {high}")
    return value


@dataclass(frozen=True)
class LD2450Zone:
    """Opposite rectangle vertices in mm, signed int16 (two's complement).

    Vertex order is preserved; reversed corners are valid in the manual.
    All-zero coordinates disable this particular rectangle.
    """

    x1_mm: int = 0
    y1_mm: int = 0
    x2_mm: int = 0
    y2_mm: int = 0

    def __post_init__(self):
        for name in ("x1_mm", "y1_mm", "x2_mm", "y2_mm"):
            _integer(getattr(self, name), -32768, 32767, name)

    @property
    def enabled(self) -> bool:
        return any((self.x1_mm, self.y1_mm, self.x2_mm, self.y2_mm))

    def to_bytes(self) -> bytes:
        return b"".join(value.to_bytes(2, "little", signed=True) for value in
                        (self.x1_mm, self.y1_mm, self.x2_mm, self.y2_mm))


@dataclass(frozen=True)
class LD2450ZoneConfiguration:
    mode: LD2450ZoneMode
    zones: Tuple[LD2450Zone, ...]


class LD2450(RadarUARTBase):
    REPORT_HEADER = b"\xAA\xFF\x03\x00"
    REPORT_FOOTER = b"\x55\xCC"
    REPORT_LENGTH = 24  # Payload; complete report is 30 bytes, no length field.
    DEFAULT_BAUDRATE = 256000
    BAUDRATES = (9600, 19200, 38400, 57600, 115200, 230400, 256000, 460800)

    def __init__(self, uart, *, debug=False, frame_timeout=1.0):
        super().__init__(uart, debug=debug, frame_timeout=frame_timeout)
        self._configuration_depth = 0
        self._configuration_enabled = False
        self._last_configuration_info = None

    def _exchange(self, command, data=b"", *, response_size=0):
        response = self._command(command, data)
        if response.ack_word != (int(command) | 0x0100):
            raise RadarProtocolError(
                f"ACK 0x{response.ack_word:04X} no corresponde al comando 0x{int(command):04X}"
            )
        self._require_success(response, LD2450Command(command).name)
        if len(response.data) != response_size:
            raise RadarProtocolError(
                f"Respuesta de {LD2450Command(command).name}: "
                f"{len(response.data)} bytes de datos; se esperaban {response_size}"
            )
        return response

    def enable_command_mode(self) -> LD2450ConfigurationInfo:
        if self._configuration_enabled:
            return self._last_configuration_info
        response = self._exchange(LD2450Command.ENABLE_CONFIGURATION,
                                  self._u16(1), response_size=4)
        info = LD2450ConfigurationInfo(self._from_u16(response.data[:2]),
                                       self._from_u16(response.data[2:]))
        self._last_configuration_info = info
        self._configuration_enabled = True
        return info

    def disable_command_mode(self):
        if self._configuration_depth:
            raise RuntimeError("No cierres manualmente una sesión with configuration()")
        try:
            return self._exchange(LD2450Command.END_CONFIGURATION)
        finally:
            # A lost ACK leaves hardware state uncertain: next operation re-enables.
            self._configuration_enabled = False

    @contextmanager
    def configuration(self):
        """Nestable session; borrowed manual sessions are left open.

        On failure, attempt END without masking the original exception.
        """
        owned = not self._configuration_enabled
        if owned:
            self.enable_command_mode()
        self._configuration_depth += 1
        try:
            yield self
        except BaseException:
            self._configuration_depth -= 1
            if owned:
                try:
                    self.disable_command_mode()
                except Exception:
                    pass
            raise
        else:
            self._configuration_depth -= 1
            if owned:
                self.disable_command_mode()

    @property
    def configuration_info(self):
        """Last successful enable response; None before the first session."""
        return self._last_configuration_info

    def _configured(self, command, data=b"", *, response_size=0):
        with self.configuration():
            return self._exchange(command, data, response_size=response_size)

    @property
    def firmware_version(self) -> str:
        """Example from p.8: 00 00 02 01 16 24 06 22 -> V1.02.22062416."""
        data = self._configured(LD2450Command.READ_FIRMWARE_VERSION,
                                response_size=8).data
        return f"V{data[3]:X}.{data[2]:02X}.{self._from_u32(data[4:]):08X}"

    def get_version(self) -> str:
        return self.firmware_version

    @property
    def tracking_mode(self) -> LD2450TrackingMode:
        data = self._configured(LD2450Command.GET_TRACKING_MODE, response_size=2).data
        try:
            return LD2450TrackingMode(self._from_u16(data))
        except ValueError as exc:
            raise RadarProtocolError("Modo de tracking desconocido") from exc

    @tracking_mode.setter
    def tracking_mode(self, value):
        mode = LD2450TrackingMode(_integer(value, 1, 2, "tracking_mode"))
        command = (LD2450Command.SINGLE_TARGET_TRACKING if mode == LD2450TrackingMode.SINGLE
                   else LD2450Command.MULTI_TARGET_TRACKING)
        self._configured(command)
    
    def set_baudrate(self, baudrate: int):
        """Save radar baud rate; takes effect AFTER restart, not on the host UART.

        Then call restart() at the old baud rate, change/reopen the host UART,
        and wait for startup. No baud-rate query exists in protocol V1.03.
        """
        _integer(baudrate, 9600, 460800, "baudrate")
        if baudrate not in self.BAUDRATES:
            raise ValueError(f"Baudrate no soportado; usa {self.BAUDRATES}")
        return self._configured(LD2450Command.SET_BAUDRATE,
                                self._u16(self.BAUDRATES.index(baudrate) + 1))

    def set_bluetooth(self, enabled: bool):
        """Persistent, requires restart. No Bluetooth-state query is documented.

        p.10 prose says 0x0100; its frame says 01 00. Use the frame (uint16 1).
        """
        if not isinstance(enabled, bool):
            raise ValueError("enabled debe ser True o False")
        return self._configured(LD2450Command.SET_BLUETOOTH, self._u16(int(enabled)))

    @property
    def mac_address(self) -> str:
        """Six bytes in transmitted order, following the p.10 example.

        The prose incorrectly describes a type byte and three MAC bytes.
        """
        data = self._configured(LD2450Command.READ_MAC_ADDRESS, self._u16(1),
                                response_size=6).data
        return ":".join(f"{value:02X}" for value in data)

    def restore_factory_settings(self):
        """Restore settings; caller must restart. Host baud becomes 256000 then.

        Defaults: multi-target, Bluetooth on, zones disabled. Does not reboot.
        """
        return self._configured(LD2450Command.RESTORE_FACTORY_SETTINGS)

    def restart(self):
        """Standalone operation: enable, restart ACK, NO END after reboot.

        Forbidden in an open session. No automatic delay or UART rate change.
        After a timeout the device may already have rebooted; do not blindly retry.
        """
        if self._configuration_depth or self._configuration_enabled:
            raise RuntimeError("Ejecuta restart() fuera de una sesión de configuración")
        self.enable_command_mode()
        try:
            return self._exchange(LD2450Command.RESTART)
        finally:
            self._configuration_enabled = False

    @property
    def zone_configuration(self) -> LD2450ZoneConfiguration:
        data = self._configured(LD2450Command.GET_ZONE_CONFIGURATION,
                                response_size=26).data
        try:
            mode = LD2450ZoneMode(self._from_u16(data[:2]))
        except ValueError as exc:
            raise RadarProtocolError("Modo de filtrado de zonas desconocido") from exc
        zones = tuple(LD2450Zone(*(int.from_bytes(data[j:j+2], "little", signed=True)
                                  for j in range(i, i+8, 2)))
                      for i in range(2, 26, 8))
        return LD2450ZoneConfiguration(mode, zones)

    @zone_configuration.setter
    def zone_configuration(self, value: LD2450ZoneConfiguration):
        if not isinstance(value, LD2450ZoneConfiguration):
            raise ValueError("Usa LD2450ZoneConfiguration")
        self.set_zones(value.mode, value.zones)

    def set_zones(self, mode, zones=()):
        """Write all three zones; omitted slots are zeroed. Immediate + persistent.

        mode: DISABLED, INCLUDE (only these zones), EXCLUDE (ignore these zones).
        Coordinates are protocol-range validated, not clipped to the physical FOV.
        """
        mode = LD2450ZoneMode(_integer(mode, 0, 2, "zone_mode"))
        zones = tuple(zones)
        if len(zones) > 3 or any(not isinstance(zone, LD2450Zone) for zone in zones):
            raise ValueError("Se requieren de 0 a 3 objetos LD2450Zone")
        zones += (LD2450Zone(),) * (3 - len(zones))
        payload = self._u16(mode) + b"".join(zone.to_bytes() for zone in zones)
        return self._configured(LD2450Command.SET_ZONE_CONFIGURATION, payload)

    @staticmethod
    def _decode_tracking_value(data: bytes) -> int:
        # NOT two's complement: bit15=1 positive, bit15=0 negative.
        word = int.from_bytes(data, "little")
        magnitude = word & 0x7FFF
        return magnitude if word & 0x8000 else -magnitude

    def read_report(self) -> LD2450Report:
        """Blocking read of the next report, normally 10 Hz (p.12).

        Uses base per-stage timeouts; not a non-blocking update() API.
        A malformed frame raises; the next call searches for the next header.
        Do not call while configuration is active or concurrently with commands.
        """
        if self._configuration_enabled:
            raise RuntimeError("Cierra la configuración antes de leer reportes")
        self._wait_for_header(self.REPORT_HEADER)
        payload = self._read_exactly(self.REPORT_LENGTH)
        footer = self._read_exactly(2)
        if footer != self.REPORT_FOOTER:
            raise RadarProtocolError(f"Footer de reporte inválido: {footer.hex(' ')}")
        self._print_hex("REPORT:", self.REPORT_HEADER + payload + footer)
        targets = []
        for slot, offset in enumerate(range(0, self.REPORT_LENGTH, 8), 1):
            raw = payload[offset:offset+8]
            targets.append(LD2450Target(
                slot, self._decode_tracking_value(raw[:2]),
                self._decode_tracking_value(raw[2:4]),
                self._decode_tracking_value(raw[4:6]),
                self._from_u16(raw[6:8]), any(raw),
            ))
        return LD2450Report(tuple(targets))

    def read(self) -> LD2450Report:
        return self.read_report()
