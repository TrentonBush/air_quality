import pytest
from sensors.bmp280 import _apply_calibration, BMP280
from sensors.i2c_base import MockSMBus, Register, Field


@pytest.fixture(scope="class")
def mocked_BMP280():
    # calibration and data values are same as in test__apply_calibration
    # converted with:
    # {k: f"{val.to_bytes(2, 'little', signed=True).hex()}"
    #   for k, val in calib.items() if val < 1<<15}
    # and:
    # {k: f"{val.to_bytes(2, 'little').hex()}"
    #   for k, val in calib.items() if val > 1<<15}

    # temp and press must be bit shifted << 4
    # (519888 << 4).to_bytes(3, 'big').hex()
    registers = {
        0xD0: 0x58,  # chip_id; id=0x58,
        0xE0: 0x00,  # reset; reset,
        0xF3: 0b00001001,  # status; measuring=True, im_update=True,
        0xF4: 0b01001010,  # ctrl_meas; osrs_t=2, osrs_p=2, mode=forced,
        0xF5: 0b10000100,  # config; t_sb=500, filter=2, spi3w_en=0,
        0xF7: 0x65,  # data.pressure, byte_0
        0xF8: 0x5A,  # data.pressure, byte_1
        0xF9: 0xC0,  # data.pressure, byte_2
        0xFA: 0x7E,  # data.temperature, byte_0
        0xFB: 0xED,  # data.temperature, byte_1
        0xFC: 0x00,  # data.temperature, byte_2
        0x88: 0x70,  # calibration.dig_t1, byte_0
        0x89: 0x6B,  # calibration.dig_t1, byte_1
        0x8A: 0x43,  # calibration.dig_t2, byte_0
        0x8B: 0x67,  # calibration.dig_t2, byte_1
        0x8C: 0x18,  # calibration.dig_t3, byte_0
        0x8D: 0xFC,  # calibration.dig_t3, byte_1
        0x8E: 0x7D,  # calibration.dig_p1, byte_0
        0x8F: 0x8E,  # calibration.dig_p1, byte_1
        0x90: 0x43,  # calibration.dig_p2, byte_0
        0x91: 0xD6,  # calibration.dig_p2, byte_1
        0x92: 0xD0,  # calibration.dig_p3, byte_0
        0x93: 0x0B,  # calibration.dig_p3, byte_1
        0x94: 0x27,  # calibration.dig_p4, byte_0
        0x95: 0x0B,  # calibration.dig_p4, byte_1
        0x96: 0x8C,  # calibration.dig_p5, byte_0
        0x97: 0x00,  # calibration.dig_p5, byte_1
        0x98: 0xF9,  # calibration.dig_p6, byte_0
        0x99: 0xFF,  # calibration.dig_p6, byte_1
        0x9A: 0x8C,  # calibration.dig_p7, byte_0
        0x9B: 0x3C,  # calibration.dig_p7, byte_1
        0x9C: 0xF8,  # calibration.dig_p8, byte_0
        0x9D: 0xC6,  # calibration.dig_p8, byte_1
        0x9E: 0x70,  # calibration.dig_p9, byte_0
        0x9F: 0x17,  # calibration.dig_p9, byte_1
    }
    smb = MockSMBus(registers)
    yield BMP280(smb)


@pytest.fixture
def sample_calib_data():
    """example values from BMP280 datasheet"""
    calibration_constants = {
        "dig_t1": 27504,
        "dig_t2": 26435,
        "dig_t3": -1000,
        "dig_p1": 36477,
        "dig_p2": -10685,
        "dig_p3": 3024,
        "dig_p4": 2855,
        "dig_p5": 140,
        "dig_p6": -7,
        "dig_p7": 15500,
        "dig_p8": -14600,
        "dig_p9": 6000,
    }
    raw_adc_vals = {
        "temperature": 519888,
        "pressure": 415148,
    }  # NOT raw bytes! this is after masking
    calibrated = {"temperature": 25.08, "pressure": 100653.27}
    yield calibration_constants, raw_adc_vals, calibrated


def test_mocked_bmp280_calib_consts(mocked_BMP280, sample_calib_data):
    """confirm that I encoded the test calib constants correctly"""
    calib_const, raw_adc_vals, calibrated = sample_calib_data
    bmp = mocked_BMP280
    bmp.calibration.read()
    expected = calib_const
    actual = bmp.calibration.values
    assert actual == expected


def test_mocked_bmp280_raw_adc_values(mocked_BMP280, sample_calib_data):
    """confirm that I encoded the test raw_adc_values correctly"""
    calib_const, raw_adc_vals, calibrated = sample_calib_data
    bmp = mocked_BMP280
    expected = raw_adc_vals
    actual = bmp._i2c_read(bmp.hardware.registers["data"])
    actual = bmp.hardware.registers["data"]._raw_bytes_to_field_values(actual)
    assert actual == expected


def test__apply_calibration__datasheet_values(sample_calib_data):
    calib, raw_adc_vals, expected = sample_calib_data
    actual = _apply_calibration(raw_adc_vals, calib)
    assert actual == pytest.approx(expected, abs=1e-2)


def test_BMP280__i2c_read(mocked_BMP280):
    bmp = mocked_BMP280
    reg = Register("chip_id", 0xD0, (Field("id"),))
    expected = b"\x58"
    actual = bmp._i2c_read(reg)
    assert actual == expected


def test_BMP280__i2c_write(mocked_BMP280):
    bmp = mocked_BMP280
    reg = Register("chip_id", 0xD0, (Field("id"),))
    bmp._i2c_write(reg, b"\xFF")
    expected = int.from_bytes(b"\xFF", "big")
    actual = bmp._i2c.regs[0xD0]
    assert actual == expected


def test_BMP280_BaseRegister_read(mocked_BMP280):
    bmp = mocked_BMP280
    expected = {"measuring": 1, "im_update": 1}
    bmp.status.read()
    actual = bmp.status.values
    assert actual == expected


def test_BMP280_ReadOnlyRegister_write(mocked_BMP280):
    bmp = mocked_BMP280
    with pytest.raises(AttributeError):
        bmp.status.write()


def test_BMP280_Reset_read(mocked_BMP280):
    """write-only register"""
    bmp = mocked_BMP280
    with pytest.raises(AttributeError):
        bmp.reset.read()


def test_BMP280_Data_read(mocked_BMP280, sample_calib_data):
    _, _, expected = sample_calib_data
    bmp = mocked_BMP280
    bmp.data.read()
    actual = bmp.data.values
    assert actual == pytest.approx(expected, abs=1e-2)


def test_BMP280_CtrlMeas_validation(mocked_BMP280):
    bmp = mocked_BMP280
    bad_measurement_mode = "asdf"
    bad_oversampling_value = 7
    with pytest.raises(ValueError):
        bmp.ctrl_meas.write(measurement_mode=bad_measurement_mode)
    with pytest.raises(ValueError):
        bmp.ctrl_meas.write(pressure_oversampling=bad_oversampling_value)
    with pytest.raises(ValueError):
        bmp.ctrl_meas.write(temperature_oversampling=bad_oversampling_value)


def test_BMP280_CtrlMeas_write(mocked_BMP280):
    bmp = mocked_BMP280
    expected = {
        "osrs_t": 2,
        "osrs_p": 4,
        "mode": "forced",
    }
    bmp.ctrl_meas.write(
        pressure_oversampling=4, temperature_oversampling=2, measurement_mode="trigger"
    )
    actual = bmp._i2c_read(bmp.hardware.registers["ctrl_meas"])
    actual = bmp.hardware.registers["ctrl_meas"]._raw_bytes_to_field_values(actual)
    assert actual == expected


def test_BMP280_Config_validation(mocked_BMP280):
    bmp = mocked_BMP280
    bad_measurement_period = 123.456
    bad_filter_const = 7
    with pytest.raises(ValueError):
        bmp.config.write(measurement_period_ms=bad_measurement_period)
    with pytest.raises(ValueError):
        bmp.config.write(smoothing_const=bad_filter_const)


def test_BMP280_Config_write(mocked_BMP280):
    bmp = mocked_BMP280
    expected = {
        "t_sb": 250,
        "filter": 2,
        "spi3w_en": 0,
    }
    bmp.config.write(measurement_period_ms=250, smoothing_const=2, disable_I2C=False)
    actual = bmp._i2c_read(bmp.hardware.registers["config"])
    actual = bmp.hardware.registers["config"]._raw_bytes_to_field_values(actual)
    assert actual == expected
