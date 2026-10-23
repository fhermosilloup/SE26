
"""
Python interface for MFRC522 RFID readers on Raspberry Pi.
Uses spidev for SPI and gpiozero for the reset pin.
"""

import time
import spidev
from gpiozero import OutputDevice


class MFRC522:
    """Interface for RC522 boards on Raspberry Pi.

    Args:
        bus: SPI bus number (usually 0).
        device: SPI chip-select device (0 = CE0, 1 = CE1).
        rst: BCM GPIO number connected to the RC522 RST pin.
        max_speed_hz: SPI clock frequency.
    """

    OK = 0
    NOTAGERR = 1
    ERR = 2

    REQIDL = 0x26
    REQALL = 0x52
    AUTHENT1A = 0x60
    AUTHENT1B = 0x61

    def __init__(
        self,
        bus=0,
        device=0,
        rst=25,
        max_speed_hz=1_000_000,
    ):
        self.spi = spidev.SpiDev()
        self.spi.open(bus, device)
        self.spi.max_speed_hz = max_speed_hz
        self.spi.mode = 0
        self.spi.bits_per_word = 8
        self.spi.no_cs = False

        # RST uses BCM numbering. CS is controlled by spidev.
        self.rst = OutputDevice(
            rst, active_high=True, initial_value=False
        )
        time.sleep(0.01)
        self.rst.on()
        time.sleep(0.05)

        self.init()

    def close(self):
        """Release SPI and GPIO resources."""
        self.spi.close()
        self.rst.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def _wreg(self, reg: int, val: int):
        address = ((reg << 1) & 0x7E)
        self.spi.xfer2([address, val & 0xFF])

    def _rreg(self, reg: int):
        address = (((reg << 1) & 0x7E) | 0x80)
        result = self.spi.xfer2([address, 0x00])
        return result[1]

    def _sflags(self, reg: int, mask: int):
        self._wreg(reg, self._rreg(reg) | mask)

    def _cflags(self, reg: int, mask: int):
        self._wreg(reg, self._rreg(reg) & (~mask & 0xFF))

    def _tocard(self, cmd: int, send):
        recv = []
        bits = 0
        irq_en = 0
        wait_irq = 0
        stat = self.ERR

        if cmd == 0x0E:
            irq_en = 0x12
            wait_irq = 0x10
        elif cmd == 0x0C:
            irq_en = 0x77
            wait_irq = 0x30

        self._wreg(0x02, irq_en | 0x80)
        self._cflags(0x04, 0x80)
        self._sflags(0x0A, 0x80)
        self._wreg(0x01, 0x00)

        for c in send:
            self._wreg(0x09, c)

        self._wreg(0x01, cmd)

        if cmd == 0x0C:
            self._sflags(0x0D, 0x80)

        i = 2000
        while True:
            n = self._rreg(0x04)
            i -= 1
            if not (
                (i != 0)
                and not (n & 0x01)
                and not (n & wait_irq)
            ):
                break

        self._cflags(0x0D, 0x80)

        if i:
            if (self._rreg(0x06) & 0x1B) == 0x00:
                stat = self.OK

                if n & irq_en & 0x01:
                    stat = self.NOTAGERR
                elif cmd == 0x0C:
                    n = self._rreg(0x0A)
                    lbits = self._rreg(0x0C) & 0x07

                    if lbits:
                        bits = (n - 1) * 8 + lbits
                    else:
                        bits = n * 8

                    if n == 0:
                        n = 1
                    elif n > 16:
                        n = 16

                    for _ in range(n):
                        recv.append(self._rreg(0x09))
            else:
                stat = self.ERR

        return stat, recv, bits

    def _crc(self, data):
        self._cflags(0x05, 0x04)
        self._sflags(0x0A, 0x80)

        for c in data:
            self._wreg(0x09, c)

        self._wreg(0x01, 0x03)

        i = 0xFF
        while True:
            n = self._rreg(0x05)
            i -= 1
            if not ((i != 0) and not (n & 0x04)):
                break

        return [self._rreg(0x22), self._rreg(0x21)]

    def init(self):
        self.reset()
        self._wreg(0x2A, 0x8D)
        self._wreg(0x2B, 0x3E)
        self._wreg(0x2D, 30)
        self._wreg(0x2C, 0)
        self._wreg(0x15, 0x40)
        self._wreg(0x11, 0x3D)
        self.antenna_on()

    def reset(self):
        self._wreg(0x01, 0x0F)

    def antenna_on(self, on=True):
        if on:
            if not (self._rreg(0x14) & 0x03):
                self._sflags(0x14, 0x03)
        else:
            self._cflags(0x14, 0x03)

    def request(self, mode):
        self._wreg(0x0D, 0x07)
        stat, recv, bits = self._tocard(0x0C, [mode])

        if stat != self.OK or bits != 0x10:
            stat = self.ERR

        return stat, bits

    def anticoll(self):
        ser_chk = 0
        ser = [0x93, 0x20]

        self._wreg(0x0D, 0x00)
        stat, recv, bits = self._tocard(0x0C, ser)

        if stat == self.OK:
            if len(recv) == 5:
                for i in range(4):
                    ser_chk ^= recv[i]
                if ser_chk != recv[4]:
                    stat = self.ERR
            else:
                stat = self.ERR

        return stat, recv

    def select_tag(self, ser):
        buf = [0x93, 0x70] + ser[:5]
        buf += self._crc(buf)
        stat, recv, bits = self._tocard(0x0C, buf)

        return (
            self.OK
            if stat == self.OK and bits == 0x18
            else self.ERR
        )

    def auth(self, mode, addr, sect, ser):
        return self._tocard(
            0x0E, [mode, addr] + sect + ser[:4]
        )[0]

    def stop_crypto1(self):
        self._cflags(0x08, 0x08)

    def read(self, addr):
        data = [0x30, addr]
        data += self._crc(data)
        stat, recv, _ = self._tocard(0x0C, data)

        return recv if stat == self.OK else None

    def write(self, addr, data):
        if len(data) < 16:
            raise ValueError("data debe contener al menos 16 bytes")

        buf = [0xA0, addr]
        buf += self._crc(buf)
        stat, recv, bits = self._tocard(0x0C, buf)

        if (
            stat != self.OK
            or bits != 4
            or not recv
            or (recv[0] & 0x0F) != 0x0A
        ):
            return self.ERR

        buf = list(data[:16])
        buf += self._crc(buf)
        stat, recv, bits = self._tocard(0x0C, buf)

        if (
            stat != self.OK
            or bits != 4
            or not recv
            or (recv[0] & 0x0F) != 0x0A
        ):
            return self.ERR

        return self.OK

    def set_antenna_gain(self, gain: int):
        self._cflags(0x26, 0x07 << 4)
        self._sflags(0x26, gain & (0x07 << 4))
