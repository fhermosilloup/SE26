"""Full driver for the Hi-Link HLK-LD2402 radar module.

Protocol notes
--------------
* UART configuration protocol: little-endian.
* Command header: FD FC FB FA
* Command footer: 04 03 02 01
* Engineering/REPORT mode payload: 131 bytes =
  1-byte detection result + 2-byte target distance +
  16 x uint32 motion energies + 16 x uint32 micro-motion energies.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from enum import IntEnum
from math import log10
from typing import Callable, Iterable, List, Optional, Sequence, Tuple, Union

from .base import RadarProtocolError, RadarUARTBase
import time


class LD2402Command(IntEnum):
    """HLK-LD2402 command words.

    Every member also exposes:

    ``description``
        Human-readable purpose.
    ``accepted_values``
        Payload/accepted-value documentation.
    ``min_firmware``
        Minimum firmware explicitly stated by the manual, when applicable.
    ``documented``
        False only for backwards-compatible commands not present in the
        currently documented LD2402 command table.
    """

    def __new__(
        cls,
        value: int,
        description: str,
        accepted_values: str,
        min_firmware: Optional[str] = None,
        documented: bool = True,
    ):
        obj = int.__new__(cls, value)
        obj._value_ = value
        obj.description = description
        obj.accepted_values = accepted_values
        obj.min_firmware = min_firmware
        obj.documented = documented
        return obj

    READ_FIRMWARE_VERSION = (
        0x0000,
        "Read firmware version.",
        "No payload. Returns uint16 length + ASCII version bytes.",
    )
    SET_PARAMETERS = (
        0x0007,
        "Write one or more sensor parameters.",
        "Payload: (uint16 parameter_id + uint32 raw_value) * N.",
    )
    GET_PARAMETERS = (
        0x0008,
        "Read one or more sensor parameters.",
        "Payload: uint16 parameter_id * N; returns uint32 raw_value * N.",
    )
    START_AUTO_THRESHOLD = (
        0x0009,
        "Start automatic threshold generation.",
        "Three uint16 coefficients: trigger, hold, micro; each raw 10..200 "
        "representing 1.0..20.0 in steps of 0.1.",
    )
    AUTO_THRESHOLD_PROGRESS = (
        0x000A,
        "Read automatic-threshold generation progress.",
        "No payload. Returns uint16 percentage, normally 0..100.",
    )
    WRITE_SERIAL_LEGACY = (
        0x0010,
        "Write serial number (legacy command documented in older LD2402 manuals).",
        "Payload: uint16 SN length + SN bytes. V1.05 documents a 2-byte SN; "
        "this command is no longer listed in the V1.08 command table.",
        None,
        False,
    )
    READ_SERIAL_ASCII = (
        0x0011,
        "Read serial number in character form.",
        "No payload. Returns uint16 length + N serial-number bytes. "
        "Firmware older than 3.3.5 may return hexadecimal-form data instead.",
    )
    SET_OUTPUT_MODE = (
        0x0012,
        "Configure UART data output mode.",
        "Payload: uint16 0x0000 + uint32 mode. Documented modes: "
        "0x00000004 engineering/REPORT, 0x00000064 normal/RUN.",
    )
    AUTO_THRESHOLD_INTERFERENCE = (
        0x0014,
        "Query interference detected during automatic threshold generation.",
        "No payload. Response status 0=no interference, 1=interference; "
        "returns a 16-bit affected-gate mask.",
    )
    READ_SERIAL_HEX = (
        0x0016,
        "Read serial number in hexadecimal/binary form.",
        "No payload. Returns uint16 length + N serial-number bytes.",
        "3.3.5",
    )
    SAVE_PARAMETERS = (
        0x00FD,
        "Persist the current configuration across power loss.",
        "No payload. Send after parameter writes, before ending configuration.",
        "3.3.2",
    )
    AUTO_GAIN_ADJUST = (
        0x00EE,
        "Start automatic internal gain adjustment.",
        "No payload. Immediate ACK is followed later by message 0x00F0 "
        "when adjustment completes.",
        "3.3.5",
    )
    END_CONFIGURATION = (
        0x00FE,
        "Exit configuration mode and resume sensor operation.",
        "No payload.",
    )
    ENABLE_CONFIGURATION = (
        0x00FF,
        "Enter configuration mode. Required before configuration commands.",
        "Payload: uint16 0x0001. Returns protocol version and buffer size.",
    )

    # Present in the user's previous implementation / some related Hi-Link
    # drivers, but not present in the documented LD2402 V1.08 command table.
    # Kept only to avoid silently breaking existing applications.
    RESTART_UNDOCUMENTED = (
        0x0068,
        "Legacy/undocumented restart command retained for compatibility.",
        "No documented LD2402 payload or support guarantee.",
        None,
        False,
    )


class LD2402Message(IntEnum):
    """Asynchronous command-protocol messages sent by the radar."""

    AUTO_GAIN_COMPLETE = 0x00F0


class LD2402Mode(IntEnum):
    """Documented UART output modes.

    ENGINEERING/REPORT (0x04)
        Binary engineering frames with result, distance, and 32 energy values.
    NORMAL/RUN (0x64)
        Normal ASCII output such as ``OFF`` and ``distance:158``.
    """

    ENGINEERING = 0x04
    REPORT = 0x04  # backwards-compatible alias
    NORMAL = 0x64
    RUN = 0x64  # backwards-compatible alias


class LD2402DetectionState(IntEnum):
    NONE = 0x00
    PRESENT = 0x01
    STATIONARY = 0x02


class LD2402PowerInterference(IntEnum):
    """Read-only value of parameter 0x0005."""
    NOT_TESTED = 0
    NO_INTERFERENCE = 1
    INTERFERENCE = 2


class LD2402Parameter(IntEnum):
    """Documented sensor parameter IDs.

    Scalar parameters
    -----------------
    MAX_DISTANCE = 0x0001
        Raw value is decimeters. Manual revisions differ slightly on the
        configurable limit (older documentation shows 0..120; later material
        shows 7..100). Physical/effective motion sensing is specified to 10 m.
    DISAPPEARANCE_DELAY = 0x0004
        0..65535 seconds.
    POWER_INTERFERENCE = 0x0005
        Read-only: 0=not tested, 1=no interference, 2=interference.

    Threshold banks
    ---------------
    TRIGGER_GATE_0..15 = 0x0010..0x001F
        Motion/trigger thresholds.
    MICRO_GATE_0..15 = 0x0030..0x003F
        Micro-motion/stationary thresholds.

    The PC-tool threshold scale is 0..95 dB and is related to the raw uint32
    UART value M by N = 10*log10(M).
    """

    MAX_DISTANCE = 0x0001
    DISAPPEARANCE_DELAY = 0x0004
    POWER_INTERFERENCE = 0x0005

    TRIGGER_GATE_0 = 0x0010
    TRIGGER_GATE_1 = 0x0011
    TRIGGER_GATE_2 = 0x0012
    TRIGGER_GATE_3 = 0x0013
    TRIGGER_GATE_4 = 0x0014
    TRIGGER_GATE_5 = 0x0015
    TRIGGER_GATE_6 = 0x0016
    TRIGGER_GATE_7 = 0x0017
    TRIGGER_GATE_8 = 0x0018
    TRIGGER_GATE_9 = 0x0019
    TRIGGER_GATE_10 = 0x001A
    TRIGGER_GATE_11 = 0x001B
    TRIGGER_GATE_12 = 0x001C
    TRIGGER_GATE_13 = 0x001D
    TRIGGER_GATE_14 = 0x001E
    TRIGGER_GATE_15 = 0x001F

    MICRO_GATE_0 = 0x0030
    MICRO_GATE_1 = 0x0031
    MICRO_GATE_2 = 0x0032
    MICRO_GATE_3 = 0x0033
    MICRO_GATE_4 = 0x0034
    MICRO_GATE_5 = 0x0035
    MICRO_GATE_6 = 0x0036
    MICRO_GATE_7 = 0x0037
    MICRO_GATE_8 = 0x0038
    MICRO_GATE_9 = 0x0039
    MICRO_GATE_10 = 0x003A
    MICRO_GATE_11 = 0x003B
    MICRO_GATE_12 = 0x003C
    MICRO_GATE_13 = 0x003D
    MICRO_GATE_14 = 0x003E
    MICRO_GATE_15 = 0x003F

    @staticmethod
    def trigger_gate(gate: int) -> "LD2402Parameter":
        if not 0 <= gate <= 15:
            raise ValueError("gate debe estar entre 0 y 15")
        return LD2402Parameter(0x0010 + gate)

    @staticmethod
    def micro_gate(gate: int) -> "LD2402Parameter":
        if not 0 <= gate <= 15:
            raise ValueError("gate debe estar entre 0 y 15")
        return LD2402Parameter(0x0030 + gate)


@dataclass(frozen=True)
class LD2402ConfigurationInfo:
    protocol_version: int
    buffer_size: int


@dataclass(frozen=True)
class LD2402ThresholdInterference:
    """Result of command 0x0014."""

    interference: bool
    gate_mask: int

    @property
    def gates(self) -> Tuple[int, ...]:
        return tuple(i for i in range(16) if self.gate_mask & (1 << i))


@dataclass(frozen=True)
class LD2402Report:
    """One LD2402 engineering/REPORT-mode measurement.

    ``energy`` is kept for backwards compatibility and contains 32 raw uint32
    values. The first 16 are motion energy gates and the final 16 are
    micro-motion/static energy gates.
    """

    result: int
    distance_cm: int
    energy: List[int]

    @property
    def presence(self) -> bool:
        return self.result != LD2402DetectionState.NONE

    @property
    def stationary(self) -> bool:
        return self.result == LD2402DetectionState.STATIONARY

    @property
    def motion_energy(self) -> List[int]:
        return self.energy[:16]

    @property
    def micro_energy(self) -> List[int]:
        return self.energy[16:32]

    @staticmethod
    def _to_db(values: Sequence[int]) -> List[float]:
        return [float("-inf") if value <= 0 else 10.0 * log10(value) for value in values]

    @property
    def motion_energy_db(self) -> List[float]:
        return self._to_db(self.motion_energy)

    @property
    def micro_energy_db(self) -> List[float]:
        return self._to_db(self.micro_energy)


class LD2402(RadarUARTBase):
    """Complete HLK-LD2402 driver.

    High-level configuration attributes are properties. The driver enters and
    exits configuration mode automatically for property access, unless the
    caller groups operations inside ``with radar.configuration():``.

    Parameters
    ----------
    uart:
        pyserial-compatible serial object.
    debug:
        Forwarded to :class:`RadarUARTBase`.
    frame_timeout:
        Forwarded to :class:`RadarUARTBase`.
    presence_pin:
        Optional BCM GPIO number connected to LD2402 IO/OT. If provided,
        gpiozero is used for event callbacks.
    bounce_time:
        gpiozero debounce time in seconds.
    """

    COMMAND_HEADER = b"\xFD\xFC\xFB\xFA"
    COMMAND_FOOTER = b"\x04\x03\x02\x01"

    REPORT_HEADER = b"\xF4\xF3\xF2\xF1"
    REPORT_FOOTER = b"\xF8\xF7\xF6\xF5"

    REPORT_LENGTH = 0x83
    THRESHOLD_GATE_COUNT = 16
    ENERGY_VALUE_COUNT = 32
    GATE_SIZE_M = 0.70

    # Conservative protocol limits. Older manual revisions accept 0..120 raw
    # (0..12 m), while later revisions document a 10 m configuration/effective
    # limit. Allowing 12 m preserves compatibility; physical specified range is
    # still 10 m.
    MAX_DISTANCE_RAW_MIN = 0
    MAX_DISTANCE_RAW_MAX = 120

    def __init__(
        self,
        uart,
        *,
        debug: bool = False,
        frame_timeout: float = 1.0,
        presence_pin: Optional[int] = None,
        bounce_time: float = 0.03
    ):
        super().__init__(uart, debug=debug, frame_timeout=frame_timeout)
        self._mode = LD2402Mode.NORMAL
        self._configuration_depth = 0
        self._configuration_enabled = False
        self._last_configuration_info: Optional[LD2402ConfigurationInfo] = None

        self._presence_input = None
        self._when_presence_detected: Optional[Callable[[], None]] = None
        self._when_presence_cleared: Optional[Callable[[], None]] = None

        if presence_pin is not None:
            try:
                from gpiozero import DigitalInputDevice
            except ImportError as exc:
                raise ImportError(
                    "presence_pin requiere gpiozero: pip install gpiozero"
                ) from exc

            self._presence_input = DigitalInputDevice(
                presence_pin,
                pull_up=False,
                bounce_time=bounce_time,
            )

    # Configuration session
    def enable_command_mode(self) -> LD2402ConfigurationInfo:
        """Enter configuration mode (command 0x00FF)."""
        response = self._require_success(
            self._command(
                LD2402Command.ENABLE_CONFIGURATION,
                self._u16(0x0001),
            ),
            "enable_command_mode",
        )
        data = response.data
        protocol_version = self._from_u16(data[0:2]) if len(data) >= 2 else 0
        buffer_size = self._from_u16(data[2:4]) if len(data) >= 4 else 0
        info = LD2402ConfigurationInfo(protocol_version, buffer_size)
        self._last_configuration_info = info
        self._configuration_enabled = True
        return info

    def disable_command_mode(self):
        """Exit configuration mode (command 0x00FE)."""
        response = self._require_success(
            self._command(LD2402Command.END_CONFIGURATION),
            "disable_command_mode",
        )
        self._configuration_enabled = False
        return response
    
    
    
    def calibrate(self):
        print("Calibración LD2402")
        print("WARNING!")
        print("Asegurese de que el radar no tenga ningun objetivo detectable durante la calibración.")
        print("Despues de aceptar la calibración, tendra 20 segundos para alejarse del sensor.")
        sel=input("Desea continuar (y/n)?")
        if sel=="y":
            time.sleep(20)
        else:
            return
        
        print("1. Gain calibración")
        self.automatic_gain_adjustment(wait=True)
        
        print("2. Threshold calibración")
            
        radar.generate_thresholds(
            trigger=5.0,
            hold=3.0,
            micro=3.0,
        )

        while True:
            progress = self.threshold_generation_progress
            print(f"Calibración: {progress}%")

            if progress >= 99:
                break
            time.sleep(1)
        
        time.sleep(3)
        print("Calibración: 100%")

        info = self.threshold_generation_interference
        if info.interference:
            print("Se detectó interferencia")
            print("Gates afectados:", info.gates)
        else:
            print("Calibración sin interferencias")
            self.save_parameters()
        
        

    @contextmanager
    def configuration(self):
        """Group several reads/writes in one configuration-mode session."""
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
    def configuration_info(self) -> Optional[LD2402ConfigurationInfo]:
        """Information returned by the last 0x00FF command."""
        return self._last_configuration_info

    
    # Generic low-level parameter access
    

    def get_parameters(self, *parameters: Union[int, LD2402Parameter]):
        """Read arbitrary parameter IDs; use high-level properties when possible."""
        if not parameters:
            raise ValueError("Debes indicar al menos un parámetro")

        with self.configuration():
            response = self._require_success(
                self._command(
                    LD2402Command.GET_PARAMETERS,
                    b"".join(self._u16(int(p)) for p in parameters),
                ),
                "get_parameters",
            )

        if len(response.data) < 4 * len(parameters):
            raise RadarProtocolError("Respuesta de parámetros incompleta")

        return {
            p: self._from_u32(response.data[i * 4 : i * 4 + 4])
            for i, p in enumerate(parameters)
        }

    def set_parameters(self, parameters):
        """Write arbitrary raw parameter IDs; use high-level properties when possible."""
        if not parameters:
            raise ValueError("parameters no puede estar vacío")

        payload = bytearray()
        for parameter, value in parameters.items():
            if not 0 <= int(value) <= 0xFFFFFFFF:
                raise ValueError("Los valores raw deben caber en uint32")
            payload += self._u16(int(parameter))
            payload += self._u32(int(value))

        with self.configuration():
            return self._require_success(
                self._command(LD2402Command.SET_PARAMETERS, bytes(payload)),
                "set_parameters",
            )

    def _get_parameter(self, parameter: Union[int, LD2402Parameter]) -> int:
        return next(iter(self.get_parameters(parameter).values()))

    def _set_parameter(self, parameter: Union[int, LD2402Parameter], value: int):
        return self.set_parameters({parameter: value})

    
    # Device-information properties
    

    @property
    def firmware_version(self):
        """Firmware version string (command 0x0000)."""
        with self.configuration():
            response = self._require_success(
                self._command(LD2402Command.READ_FIRMWARE_VERSION),
                "firmware_version",
            )
        data = response.data
        if len(data) >= 2:
            length = self._from_u16(data[:2])
            if 0 <= length <= len(data) - 2:
                data = data[2 : 2 + length]
        try:
            return data.decode("ascii").rstrip("\x00")
        except UnicodeError:
            return bytes(data)

    # backwards compatibility
    def get_version(self):
        return self.firmware_version

    def write_serial_number_legacy(self, serial_number: Union[bytes, bytearray, str]):
        """Write the legacy serial-number field using command 0x0010.

        This command is documented in older LD2402 manuals (for example V1.05)
        but is absent from the V1.08 command table. Use only when you know your
        firmware supports it.
        """
        if isinstance(serial_number, str):
            payload_bytes = serial_number.encode("ascii")
        else:
            payload_bytes = bytes(serial_number)
        if not 1 <= len(payload_bytes) <= 0xFFFF:
            raise ValueError("serial_number debe contener entre 1 y 65535 bytes")
        payload = self._u16(len(payload_bytes)) + payload_bytes
        with self.configuration():
            return self._require_success(
                self._command(LD2402Command.WRITE_SERIAL_LEGACY, payload),
                "write_serial_number_legacy",
            )

    @property
    def serial_number(self):
        """Serial number using character-form command 0x0011."""
        with self.configuration():
            response = self._require_success(
                self._command(LD2402Command.READ_SERIAL_ASCII),
                "serial_number",
            )
        data = self._decode_length_prefixed(response.data)
        try:
            return data.decode("ascii").rstrip("\x00")
        except UnicodeError:
            return bytes(data)

    @property
    def serial_number_hex(self) -> str:
        """Serial number using command 0x0016; firmware >= 3.3.5."""
        with self.configuration():
            response = self._require_success(
                self._command(LD2402Command.READ_SERIAL_HEX),
                "serial_number_hex",
            )
        return self._decode_length_prefixed(response.data).hex().upper()

    def _decode_length_prefixed(self, data: bytes) -> bytes:
        if len(data) < 2:
            raise RadarProtocolError("Respuesta sin longitud")
        length = self._from_u16(data[:2])
        if length > len(data) - 2:
            raise RadarProtocolError("Longitud declarada mayor que la respuesta")
        return bytes(data[2 : 2 + length])

    
    # Scalar configuration properties
    

    @property
    def maximum_distance_m(self) -> float:
        """Configured maximum distance in metres (raw parameter is decimetres)."""
        return self._get_parameter(LD2402Parameter.MAX_DISTANCE) / 10.0

    @maximum_distance_m.setter
    def maximum_distance_m(self, value: float):
        raw = int(round(float(value) * 10.0))
        if not self.MAX_DISTANCE_RAW_MIN <= raw <= self.MAX_DISTANCE_RAW_MAX:
            raise ValueError("maximum_distance_m debe estar entre 0.0 y 12.0 m")
        self._set_parameter(LD2402Parameter.MAX_DISTANCE, raw)

    @property
    def disappearance_delay_s(self) -> int:
        """Delay before reporting no target, in seconds (0..65535)."""
        return self._get_parameter(LD2402Parameter.DISAPPEARANCE_DELAY)

    @disappearance_delay_s.setter
    def disappearance_delay_s(self, value: int):
        value = int(value)
        if not 0 <= value <= 65535:
            raise ValueError("disappearance_delay_s debe estar entre 0 y 65535")
        self._set_parameter(LD2402Parameter.DISAPPEARANCE_DELAY, value)

    @property
    def power_supply_interference(self):
        """Read-only power-supply self-test state (parameter 0x0005)."""
        raw = self._get_parameter(LD2402Parameter.POWER_INTERFERENCE)
        try:
            return LD2402PowerInterference(raw)
        except ValueError:
            return raw

    
    # Output mode property
    

    @property
    def mode(self) -> LD2402Mode:
        """Cached UART output mode; the protocol provides a setter but no mode query."""
        return self._mode

    @mode.setter
    def mode(self, value: Union[int, LD2402Mode]):
        mode = LD2402Mode(value)
        with self.configuration():
            self._require_success(
                self._command(
                    LD2402Command.SET_OUTPUT_MODE,
                    self._u16(0x0000) + self._u32(int(mode)),
                ),
                "mode",
            )
        self._mode = mode

    @property
    def output_mode(self) -> LD2402Mode:
        return self.mode

    @output_mode.setter
    def output_mode(self, value: Union[int, LD2402Mode]):
        self.mode = value

    # backwards compatibility
    def set_mode(self, mode):
        self.mode = mode
        return self.mode

    
    # Threshold properties
    

    @staticmethod
    def _threshold_db_to_raw(value_db: float) -> int:
        value_db = float(value_db)
        if not 0.0 <= value_db <= 95.0:
            raise ValueError("El threshold debe estar entre 0 y 95 dB")
        raw = int(round(10.0 ** (value_db / 10.0)))
        return min(raw, 0xFFFFFFFF)

    @staticmethod
    def _threshold_raw_to_db(raw: int) -> float:
        raw = int(raw)
        if raw <= 0:
            return 0.0
        return 10.0 * log10(raw)

    def _get_threshold_bank_raw(self, start: int) -> List[int]:
        parameters = tuple(start + i for i in range(self.THRESHOLD_GATE_COUNT))
        values = self.get_parameters(*parameters)
        return [values[p] for p in parameters]

    def _set_threshold_bank_raw(self, start: int, values: Iterable[int]):
        values = list(values)
        if len(values) != self.THRESHOLD_GATE_COUNT:
            raise ValueError("Se requieren exactamente 16 thresholds")
        parameters = {}
        for i, value in enumerate(values):
            value = int(value)
            if not 0 <= value <= 0xFFFFFFFF:
                raise ValueError("Cada threshold raw debe caber en uint32")
            parameters[start + i] = value
        self.set_parameters(parameters)

    @property
    def trigger_thresholds_raw(self) -> List[int]:
        """16 raw uint32 motion/trigger thresholds, gates 0..15."""
        return self._get_threshold_bank_raw(0x0010)

    @trigger_thresholds_raw.setter
    def trigger_thresholds_raw(self, values: Iterable[int]):
        self._set_threshold_bank_raw(0x0010, values)

    @property
    def micro_thresholds_raw(self) -> List[int]:
        """16 raw uint32 micro-motion/stationary thresholds, gates 0..15."""
        return self._get_threshold_bank_raw(0x0030)

    @micro_thresholds_raw.setter
    def micro_thresholds_raw(self, values: Iterable[int]):
        self._set_threshold_bank_raw(0x0030, values)

    @property
    def trigger_thresholds_db(self) -> List[float]:
        """16 motion/trigger thresholds in the PC-tool 0..95 dB scale."""
        return [self._threshold_raw_to_db(v) for v in self.trigger_thresholds_raw]

    @trigger_thresholds_db.setter
    def trigger_thresholds_db(self, values: Iterable[float]):
        values = list(values)
        if len(values) != self.THRESHOLD_GATE_COUNT:
            raise ValueError("Se requieren exactamente 16 thresholds")
        self.trigger_thresholds_raw = [self._threshold_db_to_raw(v) for v in values]

    @property
    def micro_thresholds_db(self) -> List[float]:
        """16 micro-motion/stationary thresholds in the PC-tool 0..95 dB scale."""
        return [self._threshold_raw_to_db(v) for v in self.micro_thresholds_raw]

    @micro_thresholds_db.setter
    def micro_thresholds_db(self, values: Iterable[float]):
        values = list(values)
        if len(values) != self.THRESHOLD_GATE_COUNT:
            raise ValueError("Se requieren exactamente 16 thresholds")
        self.micro_thresholds_raw = [self._threshold_db_to_raw(v) for v in values]

    def get_trigger_threshold(self, gate: int, *, raw: bool = False):
        """Read one trigger threshold; a method is appropriate because gate is an index."""
        parameter = LD2402Parameter.trigger_gate(gate)
        value = self._get_parameter(parameter)
        return value if raw else self._threshold_raw_to_db(value)

    def set_trigger_threshold(self, gate: int, value: float, *, raw: bool = False):
        parameter = LD2402Parameter.trigger_gate(gate)
        encoded = int(value) if raw else self._threshold_db_to_raw(value)
        return self._set_parameter(parameter, encoded)

    def get_micro_threshold(self, gate: int, *, raw: bool = False):
        parameter = LD2402Parameter.micro_gate(gate)
        value = self._get_parameter(parameter)
        return value if raw else self._threshold_raw_to_db(value)

    def set_micro_threshold(self, gate: int, value: float, *, raw: bool = False):
        parameter = LD2402Parameter.micro_gate(gate)
        encoded = int(value) if raw else self._threshold_db_to_raw(value)
        return self._set_parameter(parameter, encoded)

    # Backwards-compatible names. The old implementation called 0x20..0x3F
    # "hold" thresholds, but that bank is not documented by the LD2402 manual.
    def set_trigger(self, gate, value):
        return self.set_trigger_threshold(gate, value, raw=True)

    def set_trigger_thresholds(self, values):
        self.trigger_thresholds_raw = values

    
    # Automatic threshold generation
    

    @staticmethod
    def _encode_coefficient(value: float) -> int:
        value = float(value)
        if not 1.0 <= value <= 20.0:
            raise ValueError("El coeficiente debe estar entre 1.0 y 20.0")
        return int(round(value * 10.0))

    def generate_thresholds(
        self,
        trigger: float = 3.0,
        hold: float = 2.0,
        micro: float = 3.0,
    ):
        """Start automatic threshold generation (command 0x0009).

        Coefficients accept 1.0..20.0. The protocol transmits each value x10.
        This is an action rather than a property because it starts a process.
        """
        payload = (
            self._u16(self._encode_coefficient(trigger))
            + self._u16(self._encode_coefficient(hold))
            + self._u16(self._encode_coefficient(micro))
        )
        with self.configuration():
            return self._require_success(
                self._command(LD2402Command.START_AUTO_THRESHOLD, payload),
                "generate_thresholds",
            )

    @property
    def threshold_generation_progress(self) -> int:
        """Automatic-threshold progress percentage, normally 0..100."""
        with self.configuration():
            response = self._require_success(
                self._command(LD2402Command.AUTO_THRESHOLD_PROGRESS),
                "threshold_generation_progress",
            )
        if len(response.data) < 2:
            raise RadarProtocolError("Respuesta de progreso incompleta")
        return self._from_u16(response.data[:2])

    @staticmethod
    def _response_status(response) -> int:
        """Best-effort compatibility with common RadarUARTBase response shapes."""
        for name in ("status", "ack", "code"):
            if hasattr(response, name):
                value = getattr(response, name)
                if isinstance(value, bool):
                    return 0 if value else 1
                return int(value)
        if hasattr(response, "success"):
            return 0 if bool(getattr(response, "success")) else 1
        raise RadarProtocolError(
            "RadarUARTBase response debe exponer status/ack/code/success "
            "para interpretar 0x0014"
        )

    @property
    def threshold_generation_interference(self) -> LD2402ThresholdInterference:
        """Interference status and affected 16-gate mask from command 0x0014."""
        with self.configuration():
            # Do NOT use _require_success(): for this command status==1 means
            # "interference detected", which is data, not a transport failure.
            response = self._command(LD2402Command.AUTO_THRESHOLD_INTERFERENCE)

        status = self._response_status(response)
        if status not in (0, 1):
            raise RadarProtocolError(f"Estado 0x0014 inesperado: {status}")
        if len(response.data) < 2:
            raise RadarProtocolError("Respuesta 0x0014 sin máscara de gates")
        gate_mask = self._from_u16(response.data[:2])
        return LD2402ThresholdInterference(bool(status), gate_mask)

    
    # Save / gain / legacy actions
    

    def save_parameters(self):
        """Persist configuration to nonvolatile storage; firmware >= 3.3.2."""
        with self.configuration():
            return self._require_success(
                self._command(LD2402Command.SAVE_PARAMETERS),
                "save_parameters",
            )

    def automatic_gain_adjustment(self, *, wait: bool = False):
        """Start automatic gain adjustment; firmware >= 3.3.5.

        If ``wait=True``, also wait for asynchronous completion message 0x00F0.
        """
        with self.configuration():
            response = self._require_success(
                self._command(LD2402Command.AUTO_GAIN_ADJUST),
                "automatic_gain_adjustment",
            )
            if wait:
                self._wait_for_gain_complete()
        return response

    def _wait_for_gain_complete(self):
        self._wait_for_header(self.COMMAND_HEADER)
        length = self._from_u16(self._read_exactly(2))
        data = self._read_exactly(length)
        if self._read_exactly(4) != self.COMMAND_FOOTER:
            raise RadarProtocolError("Footer de auto-gain inválido")
        if len(data) < 4:
            raise RadarProtocolError("Respuesta de auto-gain incompleta")
        command = self._from_u16(data[:2])
        status = self._from_u16(data[2:4])
        if command != LD2402Message.AUTO_GAIN_COMPLETE:
            raise RadarProtocolError(
                f"Se esperaba 0x00F0 y se recibió 0x{command:04X}"
            )
        if status != 1:
            raise RadarProtocolError(
                f"Estado de finalización auto-gain inesperado: {status}"
            )
        return True

    def restart(self):
        """Legacy command 0x0068; not documented in the LD2402 command table."""
        with self.configuration():
            return self._require_success(
                self._command(LD2402Command.RESTART_UNDOCUMENTED),
                "restart",
            )

    # REPORT / NORMAL data reading
    def read_report(self) -> LD2402Report:
        """Read one 131-byte engineering report."""
        self._wait_for_header(self.REPORT_HEADER)
        length = self._from_u16(self._read_exactly(2))
        if length != self.REPORT_LENGTH:
            raise RadarProtocolError(
                f"Longitud REPORT LD2402 inesperada: {length}"
            )

        data = self._read_exactly(length)
        if self._read_exactly(4) != self.REPORT_FOOTER:
            raise RadarProtocolError("Footer REPORT LD2402 inválido")

        result = data[0]
        distance = self._from_u16(data[1:3])
        energy = [
            self._from_u32(data[3 + 4 * i : 7 + 4 * i])
            for i in range(self.ENERGY_VALUE_COUNT)
        ]
        return LD2402Report(result, distance, energy)

    def readline(self):
        raw = self.uart.readline()
        if raw is None:
            return None
        try:
            return raw.decode("ascii").strip()
        except UnicodeError:
            return raw

    def read_debug(self):
        """Read currently buffered bytes without interpreting them."""
        waiting = int(getattr(self.uart, "in_waiting", 0) or 0)
        return self.uart.read(waiting) if waiting > 0 else None

    def read(self):
        if self.mode == LD2402Mode.NORMAL:
            return self.readline()
        if self.mode == LD2402Mode.ENGINEERING:
            return self.read_report()
        return self.read_debug()


    @property
    def gpio_presence(self) -> Optional[bool]:
        """Current IO/OT state, or None when no presence_pin was configured."""
        if self._presence_input is None:
            return None
        return bool(self._presence_input.is_active)

    @property
    def presence_pin(self) -> Optional[int]:
        if self._presence_input is None:
            return None
        return int(self._presence_input.pin.number)
    @presence_pin.setter
    def presence_pin(self, num):
        if self._presence_input is None:
            if num is not None:
                try:
                    from gpiozero import DigitalInputDevice
                except ImportError as exc:
                    raise ImportError("presence_pin requiere gpiozero: pip install gpiozero") from exc

                self._presence_input = DigitalInputDevice(num, pull_up=False, bounce_time=bounce_time)
                self._presence_input.when_activated = None
                self._presence_input.when_deactivated = None
    

    @property
    def when_presence_detected(self) -> Optional[Callable[[], None]]:
        return self._when_presence_detected

    @when_presence_detected.setter
    def when_presence_detected(self, callback: Optional[Callable[[], None]]):
        if self._presence_input is None:
            raise TypeError("presence_pin no se ha asignado")
        if callback is not None and not callable(callback):
            raise TypeError("when_presence_detected debe ser callable o None")
        self._when_presence_detected = callback
        self._presence_input.when_activated = self._when_presence_detected

    @property
    def when_presence_cleared(self) -> Optional[Callable[[], None]]:
        return self._when_presence_cleared

    @when_presence_cleared.setter
    def when_presence_cleared(self, callback: Optional[Callable[[], None]]):
        if self._presence_input is None:
            raise TypeError("presence_pin no se ha asignado")
        if callback is not None and not callable(callback):
            raise TypeError("when_presence_cleared debe ser callable o None")
        self._when_presence_cleared = callback
        self._presence_input.when_deactivated = self._when_presence_cleared

    def close(self):
        if self._presence_input is not None:
            self._presence_input.close()
            self._presence_input = None
        close = getattr(self.uart, "close", None)
        if callable(close):
            close()

