from smbus2 import SMBus
from time import time, sleep
import psycopg2
import logging
import typer
from dotenv import load_dotenv
import os
import sys

from sensors.bmp280 import BMP280

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

load_dotenv()


def main(sample_period_s: int = 60) -> None:
    """measure temp and pressure and write to database

    Args:
        sample_period_s (int, optional): how often to take measurements, in seconds. Defaults to 60.
    """
    username = os.getenv("db_username")

    i2c_interface = SMBus(1)
    bmp = BMP280(i2c_interface)
    connection = f"postgres://{username}@127.0.0.1:5432/air_quality"

    bmp.reset.write()
    bmp.config.write(smoothing_const=1)

    try:
        while True:
            sleep(sample_period_s - (time() % sample_period_s))  # no drift
            bmp.ctrl_meas.write(
                pressure_oversampling=16, temperature_oversampling=2, measurement_mode="trigger"
            )
            # wait for measurement to complete
            sleep(0.020)
            bmp.status.read()
            while bmp.status.values["measuring"]:
                sleep(0.025)
                bmp.status.read()
            bmp.data.read()
            write_to_db(
                connection, temp=bmp.data.values["temperature"], press=bmp.data.values["pressure"]
            )

    except KeyboardInterrupt:
        bmp.ctrl_meas.write(measurement_mode="sleep")


def write_to_db(connection: str, *, temp: float, press: float) -> None:
    sql = "INSERT INTO sensor_data(time, temp, press) VALUES (NOW(), %s, %s);"
    data = (temp, press)

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
