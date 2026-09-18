"""LD2410 / LD2410B / LD2410C common UART protocol driver.

Not for LD2410S or LD2410D. Based on the LD240 driver.

Use a short finite UART timeout; base.py cannot interrupt a blocking backend read. Not thread-safe.
"""

from __future__ import annotations

import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from enum import IntEnum
from typing import List, Optional, Tuple

from .base import RadarProtocolError, RadarUARTBase


class LD2410Command(IntEnum):
    SET_DISTANCE_RANGE = 0x0060
    READ_PARAMETERS = 0x0061
    ENABLE_ENGINEERING_MODE = 0x0062
    DISABLE_ENGINEERING_MODE = 0x0063
    SET_GATE_SENSITIVITY = 0x0064
    READ_FIRMWARE_VERSION = 0x00A0
    RESTART = 0x00A3
    END_CONFIGURATION = 0x00FE
    ENABLE_CONFIGURATION = 0x00FF


class LD2410Mode(IntEnum):
    BASIC = 0
    ENGINEERING = 1


class LD2410TargetState(IntEnum):
    NONE = 0x00
    MOVING = 0x01
    STATIONARY = 0x02
    BOTH = 0x03


@dataclass(frozen=True)
class LD2410ConfigurationInfo:
    protocol_version: int
    buffer_size: int


@dataclass(frozen=True)
class LD2410Parameters:
    """Snapshot from 0x61; all ranges are gate indices, not cm.

    Sensitivities are the module's 0..100 thresholds, not dB values.
    max_gate is the reported maximum supported gate index.
    """
    max_gate: int
    max_moving_gate: int
    max_stationary_gate: int
    moving_sensitivities: Tuple[int, ...]
    stationary_sensitivities: Tuple[int, ...]
    timeout_s: int


@dataclass(frozen=True)
class LD2410Report:
    """Basic cyclic report. A snapshot, not live properties of the radar."""
    state: LD2410TargetState
    moving_distance_cm: int
    moving_energy: int
    stationary_distance_cm: int
    stationary_energy: int
    detection_distance_cm: int

    @property
    def presence(self) -> bool:
        return self.state != LD2410TargetState.NONE

    @property
    def moving(self) -> bool:
        return self.state in (LD2410TargetState.MOVING, LD2410TargetState.BOTH)

    @property
    def stationary(self) -> bool:
        return self.state in (LD2410TargetState.STATIONARY, LD2410TargetState.BOTH)


@dataclass(frozen=True)
class LD2410EngineeringReport(LD2410Report):
    """Nine per-gate energy samples per channel; light is raw, not lux.

    Lists retained for compatibility with the original report class.
    light/out_pin are None in the 33-byte payload variant.
    """
    max_moving_gate: int
    max_stationary_gate: int
    moving_gate_energy: List[int]
    stationary_gate_energy: List[int]
    light: Optional[int] = None
    out_pin: Optional[int] = None


def _integer(value, minimum, maximum, name):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{name} debe ser entero entre {minimum} y {maximum}")
    return value


class LD2410(RadarUARTBase):
    """Common nine-gate LD2410 UART driver, with automatic configuration sessions.

    Constructor does not access hardware. Properties that query configuration
    perform UART I/O; `mode` and `configuration_info` are local cached knowledge.
    """

    REPORT_HEADER = b"\xF4\xF3\xF2\xF1"
    REPORT_FOOTER = b"\xF8\xF7\xF6\xF5"
    DEFAULT_BAUDRATE = 256000
    RANGE_GATE_COUNT = 9
    BASIC_REPORT_LENGTH = 13
    ENGINEERING_REPORT_LENGTHS = (33, 35)

    def __init__(self, uart, *, debug=False, frame_timeout=1.0):
        super().__init__(uart, debug=debug, frame_timeout=frame_timeout)
        self._mode: Optional[LD2410Mode] = None
        self._configuration_depth = 0
        self._configuration_enabled = False
        self._last_configuration_info = None
        self._last_enable_response = None

    def _exchange(self, command, data=b"", *, response_size=0):
        response = self._command(command, data)
        if response.ack_word != (int(command) | 0x0100):
            raise RadarProtocolError(
                f"ACK 0x{response.ack_word:04X} no corresponde al comando 0x{int(command):04X}"
            )
        self._require_success(response, LD2410Command(command).name)
        if len(response.data) != response_size:
            raise RadarProtocolError(
                f"{LD2410Command(command).name}: se esperaban {response_size} bytes "
                f"de datos y llegaron {len(response.data)}"
            )
        return response

    def enable_command_mode(self):
        """Enable configuration; return CommandResponse as in the original class."""
        if self._configuration_enabled:
            return self._last_enable_response
        response = self._exchange(LD2410Command.ENABLE_CONFIGURATION,
                                  self._u16(1), response_size=4)
        self._last_configuration_info = LD2410ConfigurationInfo(
            self._from_u16(response.data[:2]), self._from_u16(response.data[2:4])
        )
        self._last_enable_response = response
        self._configuration_enabled = True
        return response

    def disable_command_mode(self):
        """End configuration. Do not call manually inside configuration()."""
        if self._configuration_depth:
            raise RuntimeError("No cierres manualmente una sesión with configuration()")
        try:
            return self._exchange(LD2410Command.END_CONFIGURATION)
        finally:
            # On timeout, hardware state is uncertain: re-enable next time.
            self._configuration_enabled = False

    @contextmanager
    def configuration(self):
        """Nestable session; pre-existing manual sessions are borrowed, not closed.

        If the body fails, attempt END without masking its original exception.
        An END failure propagates when the body itself succeeded.
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
    def configuration_info(self) -> Optional[LD2410ConfigurationInfo]:
        """Last successful enable response fields, or None before first enable."""
        return self._last_configuration_info

    def _configured(self, command, data=b"", *, response_size=0):
        with self.configuration():
            return self._exchange(command, data, response_size=response_size)

    @property
    def firmware_version(self) -> str:
        """Read formatted firmware, e.g. V1.02.22062416."""
        data = self._configured(LD2410Command.READ_FIRMWARE_VERSION, response_size=8).data
        return f"V{data[3]}.{data[2]:02X}.{self._from_u32(data[4:8]):08X}"

    def get_version(self):
        """Legacy dictionary; preserves original byte meanings and key names.

        Historical major=data[2], minor=data[3] names are reversed relative to
        the displayed version. Prefer firmware_version for human-readable text.
        Unlike the original, malformed lengths raise RadarProtocolError.
        """
        data = self._configured(LD2410Command.READ_FIRMWARE_VERSION, response_size=8).data
        return {"type": self._from_u16(data[:2]), "major": data[2], "minor": data[3],
                "bugfix": self._from_u32(data[4:8]), "raw": data}

    @property
    def mode(self) -> Optional[LD2410Mode]:
        """Last acknowledged/observed mode; None initially and after restart.

        This is NOT a hardware query. External changes are only noticed on the
        next valid report. Reading this property sends no commands.
        """
        return self._mode

    @mode.setter
    def mode(self, value):
        self.set_mode(value)

    def set_mode(self, mode):
        """Select report mode; update cache only after the matching success ACK."""
        mode = LD2410Mode(_integer(mode, 0, 1, "mode"))
        command = (LD2410Command.ENABLE_ENGINEERING_MODE if mode == LD2410Mode.ENGINEERING
                   else LD2410Command.DISABLE_ENGINEERING_MODE)
        with self.configuration():
            response = self._exchange(command)
            self._mode = mode
        return response

    def enable_engineering_mode(self):
        return self.set_mode(LD2410Mode.ENGINEERING)

    def disable_engineering_mode(self):
        return self.set_mode(LD2410Mode.BASIC)

    def restart(self):
        """Enable, send restart, read ACK; never send END after reboot.

        Use outside manual/with sessions. No startup delay is assumed. A timeout
        may mean the radar rebooted before the ACK was received: do not blindly
        retry. The next successful report reestablishes the known mode.
        """
        if self._configuration_depth or self._configuration_enabled:
            raise RuntimeError("Ejecuta restart() fuera de una sesión de configuración")
        self.enable_command_mode()
        try:
            return self._exchange(LD2410Command.RESTART)
        finally:
            self._configuration_enabled = False
            self._mode = None

    # Parameter queries and read-modify-write properties
    def read_parameters(self) -> bytes:
        """Read raw 24-byte common parameter layout (legacy return type)."""
        return self._configured(LD2410Command.READ_PARAMETERS, response_size=24).data

    @property
    def parameters(self) -> LD2410Parameters:
        """Read/validate one coherent parameter snapshot; does not write settings."""
        data = self.read_parameters()
        if data[0] != 0xAA:
            raise RadarProtocolError("Cabecera interna de parámetros inválida")
        if data[1] > 8 or data[2] > data[1] or data[3] > data[1]:
            raise RadarProtocolError("Gates de configuración fuera de rango")
        if any(value > 100 for value in data[4:22]):
            raise RadarProtocolError("Sensibilidad reportada fuera de 0..100")
        return LD2410Parameters(data[1], data[2], data[3], tuple(data[4:13]),
                                tuple(data[13:22]), self._from_u16(data[22:24]))

    def set_distance_range(self, max_moving_gate, max_stationary_gate, timeout_s):
        """Write both maximum gates (0..8) and no-target delay (0..65535 s).

        Gates are indices, NOT physical distances. No minimum gate is implied.
        Preserves the original three-argument API; persistent configuration write.
        """
        moving = _integer(max_moving_gate, 0, 8, "max_moving_gate")
        stationary = _integer(max_stationary_gate, 0, 8, "max_stationary_gate")
        delay = _integer(timeout_s, 0, 65535, "timeout_s")
        data = (self._u16(0) + self._u32(moving) + self._u16(1) + self._u32(stationary)
                + self._u16(2) + self._u32(delay))
        return self._configured(LD2410Command.SET_DISTANCE_RANGE, data)

    def _update_range(self, *, moving=None, stationary=None, timeout=None):
        with self.configuration():
            current = self.parameters
            return self.set_distance_range(
                current.max_moving_gate if moving is None else moving,
                current.max_stationary_gate if stationary is None else stationary,
                current.timeout_s if timeout is None else timeout,
            )

    @property
    def max_moving_gate(self) -> int:
        return self.parameters.max_moving_gate

    @max_moving_gate.setter
    def max_moving_gate(self, value):
        self._update_range(moving=_integer(value, 0, 8, "max_moving_gate"))

    @property
    def max_stationary_gate(self) -> int:
        return self.parameters.max_stationary_gate

    @max_stationary_gate.setter
    def max_stationary_gate(self, value):
        self._update_range(stationary=_integer(value, 0, 8, "max_stationary_gate"))

    @property
    def timeout_s(self) -> int:
        """No-target disappearance delay; NOT UART frame_timeout."""
        return self.parameters.timeout_s

    @timeout_s.setter
    def timeout_s(self, value):
        self._update_range(timeout=_integer(value, 0, 65535, "timeout_s"))

    @property
    def distance_range(self) -> Tuple[int, int]:
        """(max_moving_gate, max_stationary_gate), NOT a (min,max) distance pair."""
        current = self.parameters
        return current.max_moving_gate, current.max_stationary_gate

    @distance_range.setter
    def distance_range(self, value):
        try:
            values = tuple(value)
        except TypeError as exc:
            raise ValueError("distance_range requiere dos gates") from exc
        if len(values) != 2:
            raise ValueError("distance_range requiere (max_moving_gate, max_stationary_gate)")
        moving = _integer(values[0], 0, 8, "max_moving_gate")
        stationary = _integer(values[1], 0, 8, "max_stationary_gate")
        self._update_range(moving=moving, stationary=stationary)

    def set_gate_sensitivity(self, gate, moving, stationary):
        """Write thresholds 0..100 for both channels of one gate (0..8).

        Uses the device's sensitivity terminology; values are NOT dB. This is
        a persistent setting, not a runtime measurement or calibration routine.
        """
        gate = _integer(gate, 0, 8, "gate")
        moving = _integer(moving, 0, 100, "moving")
        stationary = _integer(stationary, 0, 100, "stationary")
        data = (self._u16(0) + self._u32(gate) + self._u16(1) + self._u32(moving)
                + self._u16(2) + self._u32(stationary))
        return self._configured(LD2410Command.SET_GATE_SENSITIVITY, data)

    def _set_sensitivities(self, values, *, moving):
        try:
            values = tuple(values)
        except TypeError as exc:
            raise ValueError("Se requieren nueve sensibilidades") from exc
        if len(values) != self.RANGE_GATE_COUNT:
            raise ValueError("Se requieren nueve sensibilidades, gates 0..8")
        for value in values:
            _integer(value, 0, 100, "sensitivity")
        with self.configuration():
            current = self.parameters
            # Nine sequential writes, NOT atomic; a failure can leave a partial bank.
            for gate, value in enumerate(values):
                self.set_gate_sensitivity(
                    gate, value if moving else current.moving_sensitivities[gate],
                    current.stationary_sensitivities[gate] if moving else value,
                )

    @property
    def moving_sensitivities(self) -> Tuple[int, ...]:
        return self.parameters.moving_sensitivities

    @moving_sensitivities.setter
    def moving_sensitivities(self, values):
        """Write nine gates, preserving stationary thresholds. Not atomic."""
        self._set_sensitivities(values, moving=True)

    @property
    def stationary_sensitivities(self) -> Tuple[int, ...]:
        return self.parameters.stationary_sensitivities

    @stationary_sensitivities.setter
    def stationary_sensitivities(self, values):
        """Write nine gates, preserving moving thresholds. Not atomic."""
        self._set_sensitivities(values, moving=False)

    def set_trigger(self, gate, value):
        """Deprecated compatibility alias: writes BOTH sensitivity channels."""
        warnings.warn("set_trigger no representa trigger/hold en LD2410; "
                      "usa set_gate_sensitivity(gate, moving, stationary). "
                      "Este alias cambia ambos canales.", DeprecationWarning, stacklevel=2)
        return self.set_gate_sensitivity(gate, value, value)

    def set_hold(self, gate, value):
        """Deprecated compatibility alias: writes BOTH sensitivity channels."""
        warnings.warn("set_hold no representa trigger/hold en LD2410; "
                      "usa set_gate_sensitivity(gate, moving, stationary). "
                      "Este alias cambia ambos canales.", DeprecationWarning, stacklevel=2)
        return self.set_gate_sensitivity(gate, value, value)

    def read_report(self):
        """Blocking read; validates outer framing and internal AA / 55 00 markers.

        BASIC payload: 13 bytes. ENGINEERING: 33 bytes (nine energies per channel)
        or 35 bytes (also light/out_pin). Unsupported layouts raise, not guessed.
        A failed frame is not silently retried; next call searches a new header.
        Mode changes here only update _mode; they NEVER transmit a command.
        """
        if self._configuration_enabled:
            raise RuntimeError("Cierra la configuración antes de leer reportes")
        self._wait_for_header(self.REPORT_HEADER)
        length_raw = self._read_exactly(2)
        length = self._from_u16(length_raw)
        if length not in (self.BASIC_REPORT_LENGTH,) + self.ENGINEERING_REPORT_LENGTHS:
            raise RadarProtocolError(f"Longitud de frame LD2410 inesperada: {length}")
        payload = self._read_exactly(length)
        if self._read_exactly(4) != self.REPORT_FOOTER:
            raise RadarProtocolError("Footer LD2410 inválido")
        if payload[1] != 0xAA or payload[-2:] != b"\x55\x00":
            raise RadarProtocolError("Marcadores internos de reporte LD2410 inválidos")
        report_type = payload[0]
        if not ((report_type == 2 and length == self.BASIC_REPORT_LENGTH) or
                (report_type == 1 and length in self.ENGINEERING_REPORT_LENGTHS)):
            raise RadarProtocolError("Tipo/longitud de reporte LD2410 incompatibles")
        try:
            state = LD2410TargetState(payload[2])
        except ValueError as exc:
            raise RadarProtocolError(f"Estado objetivo desconocido: {payload[2]}") from exc
        common = dict(
            state=state, moving_distance_cm=self._from_u16(payload[3:5]),
            moving_energy=payload[5], stationary_distance_cm=self._from_u16(payload[6:8]),
            stationary_energy=payload[8], detection_distance_cm=self._from_u16(payload[9:11]),
        )
        if report_type == 2:
            value = LD2410Report(**common)
            mode = LD2410Mode.BASIC
        else:
            if payload[11] > 8 or payload[12] > 8:
                raise RadarProtocolError("Gates de reporte fuera de 0..8")
            value = LD2410EngineeringReport(
                **common, max_moving_gate=payload[11], max_stationary_gate=payload[12],
                moving_gate_energy=list(payload[13:22]),
                stationary_gate_energy=list(payload[22:31]),
                light=payload[31] if length == 35 else None,
                out_pin=payload[32] if length == 35 else None,
            )
            mode = LD2410Mode.ENGINEERING
        self._mode = mode
        self._print_hex("REPORT:", self.REPORT_HEADER + length_raw + payload + self.REPORT_FOOTER)
        return value

    def read(self):
        """Alias of read_report()."""
        return self.read_report()
