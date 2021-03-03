"""Driver for the Bosch BMP280 pressure sensor"""
from smbus2 import SMBus
import sys

from .i2c_base import Register, Field, ValueEncoder, LookupTable


class SignedInt16(ValueEncoder):
    @staticmethod
    def encode(value: int):
        b = value.to_bytes()


class BMP280(object):
    chip_id = 0x58
    i2c_addresses = (0x76, 0x77) # address pin logic level 0, 1 (GND, VCC)
    byte_order = 'big'
    registers = {
        'chip_id': Register('chip_id', 0xD0, fields=(Field('id')), read_only=True, volatile=False),
        'reset': Register('reset', 0xE0, fields=(Field('reset'))),
        'status': Register('status', 0xF3, fields=(
            Field('measuring', bit_mask=0b00001000),  # 1 when conversion is running
            Field('im_update', bit_mask=0b00000001),  # 1 when NVM data is being copied
        ), read_only=True),
        'ctrl_meas': Register('ctrl_meas', 0xF4, fields=(
            Field('osrs_t', bit_mask=0b11100000,   # Temperature oversampling
                        encoder=LookupTable({
                            1: 0b001,
                            2: 0b010,
                            4: 0b011,
                            8: 0b100,
                            16: 0b101
                        })),
            Field('osrs_p', bit_mask=0b00011100,   # Pressure oversampling
                        encoder=LookupTable({
                            1: 0b001,
                            2: 0b010,
                            4: 0b011,
                            8: 0b100,
                            16: 0b101})),
            Field('mode', bit_mask=0b00000011,     # Power mode
                        encoder=LookupTable({
                            'sleep': 0b00,
                            'forced': 0b10,
                            'normal': 0b11})),
        )),
        'config': Register('config', 0xF5, fields=(
            Field('t_sb', bit_mask=0b11100000,     # Temp standby duration in 'normal' power mode
                        encoder=LookupTable({
                            0.5: 0b000,
                            62.5: 0b001,
                            125: 0b010,
                            250: 0b011,
                            500: 0b100,
                            1000: 0b101,
                            2000: 0b110,
                            4000: 0b111})),
            Field('filter', bit_mask=0b00011100),                   # time constant of the IIR filter
            Field('spi3w_en', bit_mask=0b0000001),  # Enable 3-wire SPI interface
        )),
        'data': Register('data', 0xF7, fields=(
            Field('temperature', byte_index=(3,5), bit_mask=0xFFFFF0),
            Field('pressure', byte_index=(0,2), bit_mask=0xFFFFF0),
        ), bit_width=48, read_only=True),
        'calibration': Register('calibration', 0x88, fields=(
            Field('dig_t1', byte_index=(0,1), encoder=U16Adapter()),   # 0x88 0x89
            Field('dig_t2', byte_index=(2,3), encoder=S16Adapter()),   # 0x8A 0x8B
            Field('dig_t3', byte_index=(4,5), encoder=S16Adapter()),    # 0x8C 0x8D
            Field('dig_p1', byte_index=(6,7), encoder=U16Adapter()),    # 0x8E 0x8F
            Field('dig_p2', byte_index=(8,9), encoder=S16Adapter()),    # 0x90 0x91
            Field('dig_p3', byte_index=(10,11), encoder=S16Adapter()),    # 0x92 0x93
            Field('dig_p4', byte_index=(12,13), encoder=S16Adapter()),    # 0x94 0x95
            Field('dig_p5', byte_index=(14,15), encoder=S16Adapter()),    # 0x96 0x97
            Field('dig_p6', byte_index=(16,17), encoder=S16Adapter()),    # 0x98 0x99
            Field('dig_p7', byte_index=(18,19), encoder=S16Adapter()),    # 0x9A 0x9B
            Field('dig_p8', byte_index=(20,21), encoder=S16Adapter()),    # 0x9C 0x9D
            Field('dig_p9', byte_index=(22,23), encoder=S16Adapter()),    # 0x9E 0x9F
        ), bit_width=192, read_only=True, volatile=False),
    }

    def __init(self, i2c_device: SMBus , address_pin_level: int = 0):
        self._i2c_dev = i2c_device
        self._address_level = address_pin_level
        self.address = BMP280.i2c_addresses[self._address_level]
