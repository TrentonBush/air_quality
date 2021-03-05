from abc import ABC, abstractmethod
from typing import Dict, Tuple, Optional, Any, Sequence
from collections.abc import Mapping
from collections import defaultdict
from functools import reduce
from smbus2 import SMBus


def _count_trailing_zeros(mask: int) -> int:
    """count the trailing zeros of a bit mask. Used for shifting.

    Args:
        mask (int): bit mask, eg 0b00111000

    Returns:
        int: number of trailing zeros
    """
    count = 0
    for i in range(mask.bit_length()):
        if mask & 1:
            return count
        count += 1
        mask >>= 1
    return count


class Encoder(ABC):
    """base class for encode/decode methods to convert between human- and machine-readable data"""

    @abstractmethod
    def encode(self, value, field) -> bytes:
        """encode human-readable value to machine value"""
        ...

    @abstractmethod
    def decode(self, value: bytes, field) -> Any:
        """decode machine value to human-readable value"""
        ...


class PassThroughEncoder(Encoder):
    """returns values unchanged"""

    def encode(self, value, field):
        return value

    def decode(self, value, field):
        return value


class LookupTable(Encoder):
    """Encode with a dictionary of values"""

    def __init__(self, lookup_table: dict):
        self.lookup_table = lookup_table

    def encode(self, value, field):
        return self.lookup_table[value]

    def decode(self, value, field):
        for k, v in self.lookup_table.items():
            if v == value:
                return k
        raise ValueError(f"{value} not in lookup table")


class Field(object):
    """Immutable properties of a field or flag in an i2c register"""

    def __init__(
        self,
        name: str,
        byte_index: Tuple[int, ...] = (0,),
        bit_mask: Optional[int] = None,
        encoder: Encoder = PassThroughEncoder(),
        read_only: bool = False,
    ) -> None:
        self.name = name
        self.byte_index = byte_index
        self.bit_mask = bit_mask
        self.encoder = encoder
        self.read_only = read_only
        self._slice = slice(self.byte_index[0], self.byte_index[-1] + 1)
        self._shift = None
        if self.bit_mask is not None:
            self._shift = _count_trailing_zeros(self.bit_mask)

    def __repr__(self):
        attrs = ["name", "byte_index", "bit_mask", "encoder", "read_only"]
        sig = ", ".join(f"{attr}={getattr(self, attr)!r}" for attr in attrs)
        return f"{self.__class__.__name__}({sig})"

    def _decode_mask(self, raw_bytes: bytes) -> bytes:
        if self.bit_mask is None:
            return raw_bytes
        out = int.from_bytes(raw_bytes, "big")  # always 'big' for masking
        out &= self.bit_mask
        out >>= self._shift  # type: ignore    # _shift is None when bit_mask is None
        return out.to_bytes(
            length=-(out.bit_length() // -8), byteorder="big"  # double negation is like ceil()
        )

    def _encode_mask(self, encoded_bytes: bytes) -> bytes:
        if self.bit_mask is None:
            return encoded_bytes
        out = int.from_bytes(encoded_bytes, "big")
        out <<= self._shift  # type: ignore    # _shift is None when bit_mask is None
        return out.to_bytes(
            length=-(out.bit_length() // -8), byteorder="big"  # double negation is like ceil()
        )

    def encode(self, value: Any) -> bytes:
        out = self.encoder.encode(value, self)
        return self._encode_mask(out)

    def decode(self, value: bytes):
        value = self._decode_mask(value)
        return self.encoder.decode(value, self)


class Register(object):
    """Immutable properties of an i2c register"""

    def __init__(
        self,
        name: str,
        address: int,
        fields: Sequence[Field],
        n_bits: int = 8,
        read_only: bool = False,
        volatile: bool = True,
    ) -> None:
        self.name = name
        self.address = address
        self.fields: Dict[str, Field] = {field.name: field for field in fields}
        self.n_bits = n_bits
        self.read_only = read_only
        self.volatile = volatile

    def __repr__(self):
        attrs = ["name", "address", "fields", "n_bits", "read_only", "volatile"]
        attrs = {attr: getattr(self, attr) for attr in attrs}
        attrs["fields"] = list(attrs["fields"].values())
        sig = ", ".join(f"{attr}={val!r}" for attr, val in attrs.items())
        return f"{self.__class__.__name__}({sig})"

    def _raw_bytes_to_field_values(self, raw_bytes: bytes) -> Dict[str, Any]:
        out = {}
        for field in self.fields.values():
            bytes_ = raw_bytes[field._slice]
            out[field.name] = field.decode(bytes_)
        return out

    def _field_values_to_raw_bytes(self, field_values: Dict[str, Any]) -> bytes:
        # determine if multiple fields are encoded in the same byte
        byte_map = defaultdict(list)
        for name, value in field_values.items():
            field = self.fields[name]
            byte_map[field.byte_index].append(field.encode(value))
        # merge multiples
        for index, values in byte_map.items():
            if len(values) == 1:
                continue
            ints = [int.from_bytes(val, "big") for val in values]
            merged = reduce(lambda x, y: x | y, ints)
            n_bytes = index[-1] - index[0] + 1
            byte_map[index] = [merged.to_bytes(n_bytes, "big")]
        # join in correct order
        return b"".join((byte_map[idx][0] for idx in sorted(byte_map)))


class Device(object):
    """Immutable properties of an I2C device"""

    def __init__(
        self,
        name: str,
        chip_id: int,
        i2c_addresses: Mapping[int, int],
        registers: Sequence[Register],
        byte_order: str = "big",
        word_size: int = 8,
    ) -> None:
        self.name = name
        self.chip_id = chip_id
        self.i2c_addresses = i2c_addresses
        self.registers: Dict[str, Register] = {register.name: register for register in registers}
        self.byte_order = byte_order
        self.word_size = word_size

    def __repr__(self):
        attrs = ["name", "chip_id", "i2c_addresses", "registers", "byte_order", "word_size"]
        attrs = {attr: getattr(self, attr) for attr in attrs}
        attrs["registers"] = list(attrs["registers"].values())
        sig = ", ".join(f"{attr}={val!r}" for attr, val in attrs.items())
        return f"{self.__class__.__name__}({sig})"


class BaseDeviceAPI(ABC):
    """base class for making APIs for an i2c hardware device"""

    @property
    @classmethod
    @abstractmethod
    def hardware(cls) -> Device:  # abstract class attribute
        ...

    def __init(self, i2c_interface: SMBus, address_pin_level: int = 0):
        self._i2c = i2c_interface
        self._address_level = address_pin_level
        # TODO: check if I need type(self) here:
        self.address = self.hardware.i2c_addresses[self._address_level]

    def _i2c_write(self, register: Register, values: bytes):
        self._i2c.write_i2c_block_data(self.address, register.address, values)

    def _i2c_read(self, register: Register) -> bytes:
        return bytes(
            self._i2c.read_i2c_block_data(
                self.address,
                register.address,
                # TODO: check if I need type(self) here:
                register.n_bits // self.hardware.word_size,
            )
        )


class BaseRegisterAPI(ABC):
    """base class for registers contained in BaseDeviceAPI subclasses.

    This class serves two purposes: 1) create a helpful API and 2) cache values.
    A BaseDeviceAPI that contains BaseRegisterAPI attributes has an API format like:
    sensor.register.write(field_1=x, field_2=y)

    The .write() method should have a descriptive function signature and the docstring
    should have key info from the datasheet, like arg descriptions and appropriate values.

    Example API:
    bmp280.config.write(measurement_period_ms=250, iir_filter_const=8)
    """

    def __init__(self, parent_device: BaseDeviceAPI, reg_name: str):
        self._parent_device = parent_device
        self._reg = self._parent_device.hardware.registers[reg_name]
        self._cached = {field.name: None for field in self._reg.fields.values()}

    @abstractmethod
    def write(self):
        ...

    @abstractmethod
    def read(self):
        ...
