import pytest
from sensors.i2c_base import _count_trailing_zeros, Field


def test__count_trailing_zeros__edge_no_trailing():
    mask = 0b1
    expected = 0
    actual = _count_trailing_zeros(mask)
    assert actual == expected


def test__count_trailing_zeros__normal_one_byte():
    mask = 0b1000
    expected = 3
    actual = _count_trailing_zeros(mask)
    assert actual == expected


def test__count_trailing_zeros__normal_multi_byte():
    mask = 0xFFFF000
    expected = 12
    actual = _count_trailing_zeros(mask)
    assert actual == expected


def test__count_trailing_zeros__edge_all_zeros():
    mask = 0b0
    with pytest.raises(ValueError):
        _count_trailing_zeros(mask)
