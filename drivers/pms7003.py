"""Driver for Plantower PMS7003 particulate matter sensor"""
import struct
from typing import Optional, Dict, Tuple
from serial import Serial


def make_pms7003_serial_connection(device: str) -> Serial:
    # must have 9600 baud and timeout >= 2.3, per datasheet
    return Serial(port=device, baudrate=9600, timeout=3)


class PMS7003:
    """API for Plantower PMS7003 particulate matter sensor"""

    _start_bytes = b"\x42\x4d"
    _fields = (  # doesn't include the two start bytes
        "frame_length",
        # PM concentrations for "factory conditions", whatever that means
        "pm1_0",
        "pm2_5",
        "pm10_0",
        # PM concentrations for "atmospheric conditions", whatever that means
        "pm1_0_atm",
        "pm2_5_atm",
        "pm10_0_atm",
        # particle counts
        "count_0_3",
        "count_0_5",
        "count_1_0",
        "count_2_5",
        "count_5_0",
        "count_10_0",
        "version",
        "error",
        "checksum",
    )

    _commands = {
        "set_host_sync": b"\x42\x4d\xe1\x00\x00\x01\x70",  # "passive" mode
        "set_device_sync": b"\x42\x4d\xe1\x00\x01\x01\x71",  # "active" mode, dynamic sample period of 0.2 to 2.3 seconds
        "sleep": b"\x42\x4d\xe4\x00\x00\x01\x73",  # standby, fan off
        "wake": b"\x42\x4d\xe4\x00\x01\x01\x74",  # wake into passive mode
        "take_measurement": b"\x42\x4d\xe2\x00\x00\x01\x71",  # for passive mode measurements
    }

    _modes = {"active": 0, "passive": 1, "sleep": 2, "unknown": None}

    def __init__(self, serial_dev: Serial) -> None:
        self._ser = serial_dev
        self._cached = {k: 0 for k in PMS7003._fields[:-1]}
        self.mode: Optional[int] = None
        self._ser.flushInput()
        self.wake()
        self.set_host_sync()

    @property
    def values(self):
        return self._cached

    @property
    def data_values(self):
        return {key: self._cached[key] for key in PMS7003._fields[1:-3]}

    def _parse_frame(self, frame: bytes) -> Dict[str, int]:
        if len(frame) != 30:
            raise ValueError(f"Expected 30 byte frame, got {len(frame)} bytes")
        # checksum is byte-wise sum of message body
        checksum = sum(frame[:-2]) + sum(PMS7003._start_bytes)
        parsed = struct.unpack(">HHHHHHHHHHHHHBBH", frame)  # doesn't include start bytes
        if checksum != parsed[-1]:
            raise IOError(f"Checksum mismatch. Received {parsed[-1]}, calculated {checksum}")
        return dict(zip(PMS7003._fields[:-1], parsed[:-1]))

    def read(self) -> None:
        if self.mode != PMS7003._modes["passive"]:
            current = [k for k, v in PMS7003._modes.items() if v == self.mode][0]
            raise ValueError(
                f"Device must be in passive mode (host-based synchronization). Currently in {current} mode"
            )
        self._ser.flushInput()
        self._ser.write(PMS7003._commands["take_measurement"])
        frame = self._ser.read(32)
        parsed = self._parse_frame(frame[2:])
        self._cached.update(parsed)

    def listen(self) -> None:
        if self.mode != PMS7003._modes["active"]:
            current = [k for k, v in PMS7003._modes.items() if v == self.mode][0]
            raise ValueError(
                f"Device must be in active mode (device-based synchronization). Currently in {current} mode"
            )

        while True:
            self._ser.read_until(PMS7003._start_bytes)
            frame = self._ser.read(30)
            if len(frame) < 30:
                continue
            parsed = self._parse_frame(frame)
            self._cached.update(parsed)
            break

    def sleep(self) -> None:
        """stop measuring and turn fan off"""
        self._ser.write(PMS7003._commands["sleep"])
        self.mode = PMS7003._modes["sleep"]

    def wake(self) -> None:
        """wake into passive mode"""
        self._ser.write(PMS7003._commands["wake"])
        self.mode = PMS7003._modes["passive"]

    def set_host_sync(self) -> None:
        """passive mode"""
        self._ser.write(PMS7003._commands["set_host_sync"])
        self.mode = PMS7003._modes["passive"]

    def set_device_sync(self) -> None:
        """active mode"""
        self._ser.write(PMS7003._commands["set_device_sync"])
        self.mode = PMS7003._modes["active"]


class MockSerial:
    def __init__(
        self, values: Tuple[int, ...]
    ) -> None:  # should be length 30, but didn't want to write that out...
        self.values = values
        self.frame = PMS7003._start_bytes + struct.pack(">HHHHHHHHHHHHHBBH", *values)
        self.byte_idx = 0

    def flushInput(self) -> None:
        pass

    def write(self, cmd: bytes) -> None:
        pass

    def read(self, n_bytes: int) -> bytes:
        ret = self.frame[self.byte_idx : self.byte_idx + n_bytes]
        self.byte_idx += n_bytes
        self.byte_idx %= 32
        return ret
