import pytest
from sensors.i2c_base import _count_trailing_zeros, Field, UIntEncoder, Register, Device


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


def test_Register___eq__():
    r1 = Register("my_register", 0xFF, fields=(Field("f1"), Field("f2")))
    r2 = Register("other", 0x00, fields=[Field("f3")])
    assert not r1 == r2
    assert r1 == r1


def test_Register___repr__():
    expected = Register("my_register", 0xFF, fields=(Field("f1"), Field("f2")))
    actual = eval(repr(expected))
    assert actual == expected


def test_Register__raw_bytes_to_field_values():
    reg = Register(
        "my_register", 0xFF, fields=(Field("f1", bit_mask=0xF0), Field("f2", bit_mask=0x0F))
    )
    input_bytes = bytes([0b00011000])
    expected = {"f1": 0b0001, "f2": 0b1000}
    actual = reg._raw_bytes_to_field_values(input_bytes)
    assert actual == expected


def test_Register__field_values_to_raw_bytes__two_fields_in_one_byte():
    reg = Register(
        "my_register", 0xFF, fields=[Field("f1", bit_mask=0xF0), Field("f2", bit_mask=0x0F)]
    )
    input_field_values = {"f1": 0b0001, "f2": 0b1000}
    expected = bytes([0b00011000])
    actual = reg._field_values_to_raw_bytes(input_field_values)
    assert actual == expected


def test_Register__field_values_to_raw_bytes__two_fields_in_separate_bytes():
    reg = Register(
        "my_register", 0xFF, fields=[Field("f1", byte_index=(0,)), Field("f2", byte_index=(1,))]
    )
    input_field_values = {"f1": 0xFF, "f2": 0x00}
    expected = b"\xff\x00"
    actual = reg._field_values_to_raw_bytes(input_field_values)
    assert actual == expected


def test_Device___eq__():
    d1 = Device(
        "my_device",
        0xFF,
        {0: 0x00, 1: 0xFF},
        registers=[
            Register("r1", 0x00, fields=[Field("f1")]),
            Register("r2", 0x01, fields=[Field("f2")]),
        ],
    )
    d2 = Device(
        "other", 0x00, {0: 0x01, 1: 0xFE}, registers=[Register("r3", 0x02, fields=[Field("f4")])]
    )
    assert not d1 == d2
    assert d1 == d1


def test_Device___repr__():
    expected = Device(
        "my_device",
        0xFF,
        {0: 0x00, 1: 0xFF},
        registers=[
            Register("r1", 0x00, fields=[Field("f1")]),
            Register("r2", 0x01, fields=[Field("f2")]),
        ],
    )
    actual = eval(repr(expected))
    assert actual == expected
