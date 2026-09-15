# CircuitPython-compatible u-blox 6 / NEO-6M driver
import struct
import time

# Protocol selection
PROTOCOL_NONE = 0x00
PROTOCOL_UBX = 0x01
PROTOCOL_NMEA = 0x02
PROTOCOL_RTCM = 0x04

# Common NEO-6M navigation update rates
RATE_1HZ = 1
RATE_2HZ = 2
RATE_4HZ = 4
RATE_5HZ = 5

# NMEA messages configurable through UBX-CFG-MSG
NMEA_MESSAGE_IDS = {
    "GGA": (0xF0, 0x00),
    "GLL": (0xF0, 0x01),
    "GSA": (0xF0, 0x02),
    "GSV": (0xF0, 0x03),
    "RMC": (0xF0, 0x04),
    "VTG": (0xF0, 0x05),
}

UBX_MESSAGE_NAMES = {
    (0x05, 0x00): "ACK_NAK",
    (0x05, 0x01): "ACK_ACK",

    (0x01, 0x02): "NAV_POSLLH",
    (0x01, 0x03): "NAV_STATUS",
    (0x01, 0x06): "NAV_SOL",
    (0x01, 0x12): "NAV_VELNED",
    (0x01, 0x21): "NAV_TIMEUTC",
}

NMEA_ENABLE_ALL = ("GGA", "GLL", "GSA", "GSV", "RMC", "VTG")


def _u16(value):
    return struct.pack("<H", int(value))


def _u32(value):
    return struct.pack("<I", int(value))


def _i32_from(data, offset):
    return struct.unpack_from("<i", data, offset)[0]


def _u16_from(data, offset):
    return struct.unpack_from("<H", data, offset)[0]


def _u32_from(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def _nmea_checksum(body):
    chk = 0
    for c in body:
        chk ^= c
    return chk


def _ubx_checksum(data):
    ck_a = 0
    ck_b = 0
    for b in data:
        ck_a = (ck_a + b) & 0xFF
        ck_b = (ck_b + ck_a) & 0xFF
    return ck_a, ck_b


def _dm_to_deg(value, hemisphere):
    if not value:
        return None
    v = float(value)
    deg = int(v // 100)
    minutes = v - deg * 100
    result = deg + minutes / 60.0
    if hemisphere in ("S", "W"):
        result = -result
    return result


def _to_float(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _to_int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return None



class UpdateStatus:
    def __init__(self):
        self._nmea = False
        self._ubx = False

    @property
    def has_nmea(self):
        return self._nmea

    @property
    def has_ubx(self):
        return self._ubx

    def _set_nmea(self):
        self._nmea = True

    def _set_ubx(self):
        self._ubx = True

    def __bool__(self):
        return self._nmea or self._ubx

    def __eq__(self, other):
        if isinstance(other, bool):
            return bool(self) == other
        return NotImplemented

class UBlox6:
    """CircuitPython-compatible driver for u-blox 6 receivers such as NEO-6M."""

    def __init__(self, uart, debug=False):
        self.uart = uart
        self.debug = debug

        # Adafruit-like high-level navigation attributes
        self.latitude = None
        self.longitude = None
        self.altitude_m = None
        self.height_geoid = None
        self.speed_knots = None
        self.track_angle_deg = None
        self.horizontal_dilution = None
        self.vertical_dilution = None
        self.pdop = None
        self.satellites = None
        self.fix_quality = 0
        self.fix_type = 0
        self.timestamp = None
        self.nmea_sentence = None

        # Optional UBX-derived accuracy/status values
        self.horizontal_accuracy_m = None
        self.vertical_accuracy_m = None
        self.speed_accuracy_mps = None
        self.heading_accuracy_deg = None

        # Local parsing selection. This does not configure the receiver.
        self._parse_messages = set(NMEA_ENABLE_ALL)

        # Cached high-level configuration
        self._protocol = PROTOCOL_NMEA | PROTOCOL_UBX
        self._update_rate_hz = None
        self._baudrate = getattr(uart, "baudrate", None)

        # Stream parser
        self._mode = 0
        self._nmea_buf = bytearray()
        self._ubx_buf = bytearray()
        self._ubx_expected = 0
        self._prev_b5 = False

        # Status
        self._current_status = UpdateStatus()

        # reset serial buffer
        self.uart.reset_input_buffer()

    @property
    def has_fix(self):
        return self.fix_quality > 0 or self.fix_type >= 2

    @property
    def has_3d_fix(self):
        return self.fix_type >= 3

    @property
    def datetime(self):
        return self.timestamp

    @property
    def in_waiting(self):
        return getattr(self.uart, "in_waiting", 0)

    def read(self, num_bytes):
        return self.uart.read(num_bytes)

    def readline(self):
        return self.uart.readline()

    def write(self, data):
        return self.uart.write(data)

    def send_command(self, command, add_checksum=True):
        """Adafruit-style ASCII/NMEA command sender."""
        if isinstance(command, str):
            command = command.encode("ascii")
        command = command.strip()
        if command.startswith(b"$"):
            command = command[1:]
        if b"*" in command:
            command = command.split(b"*", 1)[0]

        if add_checksum:
            chk = _nmea_checksum(command)
            packet = b"$" + command + b"*%02X\r\n" % chk
        else:
            packet = b"$" + command + b"\r\n"
        return self.write(packet)

    def send_ubx(self, msg_class, msg_id, payload=b""):
        """Build and send a UBX binary packet."""
        if payload is None:
            payload = b""
        header = bytes((msg_class, msg_id)) + _u16(len(payload))
        ck_a, ck_b = _ubx_checksum(header + payload)
        packet = b"\xB5\x62" + header + payload + bytes((ck_a, ck_b))
        return self.write(packet)

    def poll_ubx(self, msg_class, msg_id, payload=b""):
        return self.send_ubx(msg_class, msg_id, payload)

    @property
    def nmea_output(self):
        """NMEA messages enabled for transmission by the receiver."""
        return tuple(sorted(self._nmea_output))


    @nmea_output.setter
    def nmea_output(self, messages):
        if isinstance(messages, str):
            messages = (messages,)

        selected = {str(m).upper() for m in messages}

        for name in selected:
            if name not in NMEA_MESSAGE_IDS:
                raise ValueError("Unsupported NMEA message: " + name)

        for name, ids in NMEA_MESSAGE_IDS.items():
            msg_rate = 1 if name in selected else 0

            payload = bytes((
                ids[0],   # msgClass
                ids[1],   # msgID
                msg_rate
            ))

            self.send_ubx(0x06, 0x01, payload)  # CFG-MSG
            time.sleep(0.03)

        self._nmea_output = selected

    def set_nmea_output(self, messages, rate=1):
        """Configure which NMEA messages are transmitted by the receiver."""

        if isinstance(messages, str):
            messages = (messages,)

        selected = {str(m).upper() for m in messages}

        for name in selected:
            if name not in NMEA_MESSAGE_IDS:
                raise ValueError("Unsupported NMEA message: " + name)

        for name, ids in NMEA_MESSAGE_IDS.items():

            if name in selected:
                msg_rate = rate
            else:
                msg_rate = 0

            payload = bytes((
                ids[0],      # msgClass
                ids[1],      # msgID
                msg_rate     # rate
            ))

            self.send_ubx(
                0x06,        # CFG
                0x01,        # MSG
                payload
            )

            time.sleep(0.03)

    @property
    def protocol(self):
        return self._protocol

    @protocol.setter
    def protocol(self, value):
        """Set UART1 input/output protocol mask: UBX, NMEA or both."""
        if value not in (PROTOCOL_UBX, PROTOCOL_NMEA, PROTOCOL_RTCM, PROTOCOL_UBX | PROTOCOL_NMEA, PROTOCOL_UBX | PROTOCOL_RTCM, PROTOCOL_NMEA | PROTOCOL_RTCM, PROTOCOL_UBX | PROTOCOL_NMEA | PROTOCOL_RTCM):
            raise ValueError("protocol must be PROTOCOL_UBX, PROTOCOL_NMEA or PROTOCOL_BOTH")
        self._set_uart1(port_protocol=value, new_baudrate=None)
        self._protocol = value

    @property
    def datarate(self):
        return self._update_rate_hz

    @datarate.setter
    def datarate(self, hz):
        """Set navigation/measurement rate using UBX-CFG-RATE."""
        if hz not in (RATE_1HZ, RATE_2HZ, RATE_4HZ, RATE_5HZ):
            raise ValueError("NEO-6M high-level rates: 1, 2, 4 or 5 Hz")
        meas_ms = int(1000 // hz)
        self.set_measurement_rate_ms(meas_ms)
        self._update_rate_hz = hz

    def set_measurement_rate_ms(self, milliseconds, time_reference=1):
        """Lower-level CFG-RATE access.

        navRate is fixed to 1 on u-blox 6.
        time_reference: 0=UTC, 1=GPS.
        """

        milliseconds = int(milliseconds)

        if milliseconds < 1 or milliseconds > 65535:
            raise ValueError("milliseconds must fit U2")

        if time_reference not in (0, 1):
            raise ValueError("time_reference must be 0 (UTC) or 1 (GPS)")

        payload = (
            _u16(milliseconds)
            + _u16(1)
            + _u16(time_reference)
        )

        self.send_ubx(0x06, 0x08, payload)

    @property
    def baudrate(self):
        return self._baudrate

    @baudrate.setter
    def baudrate(self, value):
        """Change UART1 baudrate in the receiver and, when possible, the host UART."""
        value = int(value)
        self._set_uart1(port_protocol=None, new_baudrate=value)
        time.sleep(0.05)

        try:
            self.uart.baudrate = value
        except (AttributeError, NotImplementedError):
            # Some UART implementations require reconstructing busio.UART.
            pass

        self._baudrate = value

    def _set_uart1(self, port_protocol=None, new_baudrate=None):
        """UBX-CFG-PRT for UART1, using 8N1."""
        baud = new_baudrate
        if baud is None:
            baud = self._baudrate if self._baudrate is not None else 9600

        proto = port_protocol
        if proto is None:
            proto = self._protocol

        port_id = 1
        reserved0 = 0
        tx_ready = 0
        mode_8n1 = 0x000008D0
        in_proto = proto
        out_proto = proto

        payload = (
            bytes((port_id, reserved0))
            + _u16(tx_ready)
            + _u32(mode_8n1)
            + _u32(baud)
            + _u16(in_proto)
            + _u16(out_proto)
            + _u16(0)
            + _u16(0)
        )
        self.send_ubx(0x06, 0x00, payload)

    def store(self):
        """Save current configuration using UBX-CFG-CFG."""
        # saveMask: ioPort + msgConf + infMsg + navConf + rxmConf
        save_mask = 0x00001F1F
        payload = _u32(0) + _u32(save_mask) + _u32(0)
        self.send_ubx(0x06, 0x09, payload)

    def restore(self):
        """Clear configuration sections and load defaults."""
        clear_mask = 0x0000FFFF
        load_mask = 0x0000FFFF
        payload = _u32(clear_mask) + _u32(0) + _u32(load_mask)
        self.send_ubx(0x06, 0x09, payload)

    def update(self):
        """Read available bytes and parse mixed NMEA + UBX traffic."""
        status = UpdateStatus()
        self._current_status = status

        available = self.in_waiting
        if available:
            data = self.uart.read(available)
        else:
            data = self.uart.read(1)

        if not data:
            return status

        for b in data:
            self._feed_byte(b)

        return status

    def _feed_byte(self, b):
        # mode 0: seek packet start
        if self._mode == 0:
            if b == 0x24:  # '$'
                self._nmea_buf = bytearray((b,))
                self._mode = 1
                self._prev_b5 = False
            elif self._prev_b5 and b == 0x62:
                self._ubx_buf = bytearray(b"\xB5\x62")
                self._mode = 2
                self._ubx_expected = 0
                self._prev_b5 = False
            else:
                self._prev_b5 = (b == 0xB5)
            return False

        # mode 1: NMEA
        if self._mode == 1:
            self._nmea_buf.append(b)
            if b == 0x0A:
                sentence = bytes(self._nmea_buf)
                self._mode = 0
                self._nmea_buf = bytearray()
                return self._parse_nmea(sentence)

            if len(self._nmea_buf) > 128:
                self._mode = 0
                self._nmea_buf = bytearray()
            return False

        # mode 2: UBX
        self._ubx_buf.append(b)

        if len(self._ubx_buf) == 6:
            payload_len = self._ubx_buf[4] | (self._ubx_buf[5] << 8)
            self._ubx_expected = 6 + payload_len + 2

        if self._ubx_expected and len(self._ubx_buf) >= self._ubx_expected:
            packet = bytes(self._ubx_buf)
            self._mode = 0
            self._ubx_buf = bytearray()
            self._ubx_expected = 0
            return self._parse_ubx(packet)

        if len(self._ubx_buf) > 1024:
            self._mode = 0
            self._ubx_buf = bytearray()
            self._ubx_expected = 0

        return False

    def _parse_nmea(self, raw):
        try:
            text = raw.decode("ascii").strip()
        except UnicodeError:
            return False

        if not text.startswith("$") or "*" not in text:
            return False

        body, supplied = text[1:].split("*", 1)
        try:
            expected = int(supplied[:2], 16)
        except ValueError:
            return False

        if _nmea_checksum(body.encode("ascii")) != expected:
            return False

        self.nmea_sentence = text
        fields = body.split(",")
        sentence = fields[0][-3:]

        if sentence not in self._parse_messages:
            return False

        if self.debug:
            print(text)

        parser = getattr(self, "_parse_" + sentence.lower(), None)
        if parser is None:
            return False

        parser(fields)
        self._current_status._set_nmea()
        return True

    def _parse_gga(self, f):
        if len(f) < 15:
            return
        self._set_time(f[1])
        self.latitude = _dm_to_deg(f[2], f[3])
        self.longitude = _dm_to_deg(f[4], f[5])
        self.fix_quality = _to_int(f[6]) or 0
        self.satellites = _to_int(f[7])
        self.horizontal_dilution = _to_float(f[8])
        self.altitude_m = _to_float(f[9])
        self.height_geoid = _to_float(f[11])

    def _parse_gll(self, f):
        if len(f) < 7:
            return
        self.latitude = _dm_to_deg(f[1], f[2])
        self.longitude = _dm_to_deg(f[3], f[4])
        self._set_time(f[5])

    def _parse_gsa(self, f):
        if len(f) < 18:
            return
        self.fix_type = _to_int(f[2]) or 0
        self.pdop = _to_float(f[15])
        self.horizontal_dilution = _to_float(f[16])
        self.vertical_dilution = _to_float(f[17])

    def _parse_gsv(self, f):
        # GSV reports satellites in view; do not overwrite "satellites used"
        # from GGA. Keep it available separately.
        if len(f) >= 4:
            self.satellites_in_view = _to_int(f[3])

    def _parse_rmc(self, f):
        if len(f) < 10:
            return
        self._set_time(f[1], f[9])
        self.latitude = _dm_to_deg(f[3], f[4])
        self.longitude = _dm_to_deg(f[5], f[6])
        self.speed_knots = _to_float(f[7])
        self.track_angle_deg = _to_float(f[8])

        if f[2] == "A" and self.fix_quality == 0:
            self.fix_quality = 1
        elif f[2] == "V":
            self.fix_quality = 0

    def _parse_vtg(self, f):
        if len(f) < 8:
            return
        self.track_angle_deg = _to_float(f[1])
        self.speed_knots = _to_float(f[5])

    def _set_time(self, time_field, date_field=None):
        if not time_field or len(time_field) < 6:
            return
        try:
            hour = int(time_field[0:2])
            minute = int(time_field[2:4])
            second = int(float(time_field[4:]))
        except ValueError:
            return

        year = month = day = 0
        if date_field and len(date_field) >= 6:
            try:
                day = int(date_field[0:2])
                month = int(date_field[2:4])
                yy = int(date_field[4:6])
                year = 2000 + yy if yy < 80 else 1900 + yy
            except ValueError:
                year = month = day = 0

        self.timestamp = time.struct_time(
            (year, month, day, hour, minute, second, -1, -1, -1)
        )

    def _parse_ubx(self, packet):
        if len(packet) < 8 or packet[0:2] != b"\xB5\x62":
            return False

        msg_class = packet[2]
        msg_id = packet[3]
        length = packet[4] | (packet[5] << 8)
        payload = packet[6:6 + length]

        ck_a, ck_b = _ubx_checksum(packet[2:6 + length])
        if packet[-2] != ck_a or packet[-1] != ck_b:
            return False

        self._current_status._set_ubx()

        # ACK-ACK / ACK-NAK
        if msg_class == 0x05 and len(payload) >= 2:
            self.last_ack = (msg_id == 0x01, payload[0], payload[1])
            return True

        # NAV-POSLLH: geodetic position
        if msg_class == 0x01 and msg_id == 0x02 and len(payload) >= 28:
            self.longitude = _i32_from(payload, 4) * 1e-7
            self.latitude = _i32_from(payload, 8) * 1e-7
            self.altitude_m = _i32_from(payload, 16) / 1000.0
            self.horizontal_accuracy_m = _u32_from(payload, 20) / 1000.0
            self.vertical_accuracy_m = _u32_from(payload, 24) / 1000.0
            return True

        # NAV-STATUS
        if msg_class == 0x01 and msg_id == 0x03 and len(payload) >= 16:
            self.fix_type = payload[4]
            flags = payload[5]
            if not (flags & 0x01):
                self.fix_quality = 0
            elif self.fix_quality == 0:
                self.fix_quality = 1
            return True

        # NAV-VELNED
        if msg_class == 0x01 and msg_id == 0x12 and len(payload) >= 36:
            speed_cms = _u32_from(payload, 20)
            heading_1e5 = _i32_from(payload, 24)
            sacc_cms = _u32_from(payload, 28)
            cacc_1e5 = _u32_from(payload, 32)
            self.speed_knots = (speed_cms / 100.0) * 1.943844492
            self.track_angle_deg = heading_1e5 * 1e-5
            self.speed_accuracy_mps = sacc_cms / 100.0
            self.heading_accuracy_deg = cacc_1e5 * 1e-5
            return True

        # NAV-SOL: number of satellites used and fix information
        if msg_class == 0x01 and msg_id == 0x06 and len(payload) >= 52:
            self.fix_type = payload[10]
            self.satellites = payload[47]
            return True

        # NAV-TIMEUTC
        if msg_class == 0x01 and msg_id == 0x21 and len(payload) >= 20:
            year = _u16_from(payload, 12)
            month = payload[14]
            day = payload[15]
            hour = payload[16]
            minute = payload[17]
            second = payload[18]
            self.timestamp = time.struct_time(
                (year, month, day, hour, minute, second, -1, -1, -1)
            )
            return True

        return True
