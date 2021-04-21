#!/usr/bin/python3
#
# To use...
#
#     tempestWeatherHelper = TempestWeatherHelper()
#     tempestWeatherHelper.start()
#
# You can then call...
#
#     tempestWeatherHelper.get_for_json()
#
# ...for the latest values, or...
#
#     tempestWeatherHelper.get_all_for_json()
#
# ...for the last 12 hours of data.
import datetime
import decimal
import enum
import json
import queue
import socket
import threading
import time

@enum.unique
class PrecipitationType(enum.Enum):
	NONE = 0
	RAIN = 1
	HAIL = 2

# Enum value is an array of two tuples representing two ranges from a_mb to b_mb, where the first is an hourly trend, and the second a three-hour trend, where a_mb is exclusive and b_mb is inclusive.
# We must use an array of tuples because enum __init__() doesn't handle a tuple of tuples in a way that's particularly useful.
# There are various and conflicting standards for the ranges.
# See: http://mintakainnovations.com/wp-content/uploads/Pressure_Tendency_Characteristic_Code.pdf
# See: https://w1.weather.gov/glossary/index.php?letter=p
@enum.unique
class PressureTrend(enum.Enum):
	FALLING_RAPIDLY = [(None, -2), (None, -6)]
	FALLING_SLOWLY = [(-2, -1), (-6, -1)]
	STEADY = [(-1, 1), (-1, 1)]
	RISING_SLOWLY = [(1, 2), (1, 6)]
	RISING_RAPIDLY = [(2, None), (6, None)]

	#
	def __init__(self, value):
		self.a_mb_change_per_hour = value[0][0]
		self.b_mb_change_per_hour = value[0][1]
		self.a_mb_change_per_three_hours = value[1][0]
		self.b_mb_change_per_three_hours = value[1][1]

	#
	@classmethod
	def fromOneHourObservation(cls, mb_change):

		#
		if mb_change is None: return None

		#
		for pressureTrend in PressureTrend:

			#
			if (pressureTrend.a_mb_change_per_hour is None or pressureTrend.a_mb_change_per_hour < mb_change) and (pressureTrend.b_mb_change_per_hour is None or mb_change <= pressureTrend.b_mb_change_per_hour): return pressureTrend

		return None

	#
	@classmethod
	def fromThreeHourObservation(cls, mb_change):

		#
		if mb_change is None: return None

		#
		for pressureTrend in PressureTrend:

			#
			if (pressureTrend.a_mb_change_per_three_hours is None or pressureTrend.a_mb_change_per_three_hours < mb_change) and (pressureTrend.b_mb_change_per_three_hours is None or mb_change <= pressureTrend.b_mb_change_per_three_hours): return pressureTrend

		return None

# TODO:
# This is an analysis of the data/time curve using calculus. We're looking for a single significant inflection point.
# Inflection points occur when the second derivative is zero or undefined.
# Comparing the values on each side of the point can yield these nine possibilities.
@enum.unique
class PressureTrendAdvanced(enum.Enum):
	CONTINUOUSLY_FALLING = 1
	CONTINUOUSLY_RISING = 2
	FALLING_AFTER_SLIGHTLY_RISING = 3
	FALLING_THEN_SLOWLY_RISING = 4
	FALLING_THEN_STEADY = 5
	RISING_AFTER_SLIGHTLY_FALLING = 6
	RISING_THEN_SLOWLY_FALLING = 7
	RISING_THEN_STEADY = 8
	STEADY = 9

# Enum value is a tuple representing a range from a_mm_per_minute to b_mm_per_minute, where a_mm_per_minute is inclusive and b_mm_per_minute is exclusive.
# There are various and conflicting standards for the ranges.
# See: https://water.usgs.gov/edu/activity-howmuchrain-metric.html
@enum.unique
class RainfallIntensity(enum.Enum):
	NONE = (None, 0.000001)
	LIGHT = (0.000001, 0.008333)
	MODERATE = (0.008333, 0.066666)
	HEAVY = (0.066666, 0.133333)
	VERY_HEAVY = (0.133333, None)

	#
	def __init__(self, a_mm_per_minute, b_mm_per_minute):
		self.a_mm_per_minute = a_mm_per_minute
		self.b_mm_per_minute = b_mm_per_minute

	#
	@classmethod
	def fromValue(cls, precipitation_mm_per_minute):

		#
		if precipitation_mm_per_minute is None: return None

		#
		for rainfallIntensity in RainfallIntensity:

			#
			if (rainfallIntensity.a_mm_per_minute is None or rainfallIntensity.a_mm_per_minute < precipitation_mm_per_minute) and (rainfallIntensity.b_mm_per_minute is None or precipitation_mm_per_minute <= rainfallIntensity.b_mm_per_minute): return rainfallIntensity

		return None

# Enum value is a tuple representing a range from a_index to b_index, where a_index is inclusive and b_index is exclusive.
@enum.unique
class UltravioletExposureCategory(enum.Enum):
	LOW = (None, 3)
	MODERATE = (3, 6)
	HIGH = (6, 8)
	VERY_HIGH = (8, 11)
	EXTREME = (11, None)

	#
	def __init__(self, a_index, b_index):
		self.a_index = a_index
		self.b_index = b_index

	#
	@classmethod
	def fromValue(cls, uv_index):

		#
		if uv_index is None: return None

		#
		for ultravioletExposureCategory in UltravioletExposureCategory:

			#
			if (ultravioletExposureCategory.a_index is None or ultravioletExposureCategory.a_index <= uv_index) and (ultravioletExposureCategory.b_index is None or uv_index < ultravioletExposureCategory.b_index): return ultravioletExposureCategory

		return None

# Enum value is a tuple representing a range from a_mph to b_mph, where a_mph is inclusive and b_mph is exclusive.
@enum.unique
class WindGust(enum.Enum):
	CALM = (None, 1)
	LIGHT_AIR = (1, 4)
	LIGHT_BREEZE = (4, 8)
	GENTLE_BREEZE = (8, 13)
	MODERATE_BREEZE = (13, 19)
	FRESH_BREEZE = (19, 25)
	STRONG_BREEZE = (25, 32)
	NEAR_GALE = (32, 38)
	GALE = (38, 47)
	STRONG_GALE = (47, 55)
	STORM = (55, 64)
	VIOLENT_STORM = (64, 73)
	HURRICANE = (73, None)

	#
	def __init__(self, a_mph, b_mph):
		self.a_mph = a_mph
		self.b_mph = b_mph

	#
	@classmethod
	def fromValue(cls, wind_gust_miles_per_hour):

		#
		if wind_gust_miles_per_hour is None: return None

		#
		for windGust in WindGust:

			#
			if (windGust.a_mph is None or windGust.a_mph <= wind_gust_miles_per_hour) and (windGust.b_mph is None or wind_gust_miles_per_hour < windGust.b_mph): return windGust

		return None

# Subclass Queue to make it do what we need.
class ReadableQueue(queue.Queue):

	# Override put()
	def put(self, *args, **kwargs):

		# Add our extra logic.
		if self.full():

			# A True value from `full()` does not guarantee that anything remains in the queue when get() is called.
			try:

				#
				self.get()

			# 
			except queue.Queue.Empty:

				#
				pass

		# Continue normally.
		queue.Queue.put(self, *args, **kwargs)

	# Returns a copy of all items in the queue in a thread-safe manner without removing them.
	def to_list(self):

		#
		with self.mutex: return list(self.queue)

#
class TempestWeatherHelper(threading.Thread):

	# For singleton pattern.
	__instance = None

	# Cache approximately 12 hours of data.
	__readable_queue = ReadableQueue(maxsize = 720)

	# Most of these are raw values from the Tempest hub, but some are derivations.
	last_updated_epoch = None
	last_updated_iso_8601 = None
	lightning_detected = None
	lightning_strike_average_distance_km = None
	lightning_strike_average_distance_miles = None
	pressure_inhg = None
	pressure_mb = None
	pressure_trend_one_hour_description = None
	pressure_trend_one_hour_inhg = None
	pressure_trend_one_hour_mb = None
	pressure_trend_three_hours_description = None
	pressure_trend_three_hours_inhg = None
	pressure_trend_three_hours_mb = None
	precipitation_description = None
	precipitation_detected = None
	precipitation_inches_per_minute = None
	precipitation_mm_per_minute = None
	precipitation_type = None
	relative_humidity = None
	solar_radiation = None
	temperature_c = None
	temperature_f = None
	uv_exposure_category = None
	uv_index = None
	wind_gust_description = None
	wind_gust_meters_per_second = None
	wind_gust_miles_per_hour = None

	#
	def __new__(cls):

		#
		if cls.__instance is None:

			# 
			cls.__instance = threading.Thread.__new__(cls)

		return cls.__instance

	#
	def __init__(self):

		# Super initialize.
		super(TempestWeatherHelper, self).__init__()

		# Whenever the parent thread dies, we want all child threads to die with it.
		self.__instance.daemon = True

	# Note it's get_for_json()—not get_json(). This isn't really JSON as we're using single quotes, None in lieu of null, True/False in lieu of true/false, etc. But it can easily be converted into strict JSON.
	@classmethod
	def get_for_json(cls):

		#
		data = {}
		data['last_updated_epoch'] = cls.last_updated_epoch if cls.last_updated_epoch is not None else None
		data['last_updated_iso_8601'] = cls.last_updated_iso_8601 if cls.last_updated_iso_8601 is not None else None
		data['lightning_detected'] = cls.lightning_detected if cls.lightning_detected is not None else None
		data['lightning_strike_average_distance_km'] = cls.lightning_strike_average_distance_km if cls.lightning_strike_average_distance_km is not None else None
		data['lightning_strike_average_distance_miles'] = cls.lightning_strike_average_distance_miles if cls.lightning_strike_average_distance_miles is not None else None
		data['pressure_inhg'] = cls.pressure_inhg if cls.pressure_inhg is not None else None
		data['pressure_mb'] = cls.pressure_mb if cls.pressure_mb is not None else None
		data['pressure_trend_one_hour_description'] = cls.pressure_trend_one_hour_description.name.replace('_', ' ') if cls.pressure_trend_one_hour_description is not None else None
		data['pressure_trend_three_hours_description'] = cls.pressure_trend_three_hours_description.name.replace('_', ' ') if cls.pressure_trend_three_hours_description is not None else None
		data['pressure_trend_one_hour_inhg'] = cls.pressure_trend_one_hour_inhg if cls.pressure_trend_one_hour_inhg is not None else None
		data['pressure_trend_one_hour_mb'] = cls.pressure_trend_one_hour_mb if cls.pressure_trend_one_hour_mb is not None else None
		data['pressure_trend_three_hours_inhg'] = cls.pressure_trend_three_hours_inhg if cls.pressure_trend_three_hours_inhg is not None else None
		data['pressure_trend_three_hours_mb'] = cls.pressure_trend_three_hours_mb if cls.pressure_trend_three_hours_mb is not None else None
		data['precipitation_inches_per_minute'] = '{0:.6f}'.format(cls.precipitation_inches_per_minute) if (cls.precipitation_inches_per_minute is not None and cls.precipitation_inches_per_minute != 0) else cls.precipitation_inches_per_minute if cls.precipitation_inches_per_minute is not None else None
		data['precipitation_mm_per_minute'] = cls.precipitation_mm_per_minute if cls.precipitation_mm_per_minute is not None else None
		data['precipitation_description'] = cls.precipitation_description.name.replace('_', ' ') if cls.precipitation_description is not None else None
		data['precipitation_detected'] = cls.precipitation_detected if cls.precipitation_detected is not None else None
		data['precipitation_type'] = cls.precipitation_type.name.replace('_', ' ') if cls.precipitation_type is not None else None
		data['relative_humidity'] = cls.relative_humidity if cls.relative_humidity is not None else None
		data['solar_radiation'] = cls.solar_radiation if cls.solar_radiation is not None else None
		data['temperature_c'] = cls.temperature_c if cls.temperature_c is not None else None
		data['temperature_f'] = cls.temperature_f if cls.temperature_f is not None else None
		data['uv_exposure_category'] = cls.uv_exposure_category.name.replace('_', ' ') if cls.uv_exposure_category is not None else None
		data['uv_index'] = cls.uv_index if cls.uv_index is not None else None
		data['wind_gust_description'] = cls.wind_gust_description.name.replace('_', ' ') if cls.wind_gust_description is not None else None
		data['wind_gust_meters_per_second'] = cls.wind_gust_meters_per_second if cls.wind_gust_meters_per_second is not None else None
		data['wind_gust_miles_per_hour'] = cls.wind_gust_miles_per_hour if cls.wind_gust_miles_per_hour is not None else None

		#
		return data

	# Note it's get_for_json()—not get_json(). This isn't really JSON as we're using single quotes, None in lieu of null, True/False in lieu of true/false, etc. But it can easily be converted into strict JSON.
	@classmethod
	def get_all_for_json(cls):
		return cls.__readable_queue.to_list()

	#
	@classmethod
	def run(cls):

		#
		cls.__socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		cls.__socket.bind(('', 50222)) # 50222 is the UDP port used by the Tempest hub to broadcast weather data.

		#
		while True:

			# This blocks until something is received.
			bytes_from_tempest_hub, address = cls.__socket.recvfrom(1024)

			#
			data = json.loads(bytes_from_tempest_hub.decode('utf-8'))

			# Troubleshooting.
			#print("received message from %s:%s — %s" % (address[0], address[1], bytes_from_tempest_hub))

			# See: https://weatherflow.github.io/Tempest/api/udp/v143/
			# We're only interested in general observation packets. Other packets report 'rapid_wind', 'hub_status', etc.
			if data['type'] != 'obs_st': continue

			# See: https://weatherflow.github.io/Tempest/api/udp/v143/
			#
			# Index    Field                                     Units
			# -------------------------------------------------------------------------------
			#  0       Time Epoch                                Seconds
			#  1       Wind Lull(minimum 3 second sample)        m / s
			#  2       Wind Avg(average over report interval)    m / s
			#  3       Wind Gust(maximum 3 second sample)        m / s
			#  4       Wind Direction                            Degrees
			#  5       Wind Sample Interval                      seconds
			#  6       Station Pressure                          MB
			#  7       Air Temperature                           C
			#  8       Relative Humidity                         %
			#  9       Illuminance                               Lux
			# 10       UV                                        Index
			# 11       Solar Radiation                           W / m ^ 2
			# 12       Precip Accumulated                        mm
			# 13       Precipitation Type                        0 = none, 1 = rain, 2 = hail
			# 14       Lightning Strike Avg Distance             km
			# 15       Lightning Strike Count
			# 16       Battery                                   Volts
			# 17       Report Interval                           Minutes
			cls.last_updated_epoch = data['obs'][0][0]
			cls.last_updated_iso_8601 = datetime.datetime.fromtimestamp(data['obs'][0][0]).utcnow().replace(tzinfo=datetime.timezone.utc, microsecond = 0).isoformat()
			cls.lightning_detected = data['obs'][0][15] > 0
			cls.lightning_strike_average_distance_km = data['obs'][0][14]
			cls.lightning_strike_average_distance_miles = float(round(decimal.Decimal(data['obs'][0][14] * 0.621371), 1))
			cls.pressure_inhg = float(round(decimal.Decimal(data['obs'][0][6] * 0.02953), 2))
			cls.pressure_mb = data['obs'][0][6]
			pressure_trend_one_hour_mb = cls.get_pressure_change_from(60)
			cls.pressure_trend_one_hour_mb = float(round(pressure_trend_one_hour_mb, 2)) if pressure_trend_one_hour_mb is not None else None
			cls.pressure_trend_one_hour_inhg = float(round(decimal.Decimal(cls.pressure_trend_one_hour_mb * 0.02953), 2)) if cls.pressure_trend_one_hour_mb is not None else None
			cls.pressure_trend_one_hour_description = PressureTrend.fromOneHourObservation(cls.pressure_trend_one_hour_mb) if cls.pressure_trend_one_hour_mb is not None else None
			pressure_trend_three_hours_mb = cls.get_pressure_change_from(180)
			cls.pressure_trend_three_hours_mb = float(round(pressure_trend_three_hours_mb, 2)) if pressure_trend_three_hours_mb is not None else None
			cls.pressure_trend_three_hours_inhg = float(round(decimal.Decimal(cls.pressure_trend_three_hours_mb * 0.02953), 2)) if cls.pressure_trend_three_hours_mb is not None else None
			cls.pressure_trend_three_hours_description = PressureTrend.fromThreeHourObservation(cls.pressure_trend_three_hours_mb) if cls.pressure_trend_three_hours_mb is not None else None
			cls.precipitation_mm_per_minute = data['obs'][0][12]
			cls.precipitation_inches_per_minute = float(round(decimal.Decimal(data['obs'][0][12] * 0.03937), 6))
			cls.precipitation_description = RainfallIntensity.fromValue(data['obs'][0][12])
			cls.precipitation_detected = data['obs'][0][12] > 0
			cls.precipitation_type = PrecipitationType(data['obs'][0][13])
			cls.relative_humidity = float(round(decimal.Decimal(data['obs'][0][8]), 1))
			cls.solar_radiation = data['obs'][0][11]
			cls.temperature_c = data['obs'][0][7]
			cls.temperature_f = float(round(decimal.Decimal(data['obs'][0][7] * 1.8 + 32), 1))
			cls.uv_index = data['obs'][0][10]
			cls.uv_exposure_category = UltravioletExposureCategory.fromValue(data['obs'][0][10])
			cls.wind_gust_meters_per_second = data['obs'][0][3]
			cls.wind_gust_miles_per_hour = float(round(decimal.Decimal(data['obs'][0][3] * 2.237), 1))
			cls.wind_gust_description = WindGust.fromValue(cls.wind_gust_miles_per_hour) if cls.wind_gust_miles_per_hour is not None else None

			# Add to 12-hour cache.
			cls.__readable_queue.put(cls.get_for_json())

	#
	@classmethod
	def get_pressure_change_from(cls, minutes_ago):

		#
		history = cls.__readable_queue.to_list()

		# This works because the Tempest hub sends updates once per minute. So we use the index of the updates themselves to get the correct entry; no need to mess around with timestamps.
		data = history[len(history) - minutes_ago] if len(history) >= minutes_ago else None

		#
		return data['pressure_mb'] - cls.pressure_mb if (data is not None and data['pressure_mb'] is not None and cls.pressure_mb is not None) else None

# Main function is executed only when run as a Python program, not when imported as a module.
def main():

	#
	tempestWeatherHelper = TempestWeatherHelper()
	tempestWeatherHelper.start()

	#
	while True:

		#
		print(tempestWeatherHelper.get_for_json())

		#
		time.sleep(5)

if __name__ == '__main__':

	#
	main()