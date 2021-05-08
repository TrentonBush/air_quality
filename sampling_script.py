from smbus2 import SMBus
from time import time, sleep
import psycopg2
import logging
import typer
from dotenv import load_dotenv
from typing import Union
import os
import sys

from drivers.bmp280 import BMP280
from drivers.hdc1080 import HDC1080
from drivers.ccs811 import CCS811
from drivers.i2c_base import BaseRegisterAPI
from drivers.s8 import SenseairS8, make_s8_serial_connection
from drivers.pms7003 import PMS7003, make_pms7003_serial_connection

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
    # ccs.reset.write() # resets baseline, which is annoying
    ccs_interval = max([s for s in ccs.meas_mode._periods if s <= sample_period_s])
    ccs.meas_mode.write(sample_period=ccs_interval)

    s8_serial = make_s8_serial_connection("/dev/ttyAMA0")
    s8 = SenseairS8(s8_serial)

    pms7003_serial = make_pms7003_serial_connection("/dev/ttyAMA1")
    pms7003 = PMS7003(pms7003_serial)

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
            io_safe_retries(bmp.data.read)

            # occasional clock stretching problems on this sensor
            io_safe_retries(ccs.data.read)
            io_safe_retries(ccs.raw_data.read)
            io_safe_retries(ccs.baseline.read)

            io_safe_retries(s8.read_co2)
            io_safe_retries(pms7003.read)

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
                co2=s8.values["co2"],
                **pms7003.data_values,
            )

    finally:
        bmp.ctrl_meas.write(measurement_mode="sleep")
        ccs.meas_mode.write(sample_period=0)  # sleep
        pms7003.sleep()
        # hdc1080 doesn't need a sleep mode, s8 doesn't have one


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
    co2: int,
    pm1_0: int,
    pm2_5: int,
    pm10_0: int,
    pm1_0_atm: int,
    pm2_5_atm: int,
    pm10_0_atm: int,
    count_0_3: int,
    count_0_5: int,
    count_1_0: int,
    count_2_5: int,
    count_5_0: int,
    count_10_0: int,
) -> None:
    sql = "INSERT INTO sensor_data(ts, temp, press, temp_hdc, humidity, eco2, tvoc, current, voltage, baseline, co2, pm1_0, pm2_5, pm10_0, pm1_0_atm, pm2_5_atm, pm10_0_atm, count_0_3, count_0_5, count_1_0, count_2_5, count_5_0, count_10_0) VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"
    data = (
        temp,
        press,
        temp_hdc,
        humidity,
        eco2,
        tvoc,
        current,
        voltage,
        baseline,
        co2,
        pm1_0,
        pm2_5,
        pm10_0,
        pm1_0_atm,
        pm2_5_atm,
        pm10_0_atm,
        count_0_3,
        count_0_5,
        count_1_0,
        count_2_5,
        count_5_0,
        count_10_0,
    )

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


def reset_cache(reg: Union[BaseRegisterAPI, PMS7003, SenseairS8]) -> None:
    reg._cached = {k: None for k in reg.values.keys()}


if __name__ == "__main__":
    typer.run(main)
