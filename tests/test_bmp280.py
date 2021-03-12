import pytest
from sensors.bmp280 import _apply_calibration


def test__apply_calibration__datasheet_values():
    """example values from BMP280 datasheet"""
    calib = {
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
    raw_adc_vals = {"temperature": 519888, "pressure": 415148}

    expected = {"temperature": 25.08, "pressure": 100653.27}
    actual = _apply_calibration(raw_adc_vals, calib)
    assert actual == pytest.approx(expected, abs=1e-2)
