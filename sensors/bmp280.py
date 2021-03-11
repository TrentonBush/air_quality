"""Driver for the Bosch BMP280 pressure sensor"""
from smbus2 import SMBus

from .i2c_base import (
    Device,
    Register,
    Field,
    Encoder,
    LookupTable,
    BaseDeviceAPI,
    BaseRegisterAPI,
    UIntEncoder,
    SIntEncoder,
)


class BMP280(BaseDeviceAPI):
    hardware = Device(
        "bmp280",
        chip_id=0x58,
        i2c_addresses={0: 0x76, 1: 0x77},  # address pin logic level 0, 1 (GND, VCC)
        registers=(
            Register("chip_id", 0xD0, fields=[Field("id")], read_only=True, non_volatile=True),
            Register("reset", 0xE0, fields=[Field("reset")]),
            Register(
                "status",
                0xF3,
                fields=[
                    Field("measuring", bit_mask=0b00001000),  # 1 when conversion is running
                    Field("im_update", bit_mask=0b00000001),  # 1 when NVM data is being copied
                ],
                read_only=True,
            ),
            Register(
                "ctrl_meas",
                0xF4,
                fields=[
                    Field(
                        "osrs_t",
                        bit_mask=0b11100000,  # Temperature oversampling
                        encoder=LookupTable(
                            {0: 0b000, 1: 0b001, 2: 0b010, 4: 0b011, 8: 0b100, 16: 0b101}
                        ),
                    ),
                    Field(
                        "osrs_p",
                        bit_mask=0b00011100,  # Pressure oversampling
                        encoder=LookupTable(
                            {0: 0b000, 1: 0b001, 2: 0b010, 4: 0b011, 8: 0b100, 16: 0b101}
                        ),
                    ),
                    Field(
                        "mode",
                        bit_mask=0b00000011,  # Power mode
                        encoder=LookupTable({"sleep": 0b00, "forced": 0b10, "normal": 0b11}),
                    ),
                ],
            ),
            Register(
                "config",
                0xF5,
                fields=[
                    Field(
                        "t_sb",  # Temp standby duration in 'normal' power mode
                        bit_mask=0b11100000,
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
                    Field(
                        "filter",  # time constant of the IIR filter
                        bit_mask=0b00011100,
                        encoder=LookupTable({0: 0b000, 2: 0b001, 4: 0b010, 8: 0b011, 16: 0b100}),
                    ),
                    Field("spi3w_en", bit_mask=0b0000001),  # Enable 3-wire SPI interface
                ],
            ),
            Register(
                "data",
                0xF7,
                fields=[
                    Field("temperature", byte_index=(3, 5), bit_mask=0xFFFFF0),
                    Field("pressure", byte_index=(0, 2), bit_mask=0xFFFFF0),
                ],
                n_bits=48,
                read_only=True,
            ),
            Register(
                "calibration",
                0x88,
                fields=[
                    Field("dig_t1", byte_index=(0, 1), encoder=UIntEncoder()),  # 0x88 0x89
                    Field("dig_t2", byte_index=(2, 3), encoder=SIntEncoder()),  # 0x8A 0x8B
                    Field("dig_t3", byte_index=(4, 5), encoder=SIntEncoder()),  # 0x8C 0x8D
                    Field("dig_p1", byte_index=(6, 7), encoder=UIntEncoder()),  # 0x8E 0x8F
                    Field("dig_p2", byte_index=(8, 9), encoder=SIntEncoder()),  # 0x90 0x91
                    Field("dig_p3", byte_index=(10, 11), encoder=SIntEncoder()),  # 0x92 0x93
                    Field("dig_p4", byte_index=(12, 13), encoder=SIntEncoder()),  # 0x94 0x95
                    Field("dig_p5", byte_index=(14, 15), encoder=SIntEncoder()),  # 0x96 0x97
                    Field("dig_p6", byte_index=(16, 17), encoder=SIntEncoder()),  # 0x98 0x99
                    Field("dig_p7", byte_index=(18, 19), encoder=SIntEncoder()),  # 0x9A 0x9B
                    Field("dig_p8", byte_index=(20, 21), encoder=SIntEncoder()),  # 0x9C 0x9D
                    Field("dig_p9", byte_index=(22, 23), encoder=SIntEncoder()),  # 0x9E 0x9F
                ],
                n_bits=192,
                read_only=True,
                non_volatile=True,
            ),
        ),
    )

    def __init(self, i2c_interface: SMBus, address_pin_level: int = 0):
        super().__init__(i2c_interface, address_pin_level)
        self.chip_id = ChipIDAPI(self, "chip_id")
        self.reset = ResetAPI(self, "reset")
        self.status = StatusAPI(self, "status")
        self.ctrl_meas = CtrlMeasAPI(self, "ctrl_meas")
        self.config = ConfigAPI(self, "config")
        self.data = DataAPI(self, "data")
        self.calibration = CalibrationAPI(self, "calibration")


class ChipIDAPI(BaseRegisterAPI):
    """chip_id register API"""

    def write(self):
        """chip_id is read only"""
        raise AttributeError("chip_id is read only")


class ResetAPI(BaseRegisterAPI):
    """reset register API"""

    def write(self):
        """Send the soft reset signal.

        Resets the logic circuity and the register values. Sensor then enters sleep mode.
        """
        field_map = {"reset": 0xB6}
        encoded = self._reg._field_values_to_raw_bytes(field_map)
        self._parent_device._i2c_write(self._reg, encoded)


class StatusAPI(BaseRegisterAPI):
    """status register API"""

    def write(self):
        """status register is read only"""
        raise AttributeError("status register is read only")


class CtrlMeasAPI(BaseRegisterAPI):
    """ctrl_meas register API"""

    _modes = {"trigger", "interval", "sleep"}
    _oversampling_values = {0, 1, 2, 4, 8, 16}

    def write(
        self, pressure_oversampling=16, temperature_oversampling=2, measurement_mode="trigger"
    ):
        """set data acquisition options

        Per the datasheet:
        Select pressure oversampling based on your desired resolution: 1x = 2.62 Pa, 2x = 1.31, 4x = 0.66, 8x = 0.33, 16x = 0.16
        Temperature oversampling can be left at 1x unless you use 16x pressure oversampling, in which case use 2x. Any further temperature oversampling does NOT provide any benefit to pressure resolution.
        Setting temperature or pressure oversampling to 0x skips that measurement. Output will be set to 0x80000

        Measurement modes are:
            sleep: take no measurements, reduce power consumption to minimum
            trigger: take a measurement only when prompted by the host (by writing to this register), then go into sleep mode.
            interval: take measurements every n milliseconds. Set n using the 'measurement_period_ms' arg of the config register.

        Args:
            pressure_oversampling (int, optional): number of pressure measurements to aggregate. Possible values are [0, 1, 2, 4, 8, 16]. Defaults to 16.
            temperature_oversampling (int, optional): number of temperature measurements to aggregate. Possible values are [0, 1, 2, 4, 8, 16]. Defaults to 2.
            measurement_mode (str, optional): one of ['trigger', 'interval', 'sleep']. See above documentation for descriptions. Defaults to 'trigger'.
        """

        if measurement_mode not in CtrlMeasAPI._modes:
            raise ValueError(
                f"measurement_mode must be one of {str(CtrlMeasAPI._modes)}. Given {measurement_mode}"
            )
        if pressure_oversampling not in CtrlMeasAPI._oversampling_values:
            raise ValueError(
                f"pressure_oversampling must be one of {str(CtrlMeasAPI._oversampling_values)}. Given {pressure_oversampling}"
            )
        if temperature_oversampling not in CtrlMeasAPI._oversampling_values:
            raise ValueError(
                f"temperature_oversampling must be one of {str(CtrlMeasAPI._oversampling_values)}. Given {temperature_oversampling}"
            )

        mode_map = {"trigger": "forced", "interval": "normal", "sleep": "sleep"}
        measurement_mode = mode_map[measurement_mode]

        field_map = {
            "osrs_t": temperature_oversampling,
            "osrs_p": pressure_oversampling,
            "mode": measurement_mode,
        }
        encoded = self._reg._field_values_to_raw_bytes(field_map)
        self._parent_device._i2c_write(self._reg, encoded)


class ConfigAPI(BaseRegisterAPI):
    """config register API"""

    _periods = {0.5, 62.5, 125, 250, 500, 1000, 2000, 4000}
    _filter_constants = {0, 2, 4, 8, 16}

    def write(self, measurement_period_ms=4000, smoothing_const=8, disable_I2C=False):
        """configure the sampling rate, filter, and interface options.
        NOTE: writes to the config register may be ignored during measurements. Set to sleep mode (via ctrl_meas register) to guarantee successful writes.

        Args:
            measurement_period_ms (int, optional): milliseconds between measurements in interval sampling mode. Possible values are [0.5, 62.5, 125, 250, 500, 1000, 2000, 4000]. Defaults to 4000.
            smoothing_const (int, optional): Smoothing filter (IIR) coefficient. Higher -> smoother. Possible values are [0, 2, 4, 8, 16]. Defaults to 8.
            disable_I2C (bool, optional): Enable SPI interface, which disables I2C and means this codebase won't work. Defaults to False.
        """
        if measurement_period_ms not in ConfigAPI._periods:
            raise ValueError(
                f"measurement_period_ms must be one of {str(ConfigAPI._periods)}. Given {measurement_period_ms}"
            )
        if smoothing_const not in ConfigAPI._filter_constants:
            raise ValueError(
                f"smoothing_const must be one of {str(ConfigAPI._filter_constants)}. Given {smoothing_const}"
            )

        field_map = {
            "t_sb": measurement_period_ms,
            "filter": smoothing_const,
            "spi3w_en": disable_I2C,
        }
        encoded = self._reg._field_values_to_raw_bytes(field_map)
        self._parent_device._i2c_write(self._reg, encoded)


class DataAPI(BaseRegisterAPI):
    """data register API"""

    def write(self):
        """data register is read only"""
        raise AttributeError("data register is read only")


class CalibrationAPI(BaseRegisterAPI):
    """calibration register API"""

    def write(self):
        """calibration register is read only"""
        raise AttributeError("calibration register is read only")


# TODO: implement cache updating for all RegisterAPI.write() methods
