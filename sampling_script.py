from smbus2 import SMBus
from pathlib import Path
from time import sleep
from datetime import datetime

from sensors.bmp280 import BMP280


i2c_path = Path("dev/iotty03")
assert i2c_path.exists()

i2c_interface = SMBus(str(i2c_path))
bmp = BMP280(i2c_interface)

# config
bmp.chip_id.read()
bmp.calibration.read()
bmp.ctrl_meas.write(measurement_mode="interval")

# sample
while True:
    start = datetime.now()
    bmp.data.read()
    end = datetime.now()
    out = f"Temp [°C]: {bmp.data.values['temperature']:.4f}\t\t Press [Pa]: {bmp.data.values['pressure']:.3f}\t\t Duration [ms]: {((end - start).total_seconds() / 1000):.2f}"
    print(out)
    sleep(4.1)
