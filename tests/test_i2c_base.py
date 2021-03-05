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


def test_UIntEncoder__encode_normal_one_byte():
    field = Field("my_field", byte_index=(0,))
    encoder = UIntEncoder()
    input_value = 0b10000001
    expected = b"\x81"
    actual = encoder.encode(input_value, field)
    assert actual == expected


def test_UIntEncoder__encode_normal_multi_byte():
    field = Field("my_field", byte_index=(0, 1, 2))
    encoder = UIntEncoder()
    input_value = 0xABCDEF
    expected = b"\xAB\xCD\xEF"
    actual = encoder.encode(input_value, field)
    assert actual == expected


def test_UIntEncoder__decode_normal_one_byte():
    field = Field("my_field", byte_index=(0,))
    encoder = UIntEncoder()
    input_value = b"\x81"
    expected = 0b10000001
    actual = encoder.decode(input_value, field)
    assert actual == expected


def test_UIntEncoder__decode_normal_multi_byte():
    field = Field("my_field", byte_index=(0, 1, 2))
    encoder = UIntEncoder()
    input_value = b"\xAB\xCD\xEF"
    expected = 0xABCDEF
    actual = encoder.decode(input_value, field)
    assert actual == expected


def test_Field___eq__():
    f1 = Field("my_field", byte_index=(0, 1), bit_mask=0b00111000)
    f2 = Field("new_field")
    assert not f1 == f2
    assert f1 == f1


def test_Field___repr__():
    expected = Field("my_field", byte_index=(0, 1), bit_mask=0b00111000)
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


def test_Field_with_UIntEncoder__encode_normal_one_byte():
    field = Field("", bit_mask=0b11110000, encoder=UIntEncoder())
    input_value = 0b00000011
    expected = bytes([0b00110000])
    actual = field.encode(input_value)
    assert actual == expected


def test_Field_with_UIntEncoder__encode_normal_multi_byte():
    field = Field("", byte_index=(0, 1, 2), bit_mask=0x0FFFF0, encoder=UIntEncoder())
    input_value = 0x00FF00
    expected = (0x0FF000).to_bytes(3, "big")
    actual = field.encode(input_value)
    assert actual == expected


def test_Field_with_UIntEncoder__decode_normal_one_byte():
    field = Field("", bit_mask=0b11110000, encoder=UIntEncoder())
    input_value = bytes([0b00111100])
    expected = 0b00000011
    actual = field.decode(input_value)
    assert actual == expected


def test_Field_with_UIntEncoder__decode_normal_multi_byte():
    field = Field("", byte_index=(0, 1, 2), bit_mask=0x0FFFF0, encoder=UIntEncoder())
    input_value = (0xFFF000).to_bytes(3, "big")
    expected = 0x00FF00
    actual = field.decode(input_value)
    assert actual == expected
