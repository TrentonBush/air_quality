from smbus2 import SMBus
from pathlib import Path
from time import sleep
from datetime import datetime

from sensors.bmp280 import BMP280


i2c_path = Path("/dev/i2c-1")
assert i2c_path.exists()

i2c_interface = SMBus(str(i2c_path))
bmp = BMP280(i2c_interface)

# config
bmp.reset.write()
bmp.config.write(measurement_period_ms=1000, smoothing_const=2, disable_I2C=False)
bmp.ctrl_meas.write(
    pressure_oversampling=16, temperature_oversampling=2, measurement_mode="trigger"
)

# sample
while True:
    start = datetime.now()
    bmp.ctrl_meas.write(
        pressure_oversampling=16, temperature_oversampling=2, measurement_mode="trigger"
    )
    bmp.status.read()
    while bmp.status.values["measuring"]:
        bmp.status.read()
        sleep(0.001)
    end = datetime.now()
    bmp.data.read()
    out = f"Temp [°C]: {bmp.data.values['temperature']:.4f} \t Press [Pa]: {bmp.data.values['pressure']:.3f} \t Duration [ms]: {(end - start).total_seconds() * 1000}"
    print(out)
    sleep(1.1)
