import pytest
from sensors.i2c_base import _count_trailing_zeros, Field, UIntEncoder


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


@pytest.fixture
def basic_Field():
    f = Field(
        "my_field", byte_index=(0, 1), bit_mask=0b00111000, encoder=UIntEncoder(), read_only=False
    )
    yield f


def test_Field___eq__(basic_Field):
    f1 = basic_Field
    f2 = Field("new_field")
    assert not f1 == f2
    assert f1 == f1


def test_Field___repr__(basic_Field):
    expected = basic_Field
    actual = eval(repr(expected))
    assert actual == expected


def test_Field__decode_mask__condition_bit_mask_is_None():
    f = Field("", bit_mask=None)
    input_bytes = bytes(list(range(3)))
    expected = input_bytes
    actual = f._decode_mask(input_bytes)
    assert actual == expected


def test_Field__decode_mask__normal_one_byte():
    """
                mask:   0b11110000
                raw:    0b00111100 <- input
                masked: 0b00110000
    masked & shifted:   0b00000011 <- output
    """
    f = Field("", bit_mask=0b11110000)
    input_bytes = bytes([0b00111100])
    expected = bytes([0b00000011])
    actual = f._decode_mask(input_bytes)
    assert actual == expected


def test_Field__decode_mask__normal_multi_byte():
    """
                mask:   0x0FFFF0
                raw:    0xFFF000 <- input
                masked: 0x0FF000
    masked & shifted:   0x00FF00 <- output
    """
    f = Field("", byte_index=(0, 1, 2), bit_mask=0x0FFFF0)
    input_bytes = (0xFFF000).to_bytes(3, "big")
    expected = (0x00FF00).to_bytes(3, "big")
    actual = f._decode_mask(input_bytes)
    assert actual == expected


def test_Field__encode_mask__condition_bit_mask_is_None():
    f = Field("", bit_mask=None)
    input_bytes = bytes(list(range(3)))
    expected = input_bytes
    actual = f._encode_mask(input_bytes)
    assert actual == expected


def test_Field__encode_mask__normal_one_byte():
    """
    mask:       0b11110000
    encoded:    0b00000011 <- input
    shifted:    0b00110000 <- output
    """
    f = Field("", bit_mask=0b11110000)
    input_bytes = bytes([0b00000011])
    expected = bytes([0b00110000])
    actual = f._encode_mask(input_bytes)
    assert actual == expected


def test_Field__encode_mask__normal_multi_byte():
    """
    mask:       0x0FFFF0
    encoded:    0x00FF00 <- input
    shifted:    0x0FF000 <- output
    """
    f = Field("", byte_index=(0, 1, 2), bit_mask=0x0FFFF0)
    input_bytes = (0x00FF00).to_bytes(3, "big")
    expected = (0x0FF000).to_bytes(3, "big")
    actual = f._encode_mask(input_bytes)
    assert actual == expected
