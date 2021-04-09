"""Driver for Senseair S8 Low Power 004-0-0053 CO2 sensor"""
from time import sleep
from typing import Optional, Dict
import serial


class ModbusCRC:
    _initial = 0xFFFF
    _table = (
        0x0000,
        0xC0C1,
        0xC181,
        0x0140,
        0xC301,
        0x03C0,
        0x0280,
        0xC241,
        0xC601,
        0x06C0,
        0x0780,
        0xC741,
        0x0500,
        0xC5C1,
        0xC481,
        0x0440,
        0xCC01,
        0x0CC0,
        0x0D80,
        0xCD41,
        0x0F00,
        0xCFC1,
        0xCE81,
        0x0E40,
        0x0A00,
        0xCAC1,
        0xCB81,
        0x0B40,
        0xC901,
        0x09C0,
        0x0880,
        0xC841,
        0xD801,
        0x18C0,
        0x1980,
        0xD941,
        0x1B00,
        0xDBC1,
        0xDA81,
        0x1A40,
        0x1E00,
        0xDEC1,
        0xDF81,
        0x1F40,
        0xDD01,
        0x1DC0,
        0x1C80,
        0xDC41,
        0x1400,
        0xD4C1,
        0xD581,
        0x1540,
        0xD701,
        0x17C0,
        0x1680,
        0xD641,
        0xD201,
        0x12C0,
        0x1380,
        0xD341,
        0x1100,
        0xD1C1,
        0xD081,
        0x1040,
        0xF001,
        0x30C0,
        0x3180,
        0xF141,
        0x3300,
        0xF3C1,
        0xF281,
        0x3240,
        0x3600,
        0xF6C1,
        0xF781,
        0x3740,
        0xF501,
        0x35C0,
        0x3480,
        0xF441,
        0x3C00,
        0xFCC1,
        0xFD81,
        0x3D40,
        0xFF01,
        0x3FC0,
        0x3E80,
        0xFE41,
        0xFA01,
        0x3AC0,
        0x3B80,
        0xFB41,
        0x3900,
        0xF9C1,
        0xF881,
        0x3840,
        0x2800,
        0xE8C1,
        0xE981,
        0x2940,
        0xEB01,
        0x2BC0,
        0x2A80,
        0xEA41,
        0xEE01,
        0x2EC0,
        0x2F80,
        0xEF41,
        0x2D00,
        0xEDC1,
        0xEC81,
        0x2C40,
        0xE401,
        0x24C0,
        0x2580,
        0xE541,
        0x2700,
        0xE7C1,
        0xE681,
        0x2640,
        0x2200,
        0xE2C1,
        0xE381,
        0x2340,
        0xE101,
        0x21C0,
        0x2080,
        0xE041,
        0xA001,
        0x60C0,
        0x6180,
        0xA141,
        0x6300,
        0xA3C1,
        0xA281,
        0x6240,
        0x6600,
        0xA6C1,
        0xA781,
        0x6740,
        0xA501,
        0x65C0,
        0x6480,
        0xA441,
        0x6C00,
        0xACC1,
        0xAD81,
        0x6D40,
        0xAF01,
        0x6FC0,
        0x6E80,
        0xAE41,
        0xAA01,
        0x6AC0,
        0x6B80,
        0xAB41,
        0x6900,
        0xA9C1,
        0xA881,
        0x6840,
        0x7800,
        0xB8C1,
        0xB981,
        0x7940,
        0xBB01,
        0x7BC0,
        0x7A80,
        0xBA41,
        0xBE01,
        0x7EC0,
        0x7F80,
        0xBF41,
        0x7D00,
        0xBDC1,
        0xBC81,
        0x7C40,
        0xB401,
        0x74C0,
        0x7580,
        0xB541,
        0x7700,
        0xB7C1,
        0xB681,
        0x7640,
        0x7200,
        0xB2C1,
        0xB381,
        0x7340,
        0xB101,
        0x71C0,
        0x7080,
        0xB041,
        0x5000,
        0x90C1,
        0x9181,
        0x5140,
        0x9301,
        0x53C0,
        0x5280,
        0x9241,
        0x9601,
        0x56C0,
        0x5780,
        0x9741,
        0x5500,
        0x95C1,
        0x9481,
        0x5440,
        0x9C01,
        0x5CC0,
        0x5D80,
        0x9D41,
        0x5F00,
        0x9FC1,
        0x9E81,
        0x5E40,
        0x5A00,
        0x9AC1,
        0x9B81,
        0x5B40,
        0x9901,
        0x59C0,
        0x5880,
        0x9841,
        0x8801,
        0x48C0,
        0x4980,
        0x8941,
        0x4B00,
        0x8BC1,
        0x8A81,
        0x4A40,
        0x4E00,
        0x8EC1,
        0x8F81,
        0x4F40,
        0x8D01,
        0x4DC0,
        0x4C80,
        0x8C41,
        0x4400,
        0x84C1,
        0x8581,
        0x4540,
        0x8701,
        0x47C0,
        0x4680,
        0x8641,
        0x8201,
        0x42C0,
        0x4380,
        0x8341,
        0x4100,
        0x81C1,
        0x8081,
        0x4040,
    )

    @staticmethod
    def calc(message: bytes) -> bytes:
        """calculate modbus CRC16 from a byte string, in little endian order as per modbus protocol.

        Args:
            message (bytes): body of a modbus message

        Returns:
            bytes: CRC16
        """
        crc = ModbusCRC._initial
        for byte in message:
            crc = (crc >> 8) ^ ModbusCRC._table[(crc ^ byte) & 0xFF]
        return crc.to_bytes(2, "little")

    @staticmethod
    def check(message: bytes) -> bool:
        """check if CRC of modbus message matches calculated CRC

        Args:
            message (bytes): modbus message

        Returns:
            bool: True if match, False if not
        """
        body = message[0:-2]
        msg_crc = message[-2:]
        calc_crc = ModbusCRC.calc(body)
        return msg_crc == calc_crc


class S8Error(Exception):
    """device reported an error. Check status register"""


def make_s8_serial_connection(device: str) -> serial.Serial:
    # must have 9600 baud and timeout >= 0.2
    return serial.Serial(port=device, baudrate=9600, timeout=1)


class SenseairS8:
    """API for SenseAir S8 Low Power 004-0-0053 CO2 sensor"""

    # Hard coded static commands. Only one (writing abc_period) is dynamic.
    # For reads, the format of the bytes is:
    # broadcast address, function code, register address high, reg addr low, N registers high, N reg low, CRC low, CRC high
    # Note the checksum is little endian.
    # For writes, the bytes are:
    # broadcast addr, func code, reg addr high, reg addr low, value high, value low, CRC low, CRC high
    _commands = {
        "co2": b"\xfe\x04\x00\x03\x00\x01\xd5\xc5",
        "type_id": b"\xfe\x04\x00\x19\x00\x02\xb4\x03",
        "fw_ver": b"\xfe\x04\x00\x1c\x00\x01\xe4\x03",
        "serial_id": b"\xfe\x04\x00\x1d\x00\x02\xf5\xc2",
        "error_code": b"\xfe\x04\x00\x00\x00\x01\x25\xc5",
        "abc_period": b"\xfe\x03\x00\x1f\x00\x01\xa1\xc3",
        "clear_ack": b"\xfe\x06\x00\x00\x00\x00\x9d\xc5",
        "read_ack": b"\xfe\x03\x00\x00\x00\x01\x90\x05",
        "force_abc": b"\xfe\x06\x00\x01\x7c\x06\x6c\xc7",
        "disable_abc": b"\xfe\x06\x00\x1f\x00\x00\xac\x03",
    }

    def __init__(self, serial_dev: serial.Serial) -> None:
        self._ser = serial_dev
        self._cached = {
            k: None for k in ["co2", "type_id", "fw_ver", "serial_id", "error_code", "abc_period"]
        }
        self._ser.flushInput()

    @property
    def values(self):
        return self._cached

    def _serial_read(self, command: bytes, n_bytes=7) -> bytes:
        self._ser.flushInput()
        self._ser.write(command)
        response = self._ser.read(n_bytes)

        if not ModbusCRC.check(response):
            raise IOError("CRC checksum mismatch")
        return response

    def _serial_write(self, message: bytes, append_crc=False) -> None:
        if append_crc:
            crc = ModbusCRC.calc(message)
            message = message + crc

        self._ser.write(message)

    def _read_register(self, cmd_name: str, n_bytes=7, integer=True):
        length = n_bytes - 5
        response = self._serial_read(SenseairS8._commands[cmd_name], n_bytes=n_bytes)
        val = response[3 : 3 + length]
        if integer:
            val = int.from_bytes(val, "big")  # type: ignore
        self._cached[cmd_name] = val  # type: ignore

    def read_co2(self) -> None:
        """Current CO2 concentration in ppm"""
        self._read_register("co2")

    def read_type_id(self) -> None:
        """Device model number"""
        self._read_register("type_id", n_bytes=9, integer=False)

    def read_serial_id(self) -> None:
        """Device serial number"""
        self._read_register("serial_id", n_bytes=9, integer=False)

    def read_firmware_version(self) -> None:
        """Operating firmware version"""
        self._read_register("fw_ver", integer=False)

    def read_error_code(self) -> None:
        """Device error code bit flags. See datasheet for interpretation"""
        self._read_register("error_code")

    def read_abc_period(self) -> None:
        """Automatic Baseline Correction period"""
        self._read_register("abc_period")

    def configure_abc(
        self, period_hours: Optional[int] = None, disable=False, recalibrate=False
    ) -> None:
        """Configure the automatic baseline correction (ABC) algorithm

        Args:
            period_hours (Optional[int], optional): set maximum time between recalibration, in hours. Device default is 192 (8 days).
            disable (bool, optional): disable ABC entirely. Defaults to False.
            recalibrate (bool, optional): force recalibration. Defaults to False.

        Raises:
            S8Error: device error during recalibration
        """
        if disable:
            cmd = self._commands["disable_abc"]
            self._serial_write(cmd)
            return

        if period_hours is not None:
            prefix = b"\xfe\x06\x00\x1f"
            value = period_hours.to_bytes(2, "big")
            self._serial_write(prefix + value, append_crc=True)
            self._cached["abc_period"] = period_hours  # type: ignore

        if recalibrate:
            # clear acknowledgement register
            self._serial_write(self._commands["clear_ack"])
            sleep(0.18)
            # start background calibration
            self._serial_write(self._commands["force_abc"])
            sleep(4.5)  # a bit more than a full measurement cycle
            # confirm; read acknowledgement register
            response = self._serial_read(self._commands["read_ack"])
            val = int.from_bytes(response[3:5], "big")
            bit_mask = 1 << 5
            if not bit_mask & val:
                raise S8Error(
                    "Recalibration failed, possibly due to unstable CO2 concentration. Try again."
                )


class MockSerial:
    def __init__(self, mock_registers: Dict[bytes, bytes]) -> None:
        self.reg = mock_registers
        self.current_reg = b""

    def name_lookup(self, cmd: bytes) -> str:
        return [key for key, msg in SenseairS8._commands.items() if msg == cmd][0]

    def flushInput(self) -> None:
        pass

    def write(self, cmd: bytes) -> None:
        reg = cmd[2:4]
        if cmd[1] != 0x06:  # reads
            self.current_reg = reg
            return
        if cmd == SenseairS8._commands["force_abc"]:
            self.reg[b"\x00\x00"] = (1 << 5).to_bytes(2, "big")
            return
        val = cmd[4:6]
        self.reg[reg] = val

    def read(self, n_bytes: int) -> bytes:
        val = self.reg[self.current_reg]
        dummy_prefix = b"\x00\x01\x02"
        body = dummy_prefix + val
        crc = ModbusCRC.calc(body)
        return body + crc
