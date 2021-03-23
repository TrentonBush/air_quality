"""Driver for CCS811 VOC sensor"""
from smbus2 import SMBus
from typing import Dict
from time import sleep

from .i2c_base import (
    Device,
    Encoder,
    Register,
    Field,
    LookupTable,
    BaseDeviceAPI,
    BaseRegisterAPI,
    ReadOnlyRegisterAPI,
)


class HumidityFixedPoint(Encoder):
    def encode(self, value: float, field: Field) -> bytes:
        val = int(round(value * 512))
        n_bytes = field.byte_index[-1] - field.byte_index[0] + 1
        return val.to_bytes(n_bytes, field.byte_order)

    def decode(self, value: bytes, field: Field) -> float:
        return int.from_bytes(value, field.byte_order) / 512


class TemperatureFixedPoint(Encoder):
    def encode(self, value: float, field: Field) -> bytes:
        val = int(round((value + 25) * 512))
        n_bytes = field.byte_index[-1] - field.byte_index[0] + 1
        return val.to_bytes(n_bytes, field.byte_order)

    def decode(self, value: bytes, field: Field) -> float:
        return int.from_bytes(value, field.byte_order) / 512 - 25


class CCS811(BaseDeviceAPI):
    """API for ScioSense CCS811B eTVOC and eCO2 sensor"""

    hardware = Device(
        "ccs811",
        chip_id=0x81,
        i2c_addresses={0: 0x5A, 1: 0x5B},
        registers=(
            Register(
                "status",
                address=0x00,
                fields=(
                    Field("app_on", bit_mask=0b10000000),
                    Field("app_erase", bit_mask=0b01000000),
                    Field("app_verify", bit_mask=0b00100000),
                    Field("app_valid", bit_mask=0b00010000),
                    Field("data_ready", bit_mask=0b00001000),
                    Field("error", bit_mask=1, read_only=True),
                ),
                read_only=True,
            ),
            Register(
                "meas_mode",
                address=0x01,
                fields=(
                    Field(
                        "sample_period",
                        bit_mask=0b01110000,
                        encoder=LookupTable(
                            {0: 0, 1: 1, 10: 0b010, 60: 0b011, 0.25: 0b100}
                        ),
                    ),
                    Field("interrupts_on", bit_mask=0b00001000),
                    Field("interrupt_on_thresh", bit_mask=0b00000100),
                ),
            ),
            Register(
                "data",
                address=0x02,
                fields=(
                    Field("co2", byte_index=(0, 1)),
                    Field("tvoc", byte_index=(2, 3)),
                ),
                read_only=True,
                n_bits=32,
            ),
            Register(
                "raw_data",
                address=0x03,
                fields=(
                    Field("current", bit_mask=0b11111100),
                    Field("voltage", byte_index=(0, 1), bit_mask=0x03FF),
                ),
                n_bits=16,
            ),
            Register(
                "env_data",
                address=0x05,
                fields=(
                    Field("humidity", byte_index=(0, 1), encoder=HumidityFixedPoint()),
                    Field(
                        "temperature",
                        byte_index=(2, 3),
                        encoder=TemperatureFixedPoint(),
                    ),
                ),
                n_bits=32,
            ),
            Register(
                "baseline",
                address=0x11,
                fields=(Field("baseline", byte_index=(0, 1)),),
                n_bits=16,
            ),
            Register(
                "chip_id",
                address=0x20,
                fields=(Field("chip_id"),),
                read_only=True,
                non_volatile=True,
            ),
            Register(
                "error_id",
                address=0xE0,
                fields=(
                    Field("invalid_write", bit_mask=0b10000000),
                    Field("invalid_read", bit_mask=0b01000000),
                    Field("invalid_mode", bit_mask=0b00100000),
                    Field("max_resistance", bit_mask=0b00010000),
                    Field("heater_fault", bit_mask=0b00001000),
                    Field("heater_supply", bit_mask=0b00000100),
                ),
                read_only=True,
            ),
            Register(
                "reset",
                address=0xFF,
                fields=(Field("reset", byte_index=(0, 1, 2, 3)),),
                n_bits=32,
            ),
        ),
    )

    def _start_device(self) -> None:
        self.status.read()
        if not self.status.values['app_valid']:
            raise Exception("CCS811 application not valid")
        self._i2c.write_byte(self.address, 0xF4)