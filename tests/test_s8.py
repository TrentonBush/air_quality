import pytest
from drivers.s8 import ModbusCRC, SenseairS8, S8Error, MockSerial


def test_ModbusCRC_calc_known_value():
    msg = b"\xfe\x04\x00\x03\x00\x01\xd5\xc5"  # read co2 command, from datasheet
    body = msg[:-2]
    expected = msg[-2:]
    actual = ModbusCRC.calc(body)
    assert actual == expected
    assert ModbusCRC.check(msg)


def test_SenseairS8_hardcoded_checksums():
    mock = MockSerial()
    s8 = SenseairS8(mock)
    for name, cmd in s8._commands.items():
        assert ModbusCRC.check(cmd), f"{name} checksum failed"
