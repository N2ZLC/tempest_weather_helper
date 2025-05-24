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
import math
import socket
import statistics
import threading
import traceback
import time

#
from collections import deque

#
@enum.unique
class PrecipitationType(enum.Enum):

	#
	NONE = 0
	RAIN = 1
	HAIL = 2

# Enum value is an array of two tuples representing two ranges from a_mb to b_mb, where the first is an hourly trend, and the second a three-hour trend, where a_mb is exclusive and b_mb is inclusive.
# We must use an array of tuples because enum __init__() doesn't handle a tuple of tuples in a way that's particularly useful.
# There are various and conflicting standards for the ranges.
# See: http://mintakainnovations.com/wp-content/uploads/Pressure_Tendency_Characteristic_Code.pdf
# See: https://w1.weather.gov/glossary/index.php?letter=p
# One-hour STEADY values suggested by William Gidley of WeatherFlow.
@enum.unique
class PressureTrend(enum.Enum):

	#
	FALLING_RAPIDLY = [(None, -2), (None, -6)]
	FALLING_SLOWLY = [(-2, -0.5), (-6, -1)]
	STEADY = [(-0.5, 0.5), (-1, 1)]
	RISING_SLOWLY = [(0.5, 2), (1, 6)]
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

#
@enum.unique
class PressureTrendAdvanced(enum.Enum):

	#
	CONTINUOUSLY_FALLING = 1
	CONTINUOUSLY_RISING = 2
	FALLING_THEN_SLIGHTLY_RISING = 3
	FALLING_THEN_STEADY = 4
	RISING_THEN_SLIGHTLY_FALLING = 5
	RISING_THEN_STEADY = 6
	SLIGHTLY_FALLING_THEN_RISING = 7
	SLIGHTLY_RISING_THEN_FALLING = 8
	STEADY = 9
	STEADY_THEN_FALLING = 10
	STEADY_THEN_RISING = 11
	UNSTEADY_OR_INCONCLUSIVE = 12

# Enum value is a tuple representing a range from a_mm_per_minute to b_mm_per_minute, where a_mm_per_minute is inclusive and b_mm_per_minute is exclusive.
# There are various and conflicting standards for the ranges.
# See: https://water.usgs.gov/edu/activity-howmuchrain-metric.html
@enum.unique
class RainfallIntensity(enum.Enum):

	#
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

	#
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

	#
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

#
class TempestWeatherHelper(threading.Thread):

	# For singleton pattern.
	__instance = None

	# Cache approximately 12 hours of data.
	__fifo_queue = deque(maxlen=720)

	# Most of these are raw values from the Tempest hub, but some are derivations.
	last_updated_epoch = None
	last_updated_iso_8601 = None
	lightning_detected = None
	lightning_strike_average_distance_km = None
	lightning_strike_average_distance_miles = None
	pressure_inhg = None
	pressure_mb = None
	pressure_trend_advanced_three_hours_description = None
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
		try:

			#
			data = {}
			data['last_updated_epoch'] = cls.last_updated_epoch if cls.last_updated_epoch is not None else None
			data['last_updated_iso_8601'] = cls.last_updated_iso_8601 if cls.last_updated_iso_8601 is not None else None
			data['lightning_detected'] = cls.lightning_detected if cls.lightning_detected is not None else None
			data['lightning_strike_average_distance_km'] = cls.lightning_strike_average_distance_km if cls.lightning_strike_average_distance_km is not None else None
			data['lightning_strike_average_distance_miles'] = cls.lightning_strike_average_distance_miles if cls.lightning_strike_average_distance_miles is not None else None
			data['pressure_inhg'] = cls.pressure_inhg if cls.pressure_inhg is not None else None
			data['pressure_mb'] = cls.pressure_mb if cls.pressure_mb is not None else None
			data['pressure_trend_advanced_three_hours_description'] = cls.pressure_trend_advanced_three_hours_description.name.replace('_', ' ') if cls.pressure_trend_advanced_three_hours_description is not None else None
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

		#
		except Exception as e:

			#
			print(traceback.format_exc(), file = sys.stderr, flush = True)

	# Note it's get_for_json()—not get_json(). This isn't really JSON as we're using single quotes, None in lieu of null, True/False in lieu of true/false, etc. But it can easily be converted into strict JSON.
	@classmethod
	def get_all_for_json(cls):
		return cls.list(__fifo_queue)

	@classmethod
	def run(cls):

		#
		while True:

			# Try to create and bind the socket.
			try:

				# We're interested in UDP.
				cls.__socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
				
				# This allows us to rebind if needed and avoid a potential "Address already in use" error.
				cls.__socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
				
				# 50222 is the UDP port used by the Tempest hub to broadcast weather data.
				cls.__socket.bind(('0.0.0.0', 50222))

				# Start listening loop.
				while True:

					#
					try:

						# This blocks until something is received.
						bytes_from_tempest_hub, address = cls.__socket.recvfrom(4096)

						#
						cls.handle_data(bytes_from_tempest_hub)

					# 
					except socket.error as e:

						# Break out to reinitialize the socket.
						break

			#
			except Exception as e:

				#
				print(traceback.format_exc(), file = sys.stderr, flush = True)

			# Cleanup.
			if cls.__socket:

				# Try to close the socket before we dereference it.
				try:

					# 
					cls.__socket.close()

				#
				except Exception:
					pass

				# Dereference from memory.
				cls.__socket = None

			# Pause a bit before attempting to regain the lost connection.
			time.sleep(5)

	#
	@classmethod
	def handle_data(cls, bytes_from_tempest_hub):

		#
		try:

			#
			data = json.loads(bytes_from_tempest_hub.decode('utf-8'))

			# Troubleshooting.
			#print("received message from %s:%s — %s" % (address[0], address[1], bytes_from_tempest_hub))

			# See: https://weatherflow.github.io/Tempest/api/udp/v143/
			# We're only interested in general observation packets. Other packets report 'rapid_wind', 'hub_status', etc.
			if data['type'] is None or data['type'] != 'obs_st': return

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
			cls.last_updated_epoch = data['obs'][0][0] if data['obs'][0][0] is not None else None
			cls.last_updated_iso_8601 = datetime.datetime.fromtimestamp(data['obs'][0][0]).utcnow().replace(tzinfo=datetime.timezone.utc, microsecond = 0).isoformat() if data['obs'][0][0] is not None else None
			cls.lightning_detected = data['obs'][0][15] > 0 if data['obs'][0][15] is not None else None
			cls.lightning_strike_average_distance_km = data['obs'][0][14] if data['obs'][0][14] is not None else None
			cls.lightning_strike_average_distance_miles = float(round(decimal.Decimal(data['obs'][0][14] * 0.621371), 1)) if data['obs'][0][14] is not None else None
			cls.pressure_inhg = float(round(decimal.Decimal(data['obs'][0][6] * 0.02953), 2)) if data['obs'][0][6] is not None else None
			cls.pressure_mb = data['obs'][0][6] if data['obs'][0][6] is not None else None
			pressure_trend_one_hour_mb = cls.get_pressure_change_mb_from(60)
			cls.pressure_trend_one_hour_mb = float(round(pressure_trend_one_hour_mb, 2)) if pressure_trend_one_hour_mb is not None else None
			cls.pressure_trend_one_hour_inhg = float(round(decimal.Decimal(cls.pressure_trend_one_hour_mb * 0.02953), 2)) if cls.pressure_trend_one_hour_mb is not None else None
			cls.pressure_trend_one_hour_description = PressureTrend.fromOneHourObservation(cls.pressure_trend_one_hour_mb) if cls.pressure_trend_one_hour_mb is not None else None
			pressure_trend_three_hours_mb = cls.get_pressure_change_mb_from(180)
			cls.pressure_trend_three_hours_mb = float(round(pressure_trend_three_hours_mb, 2)) if pressure_trend_three_hours_mb is not None else None
			cls.pressure_trend_three_hours_inhg = float(round(decimal.Decimal(cls.pressure_trend_three_hours_mb * 0.02953), 2)) if cls.pressure_trend_three_hours_mb is not None else None
			cls.pressure_trend_three_hours_description = PressureTrend.fromThreeHourObservation(cls.pressure_trend_three_hours_mb) if cls.pressure_trend_three_hours_mb is not None else None
			cls.pressure_trend_advanced_three_hours_description = cls.get_pressure_trend_advanced_from(180)
			cls.precipitation_mm_per_minute = data['obs'][0][12] if data['obs'][0][12] is not None else None
			cls.precipitation_inches_per_minute = float(round(decimal.Decimal(data['obs'][0][12] * 0.03937), 6)) if data['obs'][0][12] is not None else None
			cls.precipitation_description = RainfallIntensity.fromValue(data['obs'][0][12]) if data['obs'][0][12] is not None else None
			cls.precipitation_detected = data['obs'][0][12] > 0 if data['obs'][0][12] is not None else None
			cls.precipitation_type = PrecipitationType(data['obs'][0][13]) if data['obs'][0][13] is not None else None
			cls.relative_humidity = float(round(decimal.Decimal(data['obs'][0][8]), 1)) if data['obs'][0][8] is not None else None
			cls.solar_radiation = data['obs'][0][11] if data['obs'][0][11] is not None else None
			cls.temperature_c = data['obs'][0][7] if data['obs'][0][7] is not None else None
			cls.temperature_f = float(round(decimal.Decimal(data['obs'][0][7] * 1.8 + 32), 1)) if data['obs'][0][7] is not None else None
			cls.uv_index = data['obs'][0][10] if data['obs'][0][10] is not None else None
			cls.uv_exposure_category = UltravioletExposureCategory.fromValue(data['obs'][0][10]) if data['obs'][0][10] is not None else None
			cls.wind_gust_meters_per_second = data['obs'][0][3] if data['obs'][0][3] is not None else None
			cls.wind_gust_miles_per_hour = float(round(decimal.Decimal(data['obs'][0][3] * 2.237), 1)) if data['obs'][0][3] is not None else None
			cls.wind_gust_description = WindGust.fromValue(cls.wind_gust_miles_per_hour) if cls.wind_gust_miles_per_hour is not None else None

			# Add to cache.
			cls.__fifo_queue.append(cls.get_for_json())

		#
		except Exception as e:

			#
			print(traceback.format_exc(), file = sys.stderr, flush = True)

	#
	@classmethod
	def get_pressure_change_mb_from(cls, minutes_ago):

		#
		try:

			#
			if cls.pressure_mb is None: return None

			# This works because the Tempest hub sends updates once per minute. So we use the index of the updates themselves to get the correct entries; no need to mess around with timestamps.
			# Slice notation negative indexes allow us to take n-last elements from a list.
			history_from_minutes_ago = list(cls.__fifo_queue)[-minutes_ago:]

			# We're only interested in pressure_mb.
			# List comprehension allows us to create a list of specific dictionary key values culled from a list of dictionary objects.
			historical_pressure_mb = [i['pressure_mb'] for i in history_from_minutes_ago]

			# Validate that we have enough data.
			if len(historical_pressure_mb) < minutes_ago: return None

			# Using min/max lets us better handle cases where the pressure fell after slightly rising, or rose after slightly falling.
			# In such cases, the change is potentially greater than if we merely used the initial starting point.
			min_pressure_mb = min(historical_pressure_mb)
			max_pressure_mb = max(historical_pressure_mb)

			# Rise has a positive value; fall has a negative value.
			change_from_min = cls.pressure_mb - min_pressure_mb
			change_from_max = cls.pressure_mb - max_pressure_mb

			# Return the largest magnitude of change.
			if (max(abs(change_from_min), abs(change_from_max)) == abs(change_from_min)):
				return change_from_min
			else:
				return change_from_max

		#
		except Exception as e:

			#
			print(traceback.format_exc(), file = sys.stderr, flush = True)

	# Here we attempt to analyze curves with some very simplistic rules, and without importing big gun packages like NumPy and SciPy.
	# It works because pressure curves generally fall into a finite number of patterns for the time range we're using. Zoom out and all bets are off!
	@classmethod
	def get_pressure_trend_advanced_from(cls, minutes_ago):

		#
		try:

			# This works because the Tempest hub sends updates once per minute. So we use the index of the updates themselves to get the correct entries; no need to mess around with timestamps.
			# Slice notation negative indexes allow us to take n-last elements from a list.
			history_from_minutes_ago = list(cls.__fifo_queue)[-minutes_ago:]

			# We're only interested in pressure_mb.
			# List comprehension allows us to create an aggregated list of specific dictionary key values culled from a list of dictionary objects.
			historical_pressure_mb = [i['pressure_mb'] for i in history_from_minutes_ago]

			# Validate that we have enough data.
			if len(historical_pressure_mb) < minutes_ago: return None

			# We also want to examine the first and last quarters of data to detect areas of flatness.
			# Slice notation negative indexes allow us to take n-last elements from a list.
			first_quarter_historical_pressure_mb = historical_pressure_mb[-minutes_ago:-((minutes_ago // 4) * 3)]
			last_quarter_historical_pressure_mb = historical_pressure_mb[-(minutes_ago // 4):]

			# Critical values that will help us to characterize the pressure curve.
			min_pressure_mb = min(historical_pressure_mb)
			max_pressure_mb = max(historical_pressure_mb)
			variance_mb = statistics.pstdev(historical_pressure_mb)
			variance_of_first_quarter_mb = statistics.pstdev(first_quarter_historical_pressure_mb)
			variance_of_last_quarter_mb = statistics.pstdev(last_quarter_historical_pressure_mb)
			equals_tolerance_mb = (PressureTrend.STEADY.b_mb_change_per_three_hours - PressureTrend.STEADY.a_mb_change_per_three_hours) / 2

			# Simplify booleans for clarity.
			# Here we set our scale/sensitivity thresholds and make use of math.isclose() to add some fuzziness.
			# Zoomed in, even a relatively flat curve may appear highly variable. But zoom out too much and everything looks flat.
			# The scale we're interested in is approximately a 6-millibar range (based on the values we use in our PressureTrend enum)
			all_steady = math.isclose(variance_mb, 0, abs_tol = equals_tolerance_mb / 4)
			current_pressure_equals_max = math.isclose(cls.pressure_mb, max_pressure_mb, abs_tol = equals_tolerance_mb)
			current_pressure_equals_min = math.isclose(cls.pressure_mb, min_pressure_mb, abs_tol = equals_tolerance_mb)
			current_pressure_greater_than_min = cls.pressure_mb > min_pressure_mb and math.isclose(cls.pressure_mb, min_pressure_mb, abs_tol = equals_tolerance_mb) is False
			current_pressure_less_than_max = cls.pressure_mb < max_pressure_mb and math.isclose(cls.pressure_mb, max_pressure_mb, abs_tol = equals_tolerance_mb) is False
			ends_steady = math.isclose(variance_of_last_quarter_mb, 0, abs_tol = equals_tolerance_mb / 8)
			ends_unsteady = ends_steady is False
			past_pressure_equals_max = math.isclose(historical_pressure_mb[0], max_pressure_mb, abs_tol = equals_tolerance_mb)
			past_pressure_equals_min = math.isclose(historical_pressure_mb[0], min_pressure_mb, abs_tol = equals_tolerance_mb)
			past_pressure_greater_than_current = historical_pressure_mb[0] > cls.pressure_mb and math.isclose(historical_pressure_mb[0], cls.pressure_mb, abs_tol = equals_tolerance_mb) is False
			past_pressure_greater_than_min = historical_pressure_mb[0] > min_pressure_mb and math.isclose(historical_pressure_mb[0], min_pressure_mb, abs_tol = equals_tolerance_mb) is False
			past_pressure_less_than_current = historical_pressure_mb[0] < cls.pressure_mb and math.isclose(historical_pressure_mb[0], cls.pressure_mb, abs_tol = equals_tolerance_mb) is False
			past_pressure_less_than_max = historical_pressure_mb[0] < max_pressure_mb and math.isclose(historical_pressure_mb[0], max_pressure_mb, abs_tol = equals_tolerance_mb) is False
			starts_steady = math.isclose(variance_of_first_quarter_mb, 0, abs_tol = equals_tolerance_mb / 8)
			starts_unsteady = starts_steady is False

			# CONTINUOUSLY_FALLING
			if starts_unsteady and past_pressure_greater_than_current and past_pressure_equals_max and current_pressure_equals_min and ends_unsteady:
				return PressureTrendAdvanced.CONTINUOUSLY_FALLING

			# CONTINUOUSLY_RISING
			elif starts_unsteady and past_pressure_less_than_current and past_pressure_equals_min and current_pressure_equals_max and ends_unsteady:
				return PressureTrendAdvanced.CONTINUOUSLY_RISING

			# FALLING_THEN_SLIGHTLY_RISING
			elif starts_unsteady and past_pressure_greater_than_current and current_pressure_greater_than_min and ends_unsteady:
				return PressureTrendAdvanced.FALLING_THEN_SLIGHTLY_RISING

			# FALLING_THEN_STEADY
			elif starts_unsteady and past_pressure_greater_than_current and current_pressure_equals_min and ends_steady:
				return PressureTrendAdvanced.FALLING_THEN_STEADY

			# RISING_THEN_SLIGHTLY_FALLING
			elif starts_unsteady and past_pressure_less_than_current and current_pressure_less_than_max and ends_unsteady:
				return PressureTrendAdvanced.RISING_THEN_SLIGHTLY_FALLING

			# RISING_THEN_STEADY
			elif starts_unsteady and past_pressure_less_than_current and current_pressure_equals_max and ends_steady:
				return PressureTrendAdvanced.RISING_THEN_STEADY

			# SLIGHTLY_FALLING_THEN_RISING
			elif starts_unsteady and past_pressure_greater_than_min and past_pressure_less_than_current and current_pressure_equals_max and ends_unsteady:
				return PressureTrendAdvanced.SLIGHTLY_FALLING_THEN_RISING

			# SLIGHTLY_RISING_THEN_FALLING
			elif starts_unsteady and past_pressure_less_than_max and past_pressure_greater_than_current and current_pressure_equals_min and ends_unsteady:
				return PressureTrendAdvanced.SLIGHTLY_RISING_THEN_FALLING

			# STEADY
			elif all_steady:
				return PressureTrendAdvanced.STEADY

			# STEADY_THEN_FALLING
			elif starts_steady and past_pressure_greater_than_current and current_pressure_equals_min and ends_unsteady:
				return PressureTrendAdvanced.STEADY_THEN_FALLING

			# STEADY_THEN_RISING
			elif starts_steady and past_pressure_less_than_current and current_pressure_equals_max and ends_unsteady:
				return PressureTrendAdvanced.STEADY_THEN_RISING

			# UNSTEADY_OR_INCONCLUSIVE
			else: return PressureTrendAdvanced.UNSTEADY_OR_INCONCLUSIVE

		#
		except Exception as e:

			#
			print(traceback.format_exc(), file = sys.stderr, flush = True)

# Main function is executed only when run as a Python program, not when imported as a module.
def main():

	#
	tempestWeatherHelper = TempestWeatherHelper()
	tempestWeatherHelper.start()

	#
	while True:

		#
		print(tempestWeatherHelper.get_for_json(), file = sys.stdout, flush = True)

		#
		time.sleep(55)

if __name__ == '__main__':

	#
	main()
