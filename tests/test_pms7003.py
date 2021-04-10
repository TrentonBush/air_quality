import pytest
from drivers.pms7003 import PMS7003, MockSerial


@pytest.fixture
def mocked_pms7003_serial():
    values = (
        28,  # frame_length
        0,  # pm1_0
        1,  # pm2_5
        2,  # pm10_0
        3,  # pm1_0_atm
        4,  # pm2_5_atm
        5,  # pm10_0_atm
        6,  # count_0_3
        7,  # count_0_5
        8,  # count_1_0
        9,  # count_2_5
        10,  # count_5_0
        11,  # count_10_0
        12,  # version
        13,  # error
        28 + sum(range(14)) + sum(PMS7003._start_bytes),  # checksum
    )
    yield MockSerial(values)


def test_PMS7003_hardcoded_command_checksums():
    for name, cmd in PMS7003._commands.items():
        msg = f"{name} checksum failed"
        assert sum(cmd[:-2]) == int.from_bytes(cmd[-2:], "big"), msg


def test_PMS7003__parse_frame_normal_values(mocked_pms7003_serial):
    ser = mocked_pms7003_serial
    pms7003 = PMS7003(ser)
    expected = dict(zip(PMS7003._fields[:-1], ser.values[:-1]))
    actual = pms7003._parse_frame(ser.frame[2:])
    assert actual == expected


def test_PMS7003__parse_frame_bad_checksum(mocked_pms7003_serial):
    ser = mocked_pms7003_serial
    # make bad checksum
    ser.frame = ser.frame[:-2] + b"\xFF\xFF"
    pms7003 = PMS7003(ser)
    with pytest.raises(IOError):
        pms7003._parse_frame(ser.frame[2:])


def test_PMS7003_read(mocked_pms7003_serial):
    ser = mocked_pms7003_serial
    pms7003 = PMS7003(ser)
    expected = dict(zip(PMS7003._fields[:-1], ser.values[:-1]))
    pms7003.read()
    actual = pms7003.values
    assert actual == expected


def test_PMS7003_listen(mocked_pms7003_serial):
    ser = mocked_pms7003_serial
    pms7003 = PMS7003(ser)
    expected = dict(zip(PMS7003._fields[:-1], ser.values[:-1]))
    pms7003.set_device_sync()
    pms7003.listen()
    actual = pms7003.values
    assert actual == expected
