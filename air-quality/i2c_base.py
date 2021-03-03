from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence, Tuple


class ValueEncoder(ABC):
    """base class for encode/decode methods to convert between human- and hardware-readable data"""

    @abstractmethod
    def encode(self, value):
        """encode human-readable value to hardware value"""
        raise NotImplementedError

    @abstractmethod
    def decode(self, value):
        """decode hardware value to human-readable value"""
        raise NotImplementedError


class PassThroughEncoder(ValueEncoder):
    """returns values unchanged"""
    @staticmethod
    def decode(value):
        return value

    @staticmethod
    def encode(value):
        return value


class LookupTable(ValueEncoder):
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
    bit_mask: int = 0xFF
    encoder: ValueEncoder = PassThroughEncoder()
    bit_width = 8
    read_only = False

    # self._byte_index = slice(byte_index[0], byte_index[-1] + 1)


@dataclass(frozen=True)
class Register(object):
    """Store immutable config for an i2c register"""
    name: str
    address: int
    fields: Sequence[Field]
    bit_width = 8
    read_only = False
    volatile = True
