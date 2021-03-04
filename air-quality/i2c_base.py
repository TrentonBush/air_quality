from abc import ABC, abstractmethod
from typing import Dict, Tuple, Optional, Any, Sequence
from collections.abc import Mapping
from smbus2 import SMBus


def _bit_mask(value: bytes, bit_mask: Optional[int]) -> bytes:
    if bit_mask is None:
        return value
    raise NotImplementedError


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
        raise ValueError("{} not in lookup table".format(value))


class Field(object):
    """Immutable properties of a field or flag in an i2c register"""

    def __init__(
        self,
        name: str,
        byte_index: Tuple[int, ...] = (0,),
        bit_mask: Optional[int] = None,
        encoder: Encoder = PassThroughEncoder(),
        n_bits: int = 8,
        read_only: bool = False,
    ) -> None:
        self.name = name
        self.byte_index = byte_index
        self.bit_mask = bit_mask
        self.encoder = encoder
        self.n_bits = n_bits
        self.read_only = read_only
        self._slice = slice(self.byte_index[0], self.byte_index[-1] + 1)

    def __repr__(self):
        attrs = {attr: val for attr, val in self.__dir__.items() if not attr.startswith("_")}
        sig = ", ".join(f"{attr}={val!r}" for attr, val in attrs.items())
        return f"{self.__class__.__name__}({sig})"

    def encode(self, value) -> bytes:
        return self.encoder.encode(value, self)

    def decode(self, value: bytes):
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
        attrs = {attr: val for attr, val in self.__dir__.items() if not attr.startswith("_")}
        attrs["fields"] = list(attrs["fields"].values())
        sig = ", ".join(f"{attr}={val!r}" for attr, val in attrs.items())
        return f"{self.__class__.__name__}({sig})"


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
        attrs = {attr: val for attr, val in self.__dir__.items() if not attr.startswith("_")}
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

    def _i2c_read(self, register: Register):
        return bytes(
            self._i2c.read_i2c_block_data(
                self.address,
                register.address,
                # TODO: check if I need type(self) here:
                register.n_bits // self.hardware.word_size,
            )
        )

    def _raw_bytes_to_field_values(self, register: Register, reg_values: bytes) -> Dict[str, Any]:
        raise NotImplementedError

    def _field_values_to_raw_bytes(self, register: Register, field_values: Dict[str, Any]) -> bytes:
        raise NotImplementedError


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
