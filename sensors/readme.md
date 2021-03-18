# Drivers

This directory contains python drivers for 5 sensors, and a helper module for I2C devices

* i2c_base.py: module of abstractions and base classes for the three I2C drivers
* bmp280.py: Bosch BMP280 pressure and temperature sensor. Connects via I2C
* ccs811.py: ScioSense CCS811 volatile organic compound (VOC) sensor. Connects via I2C
* hdc1080.py: Texas Instruments HDC1080 humidity and temperature sensor. Connects via I2C
* pms7003.py: PlanTower PMS7003 particulate matter sensor. Connects via serial UART
* s8.py: SenseAir S8-LP CO2 sensor. Connects via serial UART

## i2c modules outline

### API

I wanted to improve on APIs I have seen in other driver frameworks, which look like:
```
device.write(register_name, dict_of_values)
```

With that model, you have to constantly reference the datasheet to look up the names and allowed values of everything. Instead, I wanted an API which leveraged the autocomplete and docstring lookup functionality of IDEs like VS Code or PyCharm. It now looks like:

abstract example:
```python
device.register.action(field_arg_1=x, field_arg_2=y)
```

Concrete example:
```python
bmp = BMP280(*args)
bmp.config.write(measurement_period_ms=4000, smoothing_const=1)
```
I think this is a more user friendly API. The .read() and .write() methods can now have descriptive variable names, so that obscure field names like 'osrs' can instead be mapped to an arg called 'n_oversamples'. These methods also have helpful docstrings that describe not just what the args are but common usage,  values, and gotchas.

### Structure

Immutable data about hardware properties are stored in Device, Register, and Field classes. A Device contains a few attributes and one or more Registers, which contain a few attributes and one or more Fields. A Field contains a few attributes and an Encoder, which has .encode and .decode methods to convert raw bytes to and from meaningful values like ints, floats, and strings. All these classes are considered immutable, but this is not currently enforced.

Each specific device module (like bmp280.py) contains a definition of that hardware and an API for interacting with it.

The top level class (like BMP280) contains a class attribute Device class which defines the hardware schema. It also contains RegisterAPI classes, which define .read and .write methods for interacting with each register (as well as caching values). 
