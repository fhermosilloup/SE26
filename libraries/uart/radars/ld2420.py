"""Driver for the Hi-Link HLK-LD2420 24 GHz radar module.

The driver follows the same public structure as the LD2402 driver while
keeping the LD2420 command map and its REPORT/DEBUG payloads separate.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from enum import IntEnum
from math import log10
from typing import Callable, Iterable, List, Optional, Sequence, Tuple, Union
from time import sleep
from .base import RadarProtocolError, RadarUARTBase


class LD2420Command(IntEnum):
    READ_FIRMWARE_VERSION = 0x0000
    SET_PARAMETERS = 0x0007
    GET_PARAMETERS = 0x0008
    WRITE_SERIAL_NUMBER = 0x0010
    READ_SERIAL_NUMBER = 0x0011
    SET_OUTPUT_MODE = 0x0012
    RESTART = 0x0068
    END_CONFIGURATION = 0x00FE
    ENABLE_CONFIGURATION = 0x00FF


class LD2420Mode(IntEnum):
    DEBUG = 0x00
    ENGINEERING = 0x04
    REPORT = 0x04
    NORMAL = 0x64
    RUN = 0x64


class LD2420DetectionState(IntEnum):
    NONE = 0x00
    PRESENT = 0x01


class LD2420Parameter(IntEnum):
    MIN_DISTANCE = 0x0000
    MAX_DISTANCE = 0x0001
    DISAPPEARANCE_DELAY = 0x0004

    @staticmethod
    def trigger_gate(gate: int) -> int:
        return 0x0010 + LD2420._validate_gate(gate)

    @staticmethod
    def hold_gate(gate: int) -> int:
        return 0x0020 + LD2420._validate_gate(gate)


@dataclass(frozen=True)
class LD2420ConfigurationInfo:
    protocol_version: int
    buffer_size: int


@dataclass(frozen=True)
class LD2420Report:
    result: int
    distance_cm: int
    energy: List[int]

    @property
    def state(self):
        try:
            return LD2420DetectionState(self.result)
        except ValueError:
            return self.result

    @property
    def presence(self) -> bool:
        return self.result != LD2420DetectionState.NONE

    @property
    def energy_db(self) -> List[float]:
        return [float("-inf") if value <= 0 else 10.0 * log10(value) for value in self.energy]

    @property
    def distance(self) -> int:
        """Backward-compatible alias for ``distance_cm``."""
        return self.distance_cm


@dataclass(frozen=True)
class LD2420DebugMap:
    """Range-Doppler data indexed as ``values[doppler_bin][range_gate]``."""

    values: List[List[int]]

    def __getitem__(self, item):
        return self.values[item]

    @property
    def doppler_bin_count(self) -> int:
        return len(self.values)

    @property
    def range_gate_count(self) -> int:
        return len(self.values[0]) if self.values else 0



@dataclass(frozen=True)
class LD2420CalibrationResult:
    """Background statistics and recommended thresholds for all 16 gates."""

    sample_count: int
    background_raw: List[float]
    percentile95_raw: List[float]
    percentile99_raw: List[float]
    maximum_raw: List[int]
    trigger_thresholds_raw: List[int]
    hold_thresholds_raw: List[int]
    unstable_gates: Tuple[int, ...]

    @staticmethod
    def _to_db(values: Sequence[float]) -> List[float]:
        return [0.0 if value <= 0 else 10.0 * log10(value) for value in values]

    @property
    def background_db(self) -> List[float]:
        return self._to_db(self.background_raw)

    @property
    def trigger_thresholds_db(self) -> List[float]:
        return self._to_db(self.trigger_thresholds_raw)

    @property
    def hold_thresholds_db(self) -> List[float]:
        return self._to_db(self.hold_thresholds_raw)

    def apply(self, radar: "LD2420") -> None:
        """Write both threshold banks to an LD2420 instance."""
        radar.trigger_thresholds_raw = self.trigger_thresholds_raw
        radar.hold_thresholds_raw = self.hold_thresholds_raw
        



















class LD2420(RadarUARTBase):
    COMMAND_HEADER = b"\xFD\xFC\xFB\xFA"
    COMMAND_FOOTER = b"\x04\x03\x02\x01"
    REPORT_HEADER = b"\xF4\xF3\xF2\xF1"
    REPORT_FOOTER = b"\xF8\xF7\xF6\xF5"
    DEBUG_HEADER = b"\xAA\xBF\x10\x14"
    DEBUG_FOOTER = b"\xFD\xFC\xFB\xFA"

    REPORT_LENGTH = 0x23
    RANGE_GATE_COUNT = 16
    DOPPLER_BIN_COUNT = 20
    GATE_SIZE_M = 0.70
    THRESHOLD_RAW_MAX = 1_000_000_000
    THRESHOLD_DB_MAX = 90.0

    def __init__(
        self,
        uart,
        *,
        debug: bool = False,
        frame_timeout: float = 1.0,
        presence_pin: Optional[int] = None,
        bounce_time: float = 0.03,
    ):
        super().__init__(uart, debug=debug, frame_timeout=frame_timeout)
        self._mode = LD2420Mode.RUN
        self._configuration_depth = 0
        self._configuration_enabled = False
        self._last_configuration_info: Optional[LD2420ConfigurationInfo] = None
        self._bounce_time = float(bounce_time)
        self._presence_input = None
        self._when_presence_detected: Optional[Callable[[], None]] = None
        self._when_presence_cleared: Optional[Callable[[], None]] = None
        
        # Set in RUN mode
        self.mode = LD2420Mode.RUN
        
        if presence_pin is not None:
            self.presence_pin = presence_pin

    # Configuration sessions
    def enable_command_mode(self) -> LD2420ConfigurationInfo:
        response = self._require_success(
            self._command(LD2420Command.ENABLE_CONFIGURATION, self._u16(1)),
            "enable_command_mode",
        )
        data = response.data
        info = LD2420ConfigurationInfo(
            self._from_u16(data[0:2]) if len(data) >= 2 else 0,
            self._from_u16(data[2:4]) if len(data) >= 4 else 0,
        )
        self._configuration_enabled = True
        self._last_configuration_info = info
        return info

    def disable_command_mode(self):
        response = self._require_success(
            self._command(LD2420Command.END_CONFIGURATION),
            "disable_command_mode",
        )
        self._configuration_enabled = False
        return response

    @contextmanager
    def configuration(self):
        outermost = self._configuration_depth == 0
        if outermost:
            self.enable_command_mode()
        self._configuration_depth += 1
        try:
            yield self
        finally:
            self._configuration_depth -= 1
            if outermost:
                self.disable_command_mode()

    @property
    def configuration_info(self) -> Optional[LD2420ConfigurationInfo]:
        return self._last_configuration_info

    # Generic parameters
    def get_parameters(self, *parameters: Union[int, LD2420Parameter]):
        if not parameters:
            raise ValueError("Debes indicar al menos un parámetro")
        payload = b"".join(self._u16(int(parameter)) for parameter in parameters)
        with self.configuration():
            response = self._require_success(
                self._command(LD2420Command.GET_PARAMETERS, payload),
                "get_parameters",
            )
        if len(response.data) < 4 * len(parameters):
            raise RadarProtocolError("Respuesta de parámetros incompleta")
        return {
            parameter: self._from_u32(response.data[index * 4 : index * 4 + 4])
            for index, parameter in enumerate(parameters)
        }

    def set_parameters(self, parameters):
        if not parameters:
            raise ValueError("parameters no puede estar vacío")
        payload = bytearray()
        for parameter, value in parameters.items():
            value = int(value)
            if not 0 <= value <= 0xFFFFFFFF:
                raise ValueError("Los valores raw deben caber en uint32")
            payload += self._u16(int(parameter))
            payload += self._u32(value)
        with self.configuration():
            return self._require_success(
                self._command(LD2420Command.SET_PARAMETERS, bytes(payload)),
                "set_parameters",
            )

    def _get_parameter(self, parameter) -> int:
        return next(iter(self.get_parameters(parameter).values()))

    def _set_parameter(self, parameter, value):
        return self.set_parameters({parameter: value})

    # Device information
    @staticmethod
    def _decode_length_prefixed(data: bytes) -> bytes:
        if len(data) < 2:
            raise RadarProtocolError("Respuesta sin longitud")
        length = int.from_bytes(data[:2], "little")
        if length > len(data) - 2:
            raise RadarProtocolError("Longitud declarada mayor que la respuesta")
        return bytes(data[2 : 2 + length])

    @property
    def firmware_version(self):
        response = self._require_success(
            self._command(LD2420Command.READ_FIRMWARE_VERSION),
            "firmware_version",
        )
        raw = self._decode_length_prefixed(response.data)
        try:
            return raw.decode("ascii").rstrip("\x00")
        except UnicodeError:
            return raw

    def get_version(self):
        return self.firmware_version

    @property
    def serial_number(self):
        with self.configuration():
            response = self._require_success(
                self._command(LD2420Command.READ_SERIAL_NUMBER),
                "serial_number",
            )
        raw = self._decode_length_prefixed(response.data)
        try:
            return raw.decode("ascii").rstrip("\x00")
        except UnicodeError:
            return raw

    def write_serial_number(self, value: Union[str, bytes, bytearray]):
        raw = value.encode("ascii") if isinstance(value, str) else bytes(value)
        if not 1 <= len(raw) <= 0xFFFF:
            raise ValueError("El número de serie debe contener entre 1 y 65535 bytes")
        with self.configuration():
            return self._require_success(
                self._command(LD2420Command.WRITE_SERIAL_NUMBER, self._u16(len(raw)) + raw),
                "write_serial_number",
            )

    def restart(self):
        with self.configuration():
            return self._require_success(
                self._command(LD2420Command.RESTART),
                "restart",
            )

    # Scalar properties
    @staticmethod
    def _validate_gate(gate: int) -> int:
        gate = int(gate)
        if not 0 <= gate <= 15:
            raise ValueError("gate debe estar entre 0 y 15")
        return gate

    @property
    def minimum_gate(self) -> int:
        return self._get_parameter(LD2420Parameter.MIN_DISTANCE)

    @minimum_gate.setter
    def minimum_gate(self, value: int):
        self._set_parameter(LD2420Parameter.MIN_DISTANCE, self._validate_gate(value))

    @property
    def maximum_gate(self) -> int:
        return self._get_parameter(LD2420Parameter.MAX_DISTANCE)

    @maximum_gate.setter
    def maximum_gate(self, value: int):
        self._set_parameter(LD2420Parameter.MAX_DISTANCE, self._validate_gate(value))

    @property
    def distance_range(self) -> Tuple[int, int]:
        values = self.get_parameters(LD2420Parameter.MIN_DISTANCE, LD2420Parameter.MAX_DISTANCE)
        return values[LD2420Parameter.MIN_DISTANCE], values[LD2420Parameter.MAX_DISTANCE]

    @distance_range.setter
    def distance_range(self, value: Sequence[int]):
        if len(value) != 2:
            raise ValueError("distance_range requiere (minimum_gate, maximum_gate)")
        minimum, maximum = map(self._validate_gate, value)
        if minimum > maximum:
            raise ValueError("minimum_gate no puede ser mayor que maximum_gate")
        self.set_parameters({
            LD2420Parameter.MIN_DISTANCE: minimum,
            LD2420Parameter.MAX_DISTANCE: maximum,
        })

    def set_distance_range(self, minimum, maximum):
        self.distance_range = (minimum, maximum)
        return self.distance_range

    def get_distance_range(self):
        return self.distance_range

    @property
    def disappearance_delay_s(self) -> int:
        return self._get_parameter(LD2420Parameter.DISAPPEARANCE_DELAY)

    @disappearance_delay_s.setter
    def disappearance_delay_s(self, value: int):
        value = int(value)
        if not 0 <= value <= 255:
            raise ValueError("disappearance_delay_s debe estar entre 0 y 255")
        self._set_parameter(LD2420Parameter.DISAPPEARANCE_DELAY, value)

    def set_delay(self, value):
        self.disappearance_delay_s = value

    def get_delay(self):
        return self.disappearance_delay_s

    # Output mode
    @property
    def mode(self) -> LD2420Mode:
        return self._mode

    @mode.setter
    def mode(self, value: Union[int, LD2420Mode]):
        mode = LD2420Mode(value)
        with self.configuration():
            self._require_success(
                self._command(
                    LD2420Command.SET_OUTPUT_MODE,
                    self._u16(0) + self._u32(int(mode)),
                ),
                "mode",
            )
        self._mode = mode

    # Thresholds
    @classmethod
    def _threshold_db_to_raw(cls, value_db: float) -> int:
        value_db = float(value_db)
        if not 0.0 <= value_db <= cls.THRESHOLD_DB_MAX:
            raise ValueError("El threshold debe estar entre 0 y 90 dB")
        return min(int(round(10.0 ** (value_db / 10.0))), cls.THRESHOLD_RAW_MAX)

    @staticmethod
    def _threshold_raw_to_db(raw: int) -> float:
        raw = int(raw)
        return 0.0 if raw <= 0 else 10.0 * log10(raw)

    @classmethod
    def _validate_threshold_raw(cls, value: int) -> int:
        value = int(value)
        if not 0 <= value <= cls.THRESHOLD_RAW_MAX:
            raise ValueError("threshold raw debe estar entre 0 y 1_000_000_000")
        return value

    def _get_threshold_bank_raw(self, start: int) -> List[int]:
        parameters = tuple(start + gate for gate in range(self.RANGE_GATE_COUNT))
        values = self.get_parameters(*parameters)
        return [values[parameter] for parameter in parameters]

    def _set_threshold_bank_raw(self, start: int, values: Iterable[int]):
        values = list(values)
        if len(values) != self.RANGE_GATE_COUNT:
            raise ValueError("Se requieren exactamente 16 thresholds")
        self.set_parameters({
            start + gate: self._validate_threshold_raw(value)
            for gate, value in enumerate(values)
        })

    @property
    def trigger_thresholds_raw(self) -> List[int]:
        return self._get_threshold_bank_raw(0x0010)

    @trigger_thresholds_raw.setter
    def trigger_thresholds_raw(self, values):
        self._set_threshold_bank_raw(0x0010, values)

    @property
    def hold_thresholds_raw(self) -> List[int]:
        return self._get_threshold_bank_raw(0x0020)

    @hold_thresholds_raw.setter
    def hold_thresholds_raw(self, values):
        self._set_threshold_bank_raw(0x0020, values)

    @property
    def trigger_thresholds_db(self) -> List[float]:
        return [self._threshold_raw_to_db(value) for value in self.trigger_thresholds_raw]

    @trigger_thresholds_db.setter
    def trigger_thresholds_db(self, values):
        values = list(values)
        if len(values) != self.RANGE_GATE_COUNT:
            raise ValueError("Se requieren exactamente 16 thresholds")
        self.trigger_thresholds_raw = [self._threshold_db_to_raw(value) for value in values]

    @property
    def hold_thresholds_db(self) -> List[float]:
        return [self._threshold_raw_to_db(value) for value in self.hold_thresholds_raw]

    @hold_thresholds_db.setter
    def hold_thresholds_db(self, values):
        values = list(values)
        if len(values) != self.RANGE_GATE_COUNT:
            raise ValueError("Se requieren exactamente 16 thresholds")
        self.hold_thresholds_raw = [self._threshold_db_to_raw(value) for value in values]

    def get_trigger_threshold(self, gate: int, *, raw: bool = False):
        value = self._get_parameter(LD2420Parameter.trigger_gate(gate))
        return value if raw else self._threshold_raw_to_db(value)

    def set_trigger_threshold(self, gate: int, value: float, *, raw: bool = False):
        encoded = self._validate_threshold_raw(value) if raw else self._threshold_db_to_raw(value)
        return self._set_parameter(LD2420Parameter.trigger_gate(gate), encoded)

    def get_hold_threshold(self, gate: int, *, raw: bool = False):
        value = self._get_parameter(LD2420Parameter.hold_gate(gate))
        return value if raw else self._threshold_raw_to_db(value)

    def set_hold_threshold(self, gate: int, value: float, *, raw: bool = False):
        encoded = self._validate_threshold_raw(value) if raw else self._threshold_db_to_raw(value)
        return self._set_parameter(LD2420Parameter.hold_gate(gate), encoded)

    def set_trigger(self, gate, value):
        return self.set_trigger_threshold(gate, value, raw=True)

    def get_trigger(self, gate):
        return self.get_trigger_threshold(gate, raw=True)

    def set_hold(self, gate, value):
        return self.set_hold_threshold(gate, value, raw=True)

    def get_hold(self, gate):
        return self.get_hold_threshold(gate, raw=True)

    def set_trigger_thresholds(self, values):
        self.trigger_thresholds_raw = values

    def set_hold_thresholds(self, values):
        self.hold_thresholds_raw = values

    # Measurement frames
    def read_report(self) -> LD2420Report:
        self._wait_for_header(self.REPORT_HEADER)
        length = self._from_u16(self._read_exactly(2))
        if length != self.REPORT_LENGTH:
            raise RadarProtocolError(f"Longitud REPORT LD2420 inesperada: {length}")
        data = self._read_exactly(length)
        if self._read_exactly(4) != self.REPORT_FOOTER:
            raise RadarProtocolError("Footer REPORT LD2420 inválido")
        result = data[0]
        distance_cm = self._from_u16(data[1:3])
        energy = [
            self._from_u16(data[3 + 2 * gate : 5 + 2 * gate])
            for gate in range(self.RANGE_GATE_COUNT)
        ]
        return LD2420Report(result, distance_cm, energy)

    def read_debug_map(self) -> LD2420DebugMap:
        self._wait_for_header(self.DEBUG_HEADER)
        count = self.DOPPLER_BIN_COUNT * self.RANGE_GATE_COUNT
        raw = self._read_exactly(count * 4)
        if self._read_exactly(4) != self.DEBUG_FOOTER:
            raise RadarProtocolError("Footer DEBUG LD2420 inválido")
        flat = [self._from_u32(raw[i * 4 : i * 4 + 4]) for i in range(count)]
        values = [
            flat[row * self.RANGE_GATE_COUNT : (row + 1) * self.RANGE_GATE_COUNT]
            for row in range(self.DOPPLER_BIN_COUNT)
        ]
        return LD2420DebugMap(values)

    def readline(self):
        raw = self.uart.readline()
        if raw is None:
            return None
        try:
            return raw.decode("ascii").strip()
        except UnicodeError:
            return raw

    def read(self):
        if self.mode == LD2420Mode.RUN:
            return self.readline()
        if self.mode == LD2420Mode.REPORT:
            return self.read_report()
        return self.read_debug_map()
        
    # External background calibration
    @staticmethod
    def _percentile(values: Sequence[int], fraction: float) -> float:
        """Linearly interpolated percentile without requiring NumPy."""
        ordered = sorted(values)
        if not ordered:
            raise ValueError("No hay muestras para calcular el percentil")
        position = (len(ordered) - 1) * float(fraction)
        lower = int(position)
        upper = min(lower + 1, len(ordered) - 1)
        weight = position - lower
        return ordered[lower] * (1.0 - weight) + ordered[upper] * weight

    def calibrate(
        self,
        *,
        samples: int = 300,
        warmup_frames: int = 10,
        trigger_factor: float = 5.0,
        hold_factor: float = 3.0,
        instability_ratio: float = 3.0,
        apply: bool = False,
    ) -> LD2420CalibrationResult:
        """Estimate per-gate thresholds from an empty-room REPORT capture.

        The method temporarily selects REPORT mode, discards ``warmup_frames``,
        captures ``samples`` frames and restores the previous output mode even
        if acquisition fails. By default it only returns recommendations;
        ``apply=True`` writes both threshold banks after a successful capture.
        """
        samples = int(samples)
        warmup_frames = int(warmup_frames)
        trigger_factor = float(trigger_factor)
        hold_factor = float(hold_factor)
        instability_ratio = float(instability_ratio)
        if samples < 2:
            raise ValueError("samples debe ser al menos 2")
        if warmup_frames < 0:
            raise ValueError("warmup_frames no puede ser negativo")
        if trigger_factor <= 0 or hold_factor <= 0:
            raise ValueError("Los factores de threshold deben ser positivos")
        if instability_ratio <= 1:
            raise ValueError("instability_ratio debe ser mayor que 1")
        
        
        print("Calibración LD2402")
        print("WARNING!")
        print("Asegurese de que el radar no tenga ningun objetivo detectable durante la calibración.")
        print("Despues de aceptar la calibración, tendra 20 segundos para alejarse del sensor.")
        sel=input("Desea continuar (y/n)?")
        if sel=="y":
            sleep(20)
        else:
            return
            
            
        previous_mode = self.mode
        changed_mode = previous_mode != LD2420Mode.REPORT
        columns = [[] for _ in range(self.RANGE_GATE_COUNT)]
        try:
            if changed_mode:
                self.mode = LD2420Mode.REPORT
            for _ in range(warmup_frames):
                self.read_report()
            for _ in range(samples):
                report = self.read_report()
                if len(report.energy) != self.RANGE_GATE_COUNT:
                    raise RadarProtocolError("REPORT sin las 16 energías esperadas")
                for gate, energy in enumerate(report.energy):
                    columns[gate].append(int(energy))
        finally:
            if changed_mode:
                self.mode = previous_mode

        background = [self._percentile(column, 0.50) for column in columns]
        percentile95 = [self._percentile(column, 0.95) for column in columns]
        percentile99 = [self._percentile(column, 0.99) for column in columns]
        maximum = [max(column) for column in columns]
        trigger = [
            min(self.THRESHOLD_RAW_MAX, int(round(value * trigger_factor)))
            for value in percentile99
        ]
        hold = [
            min(trigger[gate], self.THRESHOLD_RAW_MAX, int(round(value * hold_factor)))
            for gate, value in enumerate(percentile95)
        ]
        unstable = tuple(
            gate
            for gate in range(self.RANGE_GATE_COUNT)
            if background[gate] <= 0
            or percentile99[gate] / background[gate] >= instability_ratio
        )
        result = LD2420CalibrationResult(
            sample_count=samples,
            background_raw=background,
            percentile95_raw=percentile95,
            percentile99_raw=percentile99,
            maximum_raw=maximum,
            trigger_thresholds_raw=trigger,
            hold_thresholds_raw=hold,
            unstable_gates=unstable,
        )
        if apply:
            result.apply(self)
        return result
        
    
    
    
    
    
    
    
    
    
    
    
    

    # Optional GPIO presence output
    @property
    def gpio_presence(self) -> Optional[bool]:
        return None if self._presence_input is None else bool(self._presence_input.is_active)

    @property
    def presence_pin(self) -> Optional[int]:
        return None if self._presence_input is None else int(self._presence_input.pin.number)

    @presence_pin.setter
    def presence_pin(self, number: Optional[int]):
        if self._presence_input is not None:
            self._presence_input.close()
            self._presence_input = None
        if number is None:
            return
        try:
            from gpiozero import DigitalInputDevice
        except ImportError as exc:
            raise ImportError("presence_pin requiere gpiozero: pip install gpiozero") from exc
        self._presence_input = DigitalInputDevice(
            number,
            pull_up=False,
            bounce_time=self._bounce_time,
        )
        self._presence_input.when_activated = self._when_presence_detected
        self._presence_input.when_deactivated = self._when_presence_cleared

    @property
    def when_presence_detected(self) -> Optional[Callable[[], None]]:
        return self._when_presence_detected

    @when_presence_detected.setter
    def when_presence_detected(self, callback: Optional[Callable[[], None]]):
        if callback is not None and not callable(callback):
            raise TypeError("when_presence_detected debe ser callable o None")
        self._when_presence_detected = callback
        if self._presence_input is not None:
            self._presence_input.when_activated = callback

    @property
    def when_presence_cleared(self) -> Optional[Callable[[], None]]:
        return self._when_presence_cleared

    @when_presence_cleared.setter
    def when_presence_cleared(self, callback: Optional[Callable[[], None]]):
        if callback is not None and not callable(callback):
            raise TypeError("when_presence_cleared debe ser callable o None")
        self._when_presence_cleared = callback
        if self._presence_input is not None:
            self._presence_input.when_deactivated = callback

    def close(self):
        if self._presence_input is not None:
            self._presence_input.close()
            self._presence_input = None
        close = getattr(self.uart, "close", None)
        if callable(close):
            close()
