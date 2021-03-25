"""Driver for CCS811 VOC sensor"""
from smbus2 import SMBus
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
        val = max(val, 0)  # threshold at -25 °C
        n_bytes = field.byte_index[-1] - field.byte_index[0] + 1
        return val.to_bytes(n_bytes, field.byte_order)

    def decode(self, value: bytes, field: Field) -> float:
        return int.from_bytes(value, field.byte_order) / 512 - 25


class VoltageEncoder(Encoder):
    def encode(self, value, field):
        raise AttributeError("raw data is read only")

    def decode(self, value: bytes, field: Field) -> float:
        # simple scaler where maxint == 1023 == 1.65 V
        val = int.from_bytes(value, field.byte_order)
        return float(val) / 1023 * 1.65


class CCS811(BaseDeviceAPI):
    """API for ScioSense CCS811B eTVOC and eCO2 sensor"""

    # NOTE: this class does not implement all registers. There is additional
    # functionality for setting threshold values for alarm interrupts
    # and for flashing new firmware.
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
                        encoder=LookupTable({0: 0, 1: 1, 10: 0b010, 60: 0b011, 0.25: 0b100}),
                    ),
                    Field("enable_interrupt", bit_mask=0b00001000),
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
                    Field("current_uA", bit_mask=0b11111100),
                    Field("voltage", byte_index=(0, 1), bit_mask=0x03FF, encoder=VoltageEncoder()),
                ),
                n_bits=16,
                read_only=True,
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

    def __init__(self, i2c_interface: SMBus, address_pin_level: int):
        super().__init__(i2c_interface, address_pin_level=address_pin_level)

        self.reset = ResetAPI(self, "reset")
        self.env_data = EnvDataAPI(self, "env_data")
        self.meas_mode = MeasModeAPI(self, "meas_mode")
        # read only
        self.error_id = ReadOnlyRegisterAPI(self, "error_id")
        self.chip_id = ReadOnlyRegisterAPI(self, "chip_id")
        self.status = ReadOnlyRegisterAPI(self, "status")
        self.raw_data = ReadOnlyRegisterAPI(self, "raw_data")
        self.data = ReadOnlyRegisterAPI(self, "data")
        # not read only but setting baseline manually is not implemented
        self.baseline = ReadOnlyRegisterAPI(self, "baseline")
        self._start_device()

    def _start_device(self) -> None:
        self.status.read()
        if not self.status.values["app_valid"]:
            raise Exception("CCS811 application not valid")
        self._i2c.write_byte(self.address, 0xF4)  # boot command
        sleep(0.001)  # 1 ms startup time


class ResetAPI:
    """reset register API

    Differs from other registers:
     * write only
     * no values to cache, so no self._cached or self.values attributes"""

    def __init__(self, parent_device: CCS811, reg_name: str):
        self._parent_device = parent_device
        self._reg = self._parent_device.hardware.registers[reg_name]

    def read(self):
        """reset register is write only"""
        raise AttributeError("The 'reset' register is write only")

    def write(self, app_start=True):
        """Send the soft reset signal, with the option to restart the app (default) or stay in boot mode.

        Boot mode is used to flash new firmware.

        Args:
            app_start (bool, optional): start the measurement app or stay in boot mode. Defaults to True.
        """
        field_map = {"reset": 0x11E5728A}
        encoded = self._reg._field_values_to_raw_bytes(field_map)
        self._parent_device._i2c_write(self._reg, encoded)
        sleep(0.002)  # 2 ms startup time
        if app_start:
            self._parent_device._start_device()


class EnvDataAPI(BaseRegisterAPI):
    """env_data register API"""

    def write(self, temperature=25.0, humidity=50.0) -> None:
        """write environmental data from an external temperature and humidity sensor

        Args:
            temperature (float, optional): temperature in degrees C. Defaults to 25.0.
            humidity (float, optional): humidity in %RH. Defaults to 50.0.
        """
        field_map = {"temperature": temperature, "humidity": humidity}
        self._cached = field_map
        encoded = self._reg._field_values_to_raw_bytes(self._cached)
        self._parent_device._i2c_write(self._reg, encoded)


class MeasModeAPI(BaseRegisterAPI):
    """meas_mode register API"""

    _periods = {0, 0.25, 1, 10, 60}

    # def write(self, sample_period=60, enable_interrupt=False, interrupt_on_thresh=False) -> None:
    def write(self, sample_period=60) -> None:
        """choose measurement mode settings.

        This register also has fields relating to interrupts, but that capability is not implemented.

        Args:
            sample_period (int, optional): sample period in seconds. Must be in {0, 0.25, 1, 10, 60}. Defaults to 60.

        Raises:
            ValueError: if given sample_period is not in allow set of values
        """
        if sample_period not in MeasModeAPI._periods:
            raise ValueError(
                f"Given sample_period must be in {MeasModeAPI._periods}. Given {sample_period}"
            )
        field_map = {
            "sample_period": sample_period,
            "enable_interrupt": False,  # not implemented
            "interrupt_on_thresh": False,  # not implemented
        }
        self._cached = field_map
        encoded = self._reg._field_values_to_raw_bytes(self._cached)
        self._parent_device._i2c_write(self._reg, encoded)
