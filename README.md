# What is this?

**tempest_weather_helper** is a simple Python application that facilitates data-gathering directly from a WeatherFlow Tempest Weather System hub.

# Why?

Python applications that simplify Tempest Weather System integration already exist. But they work by pulling data from WeatherFlow's cloud. **tempest_weather_helper** is intended for those who want to incorporate a Tempest Weather System into their own projects in an offline manner (no Internet required).

# What can it do?

When hub data is available, it caches the data. This cache can then be pulled from **tempest_weather_helper** as JSON (technically, Python-esque JSON). It is not event-driven and will not push data to clients. It must be polled. But since it's a singleton and caches the data in memory, this LAN polling is not particularly expensive.

You have the option of getting the latest values, or the last 12 hours (up to 720 updates). The latter is useful if you plan to graph the results, or use an offline short-term weather forecaster (e.g., Sager algorithm) that depends on some historical data for trends.

In addition to Tempest Weather System hub data, **tempest_weather_helper** also offers some useful derived fields...

* last_updated_iso_8601
* lightning_detected
* lightning_strike_average_distance_miles
* pressure_inhg
* pressure_trend_advanced_three_hours_description
* pressure_trend_one_hour_description
* pressure_trend_one_hour_inhg
* pressure_trend_one_hour_mb
* pressure_trend_three_hours_description
* pressure_trend_three_hours_inhg
* pressure_trend_three_hours_mb
* precipitation_description
* precipitation_detected
* precipitation_inches_per_minute
* temperature_f
* uv_exposure_category
* wind_gust_description
* wind_gust_miles_per_hour
