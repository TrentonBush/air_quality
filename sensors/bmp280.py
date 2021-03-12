"""Driver for the Bosch BMP280 pressure sensor"""
from smbus2 import SMBus
from typing import Dict

from .i2c_base import (
    Device,
    Register,
    Field,
    LookupTable,
    BaseDeviceAPI,
    BaseRegisterAPI,
    ReadOnlyRegisterAPI,
    UIntEncoder,
    SIntEncoder,
)


def _apply_calibration(
    raw_adc_values: Dict[str, int], calib_param: Dict[str, int]
) -> Dict[str, float]:
    """convert raw ADC values of temperature and pressure to degrees C and Pascal, respectively.

    Args:
        raw_adc_values (Dict[str, int]): dict of raw ADC values, like: {'temperature': 123456, 'pressure': 123456}
        calib_param (Dict[str, int]): dict of calibration constants, like {'dig_t1': val, ...}

    Returns:
        Dict[str, float]: dict of converted values, like: {'temperature': 20.42, 'pressure': 101325.4}
    """
    uncomp_temp = raw_adc_values["temperature"]
    uncomp_pres = raw_adc_values["pressure"]

    # The following expressions are hard to read - I copied and translated them from Bosch's C implementation.
    # https://github.com/BoschSensortec/BMP280_driver/blob/master/bmp280.c#L553
    # Thankfully they include test values to check that everything works. Trust the tests!

    # temperature compensation
    var1 = (uncomp_temp / 16384 - calib_param["dig_t1"] / 1024) * calib_param["dig_t2"]
    var2 = uncomp_temp / 131072 - calib_param["dig_t1"] / 8192
    var2 = var2 * var2 * calib_param["dig_t3"]
    t_fine = var1 + var2
    temperature = t_fine / 5120

    # pressure compensation
    var1 = t_fine / 2 - 64000
    var2 = var1 * var1 * calib_param["dig_p6"] / 32768
    var2 = var2 + var1 * calib_param["dig_p5"] * 2
    var2 = var2 / 4 + calib_param["dig_p4"] * 65536
    var1 = (calib_param["dig_p3"] * var1 * var1 / 524288 + calib_param["dig_p2"] * var1) / 524288
    var1 = (1 + var1 / 32768) * calib_param["dig_p1"]

    pressure = float(1048576 - uncomp_pres)
    pressure = (pressure - var2 / 4096) * 6250 / var1
    var1 = calib_param["dig_p9"] * pressure * pressure / 2147483648
    var2 = pressure * calib_param["dig_p8"] / 32768
    pressure = pressure + (var1 + var2 + calib_param["dig_p7"]) / 16

    return {"temperature": temperature, "pressure": pressure}


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
                        encoder=LookupTable({1: 0b000, 2: 0b001, 4: 0b010, 8: 0b011, 16: 0b100}),
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

    def __init__(self, i2c_interface: SMBus, address_pin_level: int = 0):
        super().__init__(i2c_interface, address_pin_level)
        self.reset = ResetAPI(self, "reset")
        self.ctrl_meas = CtrlMeasAPI(self, "ctrl_meas")
        self.config = ConfigAPI(self, "config")
        # read-only registers
        self.chip_id = ReadOnlyRegisterAPI(self, "chip_id")
        self.status = ReadOnlyRegisterAPI(self, "status")
        self.calibration = ReadOnlyRegisterAPI(self, "calibration")
        self.data = DataAPI(self, "data")


class ResetAPI:
    """reset register API

    Differs from other registers:
     * write only
     * no values to cache, so no self._cached or self.values attributes"""

    def __init__(self, parent_device: BMP280, reg_name: str):
        self._parent_device = parent_device
        self._reg = self._parent_device.hardware.registers[reg_name]

    def read(self):
        """reset register is write only"""
        raise AttributeError("The 'reset' register is write only")

    def write(self):
        """Send the soft reset signal.

        Resets the logic circuity and the register values. Sensor then enters sleep mode.
        """
        field_map = {"reset": 0xB6}
        encoded = self._reg._field_values_to_raw_bytes(field_map)
        self._parent_device._i2c_write(self._reg, encoded)


class DataAPI(ReadOnlyRegisterAPI):
    """data register API

    Differs from other registers:
     * read only
     * overwrite .read method to apply calibration (same signature and return value)
    """

    # This subclass exists because calibration doesn't fit the standard Encoder model.
    # Calibration relies on other register values. Encoders have no concept of other registers.
    # I made an Encoder that worked (loaded it with calibration constants during sensor setup),
    # but it relied on the order in which fields were defined (temp had to be defined before pressure).
    # That felt too brittle/obscure, hence this class.
    def read(self, ignore_cache=False) -> None:
        """read current values and apply sensor calibration"""
        super().read()  # temporarily set self._cached with machine-readable values
        self._parent_device.calibration.read(ignore_cache=ignore_cache)  # type: ignore
        calib = self._parent_device.calibration._cached  # type: ignore
        field_values = _apply_calibration(self._cached, calib)  # convert to human-readable
        self._cached = field_values


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

        field_map = {
            "osrs_t": temperature_oversampling,
            "osrs_p": pressure_oversampling,
            "mode": mode_map[measurement_mode],
        }
        self._cached.update(field_map)
        encoded = self._reg._field_values_to_raw_bytes(field_map)
        self._parent_device._i2c_write(self._reg, encoded)


class ConfigAPI(BaseRegisterAPI):
    """config register API"""

    _periods = {0.5, 62.5, 125, 250, 500, 1000, 2000, 4000}
    _filter_constants = {1, 2, 4, 8, 16}

    def write(self, measurement_period_ms=4000, smoothing_const=1, disable_I2C=False):
        """configure the sampling rate, filter, and interface options.
        NOTE: writes to the config register may be ignored during measurements. Set to sleep mode (via ctrl_meas register) to guarantee successful writes.

        measurement_period_ms does not include measurement time; a 500ms period does not sample at exactly 2 Hz.
        To get total time per measurement, add approximately 1.5 ms plus 2 ms for each oversample;
        eg. 8x pressure and 2x temp = 10 samples * 2ms per sample = 20 ms + 1.5 = 21.5 ms + measurement_period_ms

        smoothing_const adjusts the weight of an IIR filter (expanding exponentially weighted moving average)
        of the previous data acquisitions. smoothing_const=1 means no smoothing is applied.
        It should probably only be used with the constant interval measurement mode.
        The formula is:
        output = (previous_value * (smoothing_const - 1) + new_value) / smoothing_const
        The weight of the point at t-n is (1/const) * ((const - 1) / const)^n
        To decay to a 2% weight, const=2 requires 4.6 samples, whereas const=16 requires 17.6

        Args:
            measurement_period_ms (int, optional): milliseconds between measurements in interval sampling mode. Possible values are [0.5, 62.5, 125, 250, 500, 1000, 2000, 4000]. For longer sampling intervals, set measurement_mode='trigger' in the ctrl_meas register. Defaults to 4000.
            smoothing_const (int, optional): Smoothing filter (IIR) coefficient. Higher -> smoother. Possible values are [0, 2, 4, 8, 16]. Defaults to 1.
            disable_I2C (bool, optional): Enable 3-wire SPI interface, which disables I2C and means this codebase won't work. Defaults to False.
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
        self._cached.update(field_map)
        encoded = self._reg._field_values_to_raw_bytes(field_map)
        self._parent_device._i2c_write(self._reg, encoded)
