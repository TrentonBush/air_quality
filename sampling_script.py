from smbus2 import SMBus
from time import time, sleep
import psycopg2
import logging
import typer
from dotenv import load_dotenv
import os
import sys

from sensors.bmp280 import BMP280
from sensors.hdc1080 import HDC1080
from sensors.ccs811 import CCS811
from sensors.i2c_base import BaseRegisterAPI

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

load_dotenv()


def main(sample_period_s: int = 60) -> None:
    """periodically measure temp and pressure and write to database

    Args:
        sample_period_s (int, optional): how often to take measurements, in seconds. Defaults to 60.
    """
    # database init
    username = os.getenv("db_username")
    password = os.getenv("db_password")
    connection = f"postgres://{username}:{password}@127.0.0.1:5432/air_quality"

    # sensor init
    i2c_interface = SMBus(1)
    bmp = BMP280(i2c_interface)
    bmp.reset.write()
    bmp.config.write(smoothing_const=1)

    hdc = HDC1080(SMBus(1))  # needs separate SMBus instance due to timing issues
    hdc.config.write(soft_reset=True)

    ccs = CCS811(i2c_interface)
    ccs.reset.write()
    ccs_interval = max([s for s in ccs.meas_mode._periods if s <= sample_period_s])
    ccs.meas_mode.write(sample_period=ccs_interval)

    try:
        while True:
            # Synchronize: start every n seconds, no drift
            sleep(sample_period_s - (time() % sample_period_s))

            # start measurement cycles in order of slowest to fastest
            bmp.ctrl_meas.write(
                pressure_oversampling=16, temperature_oversampling=2, measurement_mode="trigger"
            )
            hdc.data.read()  # 15 ms sleep is built in
            io_safe_retries(ccs.env_data.write, **hdc.data.values)

            # wait for measurements to complete
            remaining = bmp.measurement_duration - hdc.measurement_duration
            # no ccs duration because it constantly measures in the background
            sleep(max(0, remaining))

            # read data
            bmp.status.read()
            while bmp.status.values["measuring"]:
                sleep(0.005)
                bmp.status.read()
            bmp.data.read()

            # occasional clock stretching problems
            io_safe_retries(ccs.data.read)
            io_safe_retries(ccs.raw_data.read)
            io_safe_retries(ccs.baseline.read)

            # log it
            write_to_db(
                connection,
                temp=bmp.data.values["temperature"],
                press=bmp.data.values["pressure"],
                temp_hdc=hdc.data.values["temperature"],
                humidity=hdc.data.values["humidity"],
                eco2=ccs.data.values["eco2"],
                tvoc=ccs.data.values["tvoc"],
                current=ccs.raw_data.values["current_uA"],
                voltage=ccs.raw_data.values["voltage"],
                baseline=ccs.baseline.values["baseline"],
            )

    except KeyboardInterrupt:
        bmp.ctrl_meas.write(measurement_mode="sleep")
        ccs.meas_mode.write(sample_period=0)  # sleep
        exit()


def write_to_db(
    connection: str,
    *,
    temp: float,
    press: float,
    temp_hdc: float,
    humidity: float,
    eco2: int,
    tvoc: int,
    current: int,
    voltage: float,
    baseline: int,
) -> None:
    sql = "INSERT INTO sensor_data(time, temp, press, temp_hdc, humidity, eco2, tvoc, current, voltage, baseline) VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s);"
    data = (temp, press, temp_hdc, humidity, eco2, tvoc, current, voltage, baseline)

    try:
        with psycopg2.connect(connection, connect_timeout=3) as conn:
            with conn.cursor() as curs:
                try:
                    curs.execute(sql, data)
                    conn.commit()
                except psycopg2.Error as error:
                    logger.error("Exception: {}".format(error.pgerror))
                except Exception as error:
                    logger.error("Exception: {}".format(error))
    except psycopg2.OperationalError as error:
        logger.error("Exception: {}".format(error.pgerror))
    finally:
        conn.close()


def io_safe_retries(method, *args, **kwargs):
    try:
        return method(*args, **kwargs)
    except (OSError, IOError) as error:
        logger.error(f"{type(error).__name__}: {error}")
        for _ in range(2):  # retries
            sleep(0.001)
            try:
                return method(*args, **kwargs)
            except (OSError, IOError):
                continue
        reset_cache(method.__self__)  # setting None will become NULL in database


def reset_cache(reg: BaseRegisterAPI) -> None:
    reg._cached = {k: None for k in reg.values.keys()}


if __name__ == "__main__":
    typer.run(main)
