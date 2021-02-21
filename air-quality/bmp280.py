"""Driver for the Bosch BMP280 pressure sensor"""
from smbus2 import SMBus

class BMP280(object):
    chip_id = 0x58
    i2c_addresses = (0x76, 0x77) # address pin logic level 0, 1 (GND, VCC)
    endianness = 'big'

    def __init(self, i2c_device: SMBus , address_logic_level: int = 0):
        self._i2c_dev = i2c_device
        self._address_level = address_level
        self.address = BMP280.i2c_addresses[self._address_level]
