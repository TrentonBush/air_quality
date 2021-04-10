import pytest
from drivers.ccs811 import CCS811, HumidityFixedPoint, TemperatureFixedPoint
from drivers.i2c_base import MockSMBus, Field


@pytest.fixture(scope="class")
def mocked_CCS811():
    # calibration and data values are same as in test__apply_calibration
    # converted with:
    # (expected_value).to_bytes(3, 'big').hex()
    registers = {
        # temperature: -40 °C, humidity: 0 %RH.
        # Concatenated to simulate burst read for .data register
        # status: app_on=True, app_erase=False, app_verify=True, app_valid=True, data_ready=True, error=False
        0x00: [0b10111000],
        # meas_mode: sample_period=1, enable_interrupt=True, interrupt_on_thresh=True
        0x01: [0b00011100],
        0x02: [0x00, 0x80, 0x01, 0x00],  # data: eCO2=128, TVOC=256
        0x03: [0x82, 0x00],  # raw_data: current_uA=32, voltage=0.825
        0x05: [0x00, 0x00, 0x00, 0x00],  # env_data: humidity=0.0, temperature=-25.0
        0x11: [0x00, 0xFF],  # baseline=255
        0x20: [0x81],  # chip_id
        # error_id: invalid_write=True, invalid_read=False, invalid_mode=True,
        # max_resistance=False, heater_fault=True, heater_supply=False
        0xE0: [0b10101000],
        0xF4: None,  # placeholder for boot command
        0xFF: [0x00, 0x00, 0x00, 0x00],  # reset: write only
    }
    smb = MockSMBus(registers)
    yield CCS811(smb, address_pin_level=0)


def test_TemperatureFixedPoint_decode__x_and_y_intercepts():
    enc = TemperatureFixedPoint()
    dummyfield = Field("asdf", byte_index=(0, 1))
    # y intercept
    expected = -25.0
    actual = enc.decode(b"\x00\x00", dummyfield)
    assert actual == expected  # shouldnt be any roundoff error

    # x intercept
    expected = 0.0
    byte_val = (25 * 512).to_bytes(2, "big")
    actual = enc.decode(byte_val, dummyfield)
    tol = 1.0 / 512.0  # resolution of transfer function
    assert actual == pytest.approx(expected, abs=tol)


def test_TemperatureFixedPoint_encode__x_and_y_intercepts():
    enc = TemperatureFixedPoint()
    dummyfield = Field("asdf", byte_index=(0, 1))
    # y intercept
    expected = b"\x00\x00"
    actual = enc.encode(-25.0, dummyfield)
    assert actual == expected

    # x intercept
    expected = (25 * 512).to_bytes(2, "big")
    actual = enc.encode(0.0, dummyfield)
    assert actual == expected


def test_HumidityFixedPoint_decode__x_and_y_intercepts():
    enc = HumidityFixedPoint()
    dummyfield = Field("asdf", byte_index=(0, 1))
    # y intercept == x intercept == 0
    expected = 0.0
    actual = enc.decode(b"\x00\x00", dummyfield)
    assert actual == expected  # shouldnt be any roundoff error

    # also test 100.00
    expected = 100.0
    byte_val = (100 * 512).to_bytes(2, "big")
    actual = enc.decode(byte_val, dummyfield)
    tol = 1.0 / 512.0  # resolution of transfer function
    assert actual == pytest.approx(expected, abs=tol)


def test_HumidityFixedPoint_encode__x_and_y_intercepts():
    enc = HumidityFixedPoint()
    dummyfield = Field("asdf", byte_index=(0, 1))
    # y intercept == x intercept == 0
    expected = b"\x00\x00"
    actual = enc.encode(0.0, dummyfield)
    assert actual == expected

    # also test 100.00
    expected = (100 * 512).to_bytes(2, "big")
    actual = enc.encode(100.0, dummyfield)
    assert actual == expected


def test_CCS811_reads(mocked_CCS811):
    """test if I set up the registers/fields correctly"""
    ccs = mocked_CCS811

    ccs.status.read()
    expected = dict(
        app_on=True, app_erase=False, app_verify=True, app_valid=True, data_ready=True, error=False
    )
    actual = ccs.status.values
    assert actual == expected

    ccs.meas_mode.read()
    expected = dict(sample_period=1, enable_interrupt=True, interrupt_on_thresh=True)
    actual = ccs.meas_mode.values
    assert actual == expected

    ccs.data.read()
    expected = {"eco2": 128, "tvoc": 256}
    actual = ccs.data.values
    assert actual == expected

    ccs.raw_data.read()
    expected = dict(current_uA=32, voltage=0.825)
    actual = ccs.raw_data.values
    assert actual == pytest.approx(expected, abs=1 / 1023)  # tolerance of transfer func

    ccs.env_data.read()
    expected = dict(humidity=0.0, temperature=-25.0)
    actual = ccs.env_data.values
    assert actual == expected

    ccs.baseline.read()
    expected = {"baseline": 0xFF}
    actual = ccs.baseline.values
    assert actual == expected

    ccs.chip_id.read()
    expected = {"chip_id": 0x81}
    actual = ccs.chip_id.values
    assert actual == expected

    ccs.error_id.read()
    expected = dict(
        invalid_write=True,
        invalid_read=False,
        invalid_mode=True,
        max_resistance=False,
        heater_fault=True,
        heater_supply=False,
    )
    actual = ccs.error_id.values
    assert actual == expected


def test_CCS811_MeasMode__validation(mocked_CCS811):
    ccs = mocked_CCS811
    bad_period = 123
    with pytest.raises(ValueError):
        ccs.meas_mode.write(sample_period=bad_period)


def test_CCS811_MeasMode__write(mocked_CCS811):
    ccs = mocked_CCS811
    expected = dict(
        sample_period=10,
        enable_interrupt=False,
        interrupt_on_thresh=False,
    )
    ccs.meas_mode.write(sample_period=10)
    actual = ccs._i2c_read(ccs.hardware.registers["meas_mode"])
    actual = ccs.hardware.registers["meas_mode"]._raw_bytes_to_field_values(actual)
    assert actual == expected
