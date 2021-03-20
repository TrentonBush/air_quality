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

    try:
        while True:
            # Synchronize: start every n seconds, no drift
            sleep(sample_period_s - (time() % sample_period_s))

            # start measurement cycles in order of slowest to fastest
            bmp.ctrl_meas.write(
                pressure_oversampling=16, temperature_oversampling=2, measurement_mode="trigger"
            )
            hdc.data.read()  # 15 ms sleep is built in

            # wait for measurements to complete
            remaining = bmp.measurement_duration - hdc.measurement_duration
            sleep(max(0, remaining))

            # read data
            bmp.status.read()
            while bmp.status.values["measuring"]:
                sleep(0.005)
                bmp.status.read()
            bmp.data.read()

            # log it
            write_to_db(
                connection,
                temp=bmp.data.values["temperature"],
                press=bmp.data.values["pressure"],
                temp_hdc=hdc.data.values["temperature"],
                humidity=hdc.data.values["humidity"],
            )

    except KeyboardInterrupt:
        bmp.ctrl_meas.write(measurement_mode="sleep")
        exit()


def write_to_db(
    connection: str, *, temp: float, press: float, temp_hdc: float, humidity: float
) -> None:
    sql = "INSERT INTO sensor_data(time, temp, press, temp_hdc, humidity) VALUES (NOW(), %s, %s, %s, %s);"
    data = (temp, press, temp_hdc, humidity)

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


if __name__ == "__main__":
    typer.run(main)
