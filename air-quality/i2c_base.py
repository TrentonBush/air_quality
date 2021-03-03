from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Tuple, Type, Optional
from collections.abc import Mapping

def _bit_mask(value: bytes, bit_mask: Optional[int]) -> bytes:
    if bit_mask is None:
        return value
    raise NotImplementedError


class Encoder(ABC):
    """base class for encode/decode methods to convert between human- and machine-readable data"""

    @staticmethod
    @abstractmethod
    def encode(value, field: Field) -> bytes:
        """encode human-readable value to machine value"""
        pass

    @staticmethod
    @abstractmethod
    def decode(value: bytes, field: Field):
        """decode machine value to human-readable value"""
        pass


class PassThroughEncoder(Encoder):
    """returns values unchanged"""

    @staticmethod
    def encode(value):
        return value

    @staticmethod
    def decode(value):
        return value


class LookupTable(Encoder):
    """Encode with a dictionary of values"""

    def __init__(self, lookup_table: dict):
        self.lookup_table = lookup_table

    def encode(self, value):
        return self.lookup_table[value]

    def decode(self, value):
        for k, v in self.lookup_table.items():
            if v == value:
                return k
        raise ValueError("{} not in lookup table".format(value))


@dataclass(frozen=True)
class Field(object):
    """Store immutable config for a field or flag in an i2c register"""
    name: str
    byte_index: Tuple[int, ...] = (0,)
    bit_mask: Optional[int] = None
    encoder: Type[Encoder] = PassThroughEncoder  # uses static methods
    bit_width = 8
    read_only = False

    def __post_init__(self):
        self._slice = slice(byte_index[0], byte_index[-1] + 1) # for slicing bytes from register
    
    def encode(self, value) -> bytes:
        return self.encoder.encode(value, self)

    def decode(self, value: bytes):
        return self.encoder.decode(value, self)


@dataclass(frozen=True)
class Register(object):
    """Store immutable config for an i2c register"""
    name: str
    address: int
    fields: Dict[str, Field]
    bit_width = 8
    read_only = False
    volatile = True


@dataclass(frozen=True)
class Device(object):
    """Store immutable config for an I2C device"""
    name: str
    chip_id: int
    i2c_addresses: Mapping[int, int]
    registers: Dict[str, Register]
    byte_order = 'big'
    bit_width: int = 8