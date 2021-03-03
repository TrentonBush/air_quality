"""Driver for the Bosch BMP280 pressure sensor"""
from smbus2 import SMBus
from abc import ABC, abstractmethod
import sys

from .i2c_base import Device, Register, Field, Encoder, LookupTable, _bit_mask


class Int16(Encoder):
    """Signed 16 bit integer"""
    @staticmethod
    def encode(value: int, field) -> bytes:
        pass # relevant field is read-only
    @staticmethod
    def decode(value: bytes, field) -> int:
        if len(value) != 2:
            raise ValueError(f"Not 16 bits. Given: {value}")
        value = _bit_mask(value, field.bit_mask)
        return int.from_bytes(value, BMP280.hardware.byte_order, signed=True)


class UInt16(Encoder):
    """Unsigned 16 bit integer"""
    @staticmethod
    def encode(value: int, field) -> bytes:
        pass # relevant field is read-only
    @staticmethod
    def decode(value: bytes, field) -> int:
        if len(value) != 2:
            raise ValueError(f"Not 16 bits. Given: {value}")
        value = _bit_mask(value, field.bit_mask)
        return int.from_bytes(value, BMP280.hardware.byte_order)


class RegisterAPI(ABC):
    def __init__(self, bmp280: BMP280, reg_name: str):
        self._reg = bmp280.hardware.registers[reg_name]
        self._cached = {field.name: None for field in self._reg.fields.values()}
    
    @abstractmethod
    def write(self):
        pass
    @abstractmethod
    def read(self):
        pass

class ConfigAPI(RegisterAPI):
    def write(self, temp_standby_ms = 4000, iir_filter_const = 8, spi = False):
        """write to the config register

        Args:
            temp_standby_ms (int, optional): time (unit: ms) between temperature measurements in constant sampling mode. Possible values are [0.5, 62.5, 125, 250, 500, 1000, 2000, 4000]. Defaults to 4000.
            iir_filter_const (int, optional): IIR filter coefficient. Higher -> smoother. Possible values are [0, 2, 4, 8, 16]. Defaults to 8.
            spi (bool, optional): Enable SPI interface, which means none of this code will work. Defaults to False.
        """
        raise NotImplementedError

    def read(self):
        """read current config"""
        raise NotImplementedError


class BMP280(object):
    hardware = Device(
        "bmp280",
        chip_id=0x58,
        i2c_addresses={0: 0x76, 1: 0x77},  # address pin logic level 0, 1 (GND, VCC)
        registers={
            "chip_id": Register(
                "chip_id", 0xD0, fields=(Field("id")), read_only=True, volatile=False
            ),
            "reset": Register("reset", 0xE0, fields=(Field("reset"))),
            "status": Register(
                "status",
                0xF3,
                fields=(
                    Field("measuring", bit_mask=0b00001000),  # 1 when conversion is running
                    Field(
                        "im_update", bit_mask=0b00000001
                    ),  # 1 when NVM data is being copied
                ),
                read_only=True,
            ),
            "ctrl_meas": Register(
                "ctrl_meas",
                0xF4,
                fields=(
                    Field(
                        "osrs_t",
                        bit_mask=0b11100000,  # Temperature oversampling
                        encoder=LookupTable(
                            {1: 0b001, 2: 0b010, 4: 0b011, 8: 0b100, 16: 0b101}
                        ),
                    ),
                    Field(
                        "osrs_p",
                        bit_mask=0b00011100,  # Pressure oversampling
                        encoder=LookupTable(
                            {1: 0b001, 2: 0b010, 4: 0b011, 8: 0b100, 16: 0b101}
                        ),
                    ),
                    Field(
                        "mode",
                        bit_mask=0b00000011,  # Power mode
                        encoder=LookupTable(
                            {"sleep": 0b00, "forced": 0b10, "normal": 0b11}
                        ),
                    ),
                ),
            ),
            "config": Register(
                "config",
                0xF5,
                fields=(
                    Field(
                        "t_sb",
                        bit_mask=0b11100000,  # Temp standby duration in 'normal' power mode
                        encoder=LookupTable(
                            {
                                0.5: 0b000,
                                62.5: 0b001,
                                125: 0b010,
                                250: 0b011,
                                500: 0b100,
                                1000: 0b101,
                                2000: 0b110,
                                4000: 0b111,
                            }
                        ),
                    ),
                    Field("filter", bit_mask=0b00011100),  # time constant of the IIR filter
                    Field("spi3w_en", bit_mask=0b0000001),  # Enable 3-wire SPI interface
                ),
            ),
            "data": Register(
                "data",
                0xF7,
                fields=(
                    Field("temperature", byte_index=(3, 5), bit_mask=0xFFFFF0),
                    Field("pressure", byte_index=(0, 2), bit_mask=0xFFFFF0),
                ),
                bit_width=48,
                read_only=True,
            ),
            "calibration": Register(
                "calibration",
                0x88,
                fields=(
                    Field("dig_t1", byte_index=(0, 1), encoder=UInt16),  # 0x88 0x89
                    Field("dig_t2", byte_index=(2, 3), encoder=Int16),  # 0x8A 0x8B
                    Field("dig_t3", byte_index=(4, 5), encoder=Int16),  # 0x8C 0x8D
                    Field("dig_p1", byte_index=(6, 7), encoder=UInt16),  # 0x8E 0x8F
                    Field("dig_p2", byte_index=(8, 9), encoder=Int16),  # 0x90 0x91
                    Field("dig_p3", byte_index=(10, 11), encoder=Int16),  # 0x92 0x93
                    Field("dig_p4", byte_index=(12, 13), encoder=Int16),  # 0x94 0x95
                    Field("dig_p5", byte_index=(14, 15), encoder=Int16),  # 0x96 0x97
                    Field("dig_p6", byte_index=(16, 17), encoder=Int16),  # 0x98 0x99
                    Field("dig_p7", byte_index=(18, 19), encoder=Int16),  # 0x9A 0x9B
                    Field("dig_p8", byte_index=(20, 21), encoder=Int16),  # 0x9C 0x9D
                    Field("dig_p9", byte_index=(22, 23), encoder=Int16),  # 0x9E 0x9F
                ),
                bit_width=192,
                read_only=True,
                volatile=False,
            ),
        },
    )

    def __init(self, i2c_interface: SMBus, address_pin_level: int = 0):
        self._i2c_interface = i2c_interface
        self._address_level = address_pin_level
        self.address = BMP280.hardware.i2c_addresses[self._address_level]
        self._cached = {
            register.name: {field.name: None for field in register.fields.values()}
            for register in BMP280.hardware.registers.values()
        }
