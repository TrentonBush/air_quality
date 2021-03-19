"""Driver for Texas Instruments HDC1080 temperature and humidity sensor"""
from smbus2 import SMBus
from time import sleep

from .i2c_base import (
    Device,
    Register,
    Field,
    LookupTable,
    BaseDeviceAPI,
    Encoder,
    BaseRegisterAPI,
    ReadOnlyRegisterAPI,
)


class TemperatureEncoder(Encoder):
    def encode(self, value: float, field: Field):
        raise AttributeError("temperature is read only")

    def decode(self, value: bytes, field: Field):
        num = int.from_bytes(value, field.byte_order)
        return num * 165 / 2 ** 16 - 40


class HumidityEncoder(Encoder):
    def encode(self, value: float, field: Field):
        raise AttributeError("humidity is read only")

    def decode(self, value: bytes, field: Field):
        num = int.from_bytes(value, field.byte_order)
        return num * 100 / 2 ** 16


class HDC1080(BaseDeviceAPI):
    """API for Texas Instruments HDC1080 humidity/temperature sensor"""

    hardware = Device(
        "hdc1080",
        chip_id=0x1050,
        i2c_addresses={0: 0x40, 1: 0x40},  # only one address
        registers=(
            Register(
                "device_id",
                0xFF,
                fields=(Field("device_id", byte_index=(0, 1)),),
                n_bits=16,
                read_only=True,
                non_volatile=True,
            ),
            Register(
                "manufacturer_id",
                0xFE,
                fields=(Field("manufacturer_id", byte_index=(0, 1)),),
                n_bits=16,
                read_only=True,
                non_volatile=True,
            ),
            Register(
                "serial_id",
                0xFB,
                fields=(Field("serial_id", byte_index=tuple(range(5))),),
                n_bits=48,
                read_only=True,
                non_volatile=True,
            ),
            Register(
                "config",
                0x02,
                fields=(
                    Field("reset", bit_mask=0b10000000),
                    Field("heater_on", bit_mask=0b00100000),
                    Field("mode", bit_mask=0b00010000),
                    Field("battery_low", bit_mask=0b00001000, read_only=True),
                    Field(
                        "temp_res_bits",
                        bit_mask=0b00000100,
                        encoder=LookupTable(
                            {
                                14: 0,
                                11: 1,
                            }
                        ),
                    ),
                    Field(
                        "rh_res_bits",
                        bit_mask=0b00000011,
                        encoder=LookupTable(
                            {
                                14: 0b00,
                                11: 0b01,
                                8: 0b10,
                            }
                        ),
                    ),
                    Field("reserved", byte_index=(1,), bit_mask=0),  # second byte must be null
                ),
                n_bits=16,
            ),
            Register(
                "humidity",
                0x01,
                fields=(Field("humidity", byte_index=(0, 1), encoder=HumidityEncoder()),),
                n_bits=16,
            ),
            Register(
                "temp",
                0x00,
                fields=(Field("temp", byte_index=(0, 1), encoder=TemperatureEncoder()),),
                n_bits=16,
            ),
            # HDC1080 can measure only temp, only RH, or both at once.
            # The i2c_base framework requires different Register objects for those options
            Register(
                "data",
                0x00,
                fields=(
                    Field("temp", byte_index=(0, 1), encoder=TemperatureEncoder()),
                    Field("humidity", byte_index=(2, 3), encoder=HumidityEncoder()),
                ),
                n_bits=32,
            ),
        ),
        word_size=16,
    )

    def __init__(self, i2c_interface: SMBus, address_pin_level: int = 0):
        super().__init__(i2c_interface, address_pin_level)
        self._timings = {"temp": {14: 6.35, 11: 3.65}, "humidity": {14: 6.35, 11: 3.65, 8: 2.5}}
        self.config = ConfigAPI(self, "config")
        # read only registers
        self.data = ReadOnlyRegisterAPI(self, "data")
        self.humidity = ReadOnlyRegisterAPI(self, "humidity")
        self.temperature = ReadOnlyRegisterAPI(self, "temperature")
        self.serial_id = ReadOnlyRegisterAPI(self, "serial_id")
        self.manufacturer_id = ReadOnlyRegisterAPI(self, "manufacturer_id")
        self.device_id = ReadOnlyRegisterAPI(self, "device_id")

    @property
    def measurement_duration(self) -> float:
        """calculate measurement duration, per datasheet. Used for sleep timing.

        Returns:
            float: duration, in seconds
        """
        t_ms = self._timings["temp"][self.config.values["temp_res_bits"]]
        rh_ms = self._timings["humidity"][self.config.values["rh_res_bits"]]
        if self.config.values["mode"]:  # measure both temp and RH
            return (t_ms + rh_ms) / 1000 + 0.001
        return max(t_ms, rh_ms) / 1000 + 0.001

    def trigger_measurement(self, temperature=True, humidity=True) -> None:
        """begin a measurement based on current config values

        Args:
            temperature (bool, optional): whether to measure temperature. Defaults to True.
            humidity (bool, optional): whether to measure humidity. Defaults to True.
        """
        if humidity and not temperature:
            reg_addr = self.hardware.registers["humidity"].address
        else:
            reg_addr = self.hardware.registers["temp"].address
        self._i2c.write_byte(self.address, reg_addr)
        sleep(self.measurement_duration)


class ConfigAPI(BaseRegisterAPI):
    """API for config register"""

    _resolutions = (8, 11, 14)

    def write(
        self,
        soft_reset=False,
        heater_on=False,
        temp_resolution_bits=14,
        humidity_resolution_bits=14,
        measure_both=True,
    ) -> None:
        """configure the hdc1080

        Measurement Resolution
        HDC1080 can measure temperature and humidity with variable resolution.
        These correspond to the following approximate decimal precision:
            temperature:
                11 bits -> 0.08 °C
                14 bits -> 0.01 °C
            humidity:
                8 bits -> 0.4 %RH
                11 bits -> 0.05 %RH
                14 bits -> 0.006 %RH

        Measurement Modes
        The HDC1080 can measure temperature and humidity independently or simultaneously.

        For simultaneous measurements, set 'measure_both' to True (default).
        call device.trigger_measurements() with default args
        read with device.data.read()
        access at device.data.values

        To take independent measurements, set 'measure_both' to False.
        Then use the device.trigger_measurement(temp: bool, humidity: bool) method to select which to measure.
        Finally, read the measurements with either device.humidity.read() or device.temperature.read()
        Access data at either device.humidity.values or device.temperature.values

        Args:
            soft_reset (bool, optional): reset the device. Defaults to False.
            heater_on (bool, optional): turn on the heater. Used to drive off condensation. Defaults to False.
            temp_resolution_bits (int, optional): Select the resolution (11 or 14 bits) of the temperature measurements. Defaults to 14.
            humidity_resolution_bits (int, optional): Select the resolution (8, 11 or 14 bits) of the humidity measurements. Defaults to 14.
            measure_both (bool, optional): measure both temp and humidity simultaneously. Defaults to True.
        """
        if temp_resolution_bits not in ConfigAPI._resolutions[1:]:
            raise ValueError(
                f"temp_resolution_bits must be one of {str(ConfigAPI._resolutions[1:])}. Given {measurement_period_ms}"
            )
        if humidity_resolution_bits not in ConfigAPI._resolutions:
            raise ValueError(
                f"humidity_resolution_bits must be one of {str(ConfigAPI._resolutions)}. Given {smoothing_const}"
            )
        field_map = {
            "reset": soft_reset,
            "heater_on": heater_on,
            "temp_res_bits": temp_resolution_bits,
            "rh_res_bits": humidity_resolution_bits,
            "mode": measure_both,
        }
        self._cached.update(field_map)
        encoded = self._reg._field_values_to_raw_bytes(self._cached)
        self._parent_device._i2c_write(self._reg, encoded)
        if soft_reset:
            sleep(0.015)
