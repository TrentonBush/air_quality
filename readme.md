# IoT Data Logging and Dashboard

This project consists of three parts:

1. Device drivers for 5 air quality sensors (measuring particulate matter, CO2, volatile organics, temperature, humidity, pressure). Written in python.
2. Data logging to a TimescaleDB database (a PostgreSQL extension). Implemented as a systemd service to start on boot and auto-restart if it exits.
3. Live dashboard of KPIs, time series, and ad-hoc queries via Grafana.

This setup runs on a Raspberry Pi 4 running Ubuntu 20.04 (aarch64/arm64).
<img src="docs/images/sensors.jpg" width=50% height=50% alt="picture of RPi and sensors" title="The little monster and its sensors">

## What I Learned

## Linux ARM64 support is still hard to come by

Linux ARM64 (aka aarch64) might be the future, but it certainly isn't the present. ARM64 was a pain point because most software is not available pre-built for this architecture, so I had to build from source or find alternatives. Basic stuff like PgAdmin, TimescaleDB, and Anaconda were not available through apt or PPAs. Pip installing python libraries was slow for the same reason: few binary wheels were pre-built, so they had to build at install time. Some builds failed until I found the right compilers.

<img src="docs/images/arm64.png" width=75% height=75% alt="screenshot of installers with no arm64 version">

This wasn't a deal-breaker but I wouldn't use aarch64 again without a compelling reason to do so, at least until ARM market share grows and support improves.

## Sensor hardware is surprisingly configurable - and so are their outputs

This configurability is a double-edged sword because it can have significant impacts on the reported measurements, as I'll explain below. That impact means the configuration must be documented at minimum, and preferably included in the user feedback process.

### Sensors themselves do edge computing

Perhaps naively, I thought reading a pressure sensor returned a single pressure measurement. But actually sensors can perform a surprising amount of post-processing on-chip. For example, my pressure sensor can aggregate up to 16 individual measurements in each reported value, or blend multiple measurements together with an IIR smoothing filter.

Like all edge computing, this processing power can deliver greater value per bandwidth and per storage, but risks erasing key information by aggregating too early.

### There are bias-variance tradeoffs in measurement itself

I know metrology (the study of measurement) is a whole discipline, but I thought all those decisions were made and all that complexity managed at the hardware level. I thought there was nothing a user could do about them except to buy a different device with different specs. Not so. Take my resistive temperature sensor as an example.

I can change the reported measurements from my temperature sensor by 0.2 °C just by changing the sampling frequency. Maybe that is irrelevant for your application, or maybe it is critical. But it is up to the user to design accordingly (and to figure this out in the first place; the datasheet doesn't say a word about self-heating!).

Here are the physics of why this happens. The sensor contains a resistor whose resistance changes with temperature in a known way. By passing current through that resistor and measuring the resistance, the sensor can calculate temperature. But there is a problem here: passing current through a resistor produces heat. Thus the act of measurement changes the temperature of the thing being measured! Again, I thought this complexity was accounted for by the OEM, whether in device design or calibration factors or something. And I'm sure it is to some extent. But not entirely!

The temperature sensor I used gives you the option of oversampling - taking the average of a burst of up to 16 measurements over a few milliseconds. This reduces variance by averaging out random fluctuations. But it increases bias by dumping 16x more heat into the sensor, producing the aforementioned 0.2 °C temp rise. Which option do the end users of the data prefer?

## TimescaleDB is nifty for time series (surprise!)

An extension of PostgreSQL, TimescaleDB gives data engineers a chance to simplify their tooling by putting time series data in the same RDBMS as regular relational data, scale permitting. The extension is enabled per-database, and specific features enabled per table, allowing a nice compartmentalization. I found it integrated seamlessly with Postgres tooling like PgAdmin4, Grafana, and psycopg2.

Timescale also has some built in functionality to make working with time series more convenient and maintainable vs vanilla SQL. For example, tables can be configured with scheduled (time-to-live) aggregation and/or compression, and queries come with built-in time functions like rolling averages, deltas, and binning. The query functionality was fully-featured enough to keep me working in SQL instead of reverting to my comfort zone of the pandas python library.

This is probably starting to sound like an ad for TimescaleDB (TM), but it really was nice to use!
