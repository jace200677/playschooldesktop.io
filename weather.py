import requests
from datetime import datetime, timedelta
import random

# Weather Underground Station ID and password
STATION_ID = "KMNBABBI25"
PASSWORD = "SX8EG38H"
SECRET = "my-secret-token"

# Timezone offset: CST is UTC-6
CST_OFFSET = -6

# Current time in CST
now_utc = datetime.utcnow()
now_cst = now_utc + timedelta(hours=CST_OFFSET)

# Define start and peak times in CST
time_start_cst = datetime(2026, 1, 23, 12, 52)
time_peak_cst  = datetime(2026, 1, 23, 18, 0)

# Base start and peak values
start_values = {
    "temp_f": -65.0,
    "wind_speed": 38.0,
    "wind_gust": 58.0,
    "rain_in": 0.0,
    "baro_in": 28.80,
    "dewpt_f": -55.0,
    "humidity": 100.0
}

peak_values = {
    "temp_f": -25.0,
    "wind_speed": 98.0,
    "wind_gust": 128.0,
    "rain_in": 0.0,
    "baro_in": 30.30,
    "dewpt_f": -55.0,
    "humidity": 100.0
}

# Linear interpolation
def interpolate(start, end, factor):
    return start + (end - start) * factor

# Random fluctuation
def fluctuate(value, fluctuation):
    return value + random.uniform(-fluctuation, fluctuation)

# Clamp function
def clamp(value, min_val=None, max_val=None):
    if min_val is not None and value < min_val:
        return min_val
    if max_val is not None and value > max_val:
        return max_val
    return value

# Compute factor based on time
if now_cst <= time_start_cst:
    factor = 0.0
elif now_cst >= time_peak_cst:
    factor = 1.0
else:
    total_seconds = (time_peak_cst - time_start_cst).total_seconds()
    elapsed_seconds = (now_cst - time_start_cst).total_seconds()
    factor = elapsed_seconds / total_seconds

# Interpolate + fluctuate + clamp
temp_f      = fluctuate(interpolate(start_values["temp_f"], peak_values["temp_f"], factor), 3.0)
wind_speed  = fluctuate(interpolate(start_values["wind_speed"], peak_values["wind_speed"], factor), 5.0)
wind_gust   = fluctuate(interpolate(start_values["wind_gust"], peak_values["wind_gust"], factor), 7.0)
rain_in     = clamp(fluctuate(interpolate(start_values["rain_in"], peak_values["rain_in"], factor), 0.05), min_val=0)
baro_in     = fluctuate(interpolate(start_values["baro_in"], peak_values["baro_in"], factor), 0.05)
dewpt_f     = fluctuate(interpolate(start_values["dewpt_f"], peak_values["dewpt_f"], factor), 2.0)
humidity    = clamp(fluctuate(interpolate(start_values["humidity"], peak_values["humidity"], factor), 3.0), max_val=100)
if humidity > 100:
    humidity = 100
if wind_dir < 0:
    wind_dir = 359
elif wind_dir >= 360:
    wind_dir = 0
# Constants
wind_dir = clamp(fluctuate(230.0, 15.0), 0, 360)  # wind direction valid 0-360°
clouds = "BKN250"
weather = "RA"
software_type = "vws versionxx"

# Format current UTC datetime for Weather Underground
dateutc_str = now_utc.strftime("%Y-%m-%d %H:%M:%S")

# Build URL
URL = (
    f"https://weatherstation.wunderground.com/weatherstation/updateweatherstation.php"
    f"?ID={STATION_ID}&PASSWORD={PASSWORD}&dateutc=now"
    f"&winddir={wind_dir:.0f}&windspeedmph={wind_speed:.1f}&windgustmph={wind_gust:.1f}"
    f"&tempf={temp_f:.1f}&rainin={rain_in:.2f}&baromin={baro_in:.2f}&dewptf={dewpt_f:.1f}"
    f"&humidity={humidity:.0f}&weather={weather}&clouds={clouds}"
    f"&softwaretype={software_type}&action=updateraw"
)

def main():
    print("Sending weather update at CST:", now_cst.strftime("%Y-%m-%d %H:%M:%S"))
    print(f"Temp: {temp_f:.1f}F, Wind: {wind_speed:.1f}mph, Gust: {wind_gust:.1f}mph, Rain: {rain_in:.2f}in, Baro: {baro_in:.2f}, Dew: {dewpt_f:.1f}, Humidity: {humidity:.0f}%")
    r = requests.get(URL)
    print("Status:", r.status_code)
    print("Response:", r.text)

if __name__ == "__main__":
    main()

