from abc import ABC, abstractmethod
from dataclasses import dataclass, InitVar
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


@dataclass(frozen=True, eq=False)
class Field(object):
    """Immutable properties of a field or flag in an i2c register"""

    name: str
    byte_index: Tuple[int, ...] = (0,)
    bit_mask: Optional[int] = None
    encoder: Encoder = PassThroughEncoder()
    n_bits: int = 8
    read_only: bool = False

    def __post_init__(self) -> None:
        # NOTE: must use __setattr__ due to quirk of frozen dataclasses
        # for slicing bytes from register
        object.__setattr__(
            self, "_slice", slice(self.byte_index[0], self.byte_index[-1] + 1)
        )

    def encode(self, value) -> bytes:
        return self.encoder.encode(value, self)

    def decode(self, value: bytes):
        return self.encoder.decode(value, self)


@dataclass(eq=False)
class Register(object):
    """Immutable properties of an i2c register"""

    name: str
    address: int
    fields: InitVar[Sequence[Field]] # InitVar not in __repr__
    n_bits: int = 8
    read_only: bool = False
    volatile: bool = True

    def __post_init__(self, fields) -> None:
        self.fields: Dict[str, Field] = {field.name: field for field in fields}


@dataclass(eq=False)
class Device(object):
    """Immutable properties of an I2C device"""

    name: str
    chip_id: int
    i2c_addresses: Mapping[int, int]
    registers: Sequence[Register]  # not using InitVar makes mypy angry
    byte_order: str = "big"
    word_size: int = 8

    def __post_init__(self) -> None:
        new_vals = {register.name: register for register in self.registers}
        self.registers: Dict[str, Register] = new_vals


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

    def _raw_bytes_to_field_values(
        self, register: Register, reg_values: bytes
    ) -> Dict[str, Any]:
        raise NotImplementedError

    def _field_values_to_raw_bytes(
        self, register: Register, field_values: Dict[str, Any]
    ) -> bytes:
        raise NotImplementedError


class BaseRegisterAPI(ABC):
    """base class to provide documented .read() and .write() methods for registers of BaseDeviceAPI subclasses.

    This class serves two purposes: 1) create a helpful API and 2) cache values.
    A BaseDeviceAPI that contains BaseRegisterAPI attributes produces an API format like:
    sensor.register.write(field_1=x, field_2=y)

    This is so .write() can have a descriptive function signature and the docstring
    has key info from the datasheet, like arg descriptions and appropriate values.

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


"""
Below is an implementation of Device with frozen=True.
It shows/explains a conflict between frozen dataclasses and mypy
and why I opted to remove the frozen parameter entirely.

from dataclasses import dataclass, InitVar
import dataclasses.field # weird import due to name collision

@dataclass(frozen=True)
class Device(object):

    name: str
    chip_id: int
    i2c_addresses: Mapping[int, int]
    _registers: InitVar[Sequence[Register]]
    byte_order = "big"
    word_size: int = 8
    registers: Dict[str, Register] = dataclasses.field(default_factory=dict)
    # Why I have both .registers and ._registers:
    # short version: there is a conflict between frozen dataclasses and mypy

    # long version:
    # I wanted to simply do:
    # registers: Sequence[Register]
    # then in __post_init__:
    # self.registers = {register.name: register for register in self.registers}

    # But frozen dataclasses remove attribute assignment, so that doesn't work.
    # Instead, I had use object.__setattr__ (per docs: https://docs.python.org/3/library/dataclasses.html#frozen-instances)
    # object.__setattr__(self, "registers", {register.name: register for register in self.registers})
    # But mypy can't follow dynamic assignment, and thinks it's still Sequence[Register]

    # The solution here makes a temporary (InitVar) _registers attr and an empty dict
    # then fills the dict in __post_init__. But this makes a confusing API :(
    # So I dropped the frozen=True instead.
    def __post_init__(self) -> None:
        for register in self._registers:
            self.registers[register.name] = register
"""
