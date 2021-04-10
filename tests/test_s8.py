import pytest
from drivers.s8 import ModbusCRC, SenseairS8, MockSerial


def test_ModbusCRC_calc_known_value():
    msg = b"\xfe\x04\x00\x03\x00\x01\xd5\xc5"  # read co2 command, from datasheet
    body = msg[:-2]
    expected = msg[-2:]
    actual = ModbusCRC.calc(body)
    assert actual == expected
    assert ModbusCRC.check(msg)


@pytest.fixture
def mocked_s8():
    """In this minimal implementation, I did not differentiate between input registers and holding registers.
    This creates an address collision between error_code and clear_ack/read_ack.
    So you must pay attention to the order of reads/writes on this register.
    The recalibration sequence will effect error_code."""
    registers = {
        b"\x00\x03": (500).to_bytes(2, "big"),  # co2 = 500
        b"\x00\x19": b"\x00\x01\x02\x03",  # type_id = 0x00010203
        b"\x00\x1d": b"\xff\x01\x02\x03",  # serial_id = 0xFF010203
        b"\x00\x1c": b"\x00\x01",  # fw_ver = 0x0001
        b"\x00\x1f": (12).to_bytes(2, "big"),  # abc_period = 12
        b"\x00\x00": (1 << 6).to_bytes(2, "big"),  # read_ack = 0x0040 AND error_code = 64
    }
    yield MockSerial(registers)


def test_SenseairS8_hardcoded_checksums(mocked_s8):
    mock = mocked_s8
    s8 = SenseairS8(mock)
    for name, cmd in s8._commands.items():
        assert ModbusCRC.check(cmd), f"{name} checksum failed"


def test_SenseairS8_reads(mocked_s8):
    mock = mocked_s8
    s8 = SenseairS8(mock)

    s8.read_abc_period()
    assert s8.values["abc_period"] == 12

    s8.read_co2()
    assert s8.values["co2"] == 500

    s8.read_error_code()
    assert s8.values["error_code"] == 64

    s8.read_firmware_version()
    assert s8.values["fw_ver"] == b"\x00\x01"

    s8.read_serial_id()
    assert s8.values["serial_id"] == b"\xff\x01\x02\x03"

    s8.read_type_id()
    assert s8.values["type_id"] == b"\x00\x01\x02\x03"


def test_SenseairS8_configure_abc__set_period(mocked_s8):
    mock = mocked_s8
    s8 = SenseairS8(mock)

    s8.configure_abc(period_hours=5)
    assert mock.reg[b"\x00\x1f"] == (5).to_bytes(2, "big")


def test_SenseairS8_configure_abc__disable_abc(mocked_s8):
    mock = mocked_s8
    s8 = SenseairS8(mock)

    s8.configure_abc(disable=True)
    assert mock.reg[b"\x00\x1f"] == (0).to_bytes(2, "big")


def test_SenseairS8_configure_abc__force_recalibrate(mocked_s8):
    mock = mocked_s8
    s8 = SenseairS8(mock)

    s8.configure_abc(recalibrate=True)
    assert mock.reg[b"\x00\x00"] == (1 << 5).to_bytes(2, "big")
