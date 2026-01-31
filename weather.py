import requests
from datetime import datetime, timedelta, time
import random

# ---------------- CONFIG ----------------
STATION_ID = "KMNBABBI25"
PASSWORD = "SX8EG38H"
SECRET = "my-secret-token"

CST_OFFSET = -6  # Central Standard Time

# Nearby PWS (Babbitt MN) for wind comparison
BABBitt_PWS_ID = "KMNBABBI27"
BABBitt_API_KEY = "354b43fc8a5e4d7c8b43fc8a5ecd7c56"  # replace with your WU API key if needed

# ---------------- BASE INTERPOLATION VALUES ----------------
base_values = {
    "temp_f": {"winter_low": -10, "winter_high": 20, "summer_low": 55, "summer_high": 85},
    "wind_speed": {"max": 15},  # default max for interpolation
    "wind_gust": {"max": 30},
    "rain_in": 0.0,
    "daily_rain_in": 0.0,
    "baro_in": 30.30,
    "dewpt_f": 29.0,
    "humidity": 100.0,
    "uv_index": 0.0,
    "sol_rad": 0.0
}

# ---------------- UTILITY FUNCTIONS ----------------
def interpolate(start, end, factor):
    return start + (end - start) * factor

def fluctuate(value, fluctuation):
    return value + random.uniform(-fluctuation, fluctuation)

def clamp(value, min_val=None, max_val=None):
    if min_val is not None and value < min_val:
        return min_val
    if max_val is not None and value > max_val:
        return max_val
    return value

def get_seasonal_temp(now_cst):
    month = now_cst.month
    if month in [12, 1, 2]:  # Winter
        return base_values["temp_f"]["winter_low"], base_values["temp_f"]["winter_high"]
    elif month in [6, 7, 8]:  # Summer
        return base_values["temp_f"]["summer_low"], base_values["temp_f"]["summer_high"]
    else:  # Spring/Fall
        low = (base_values["temp_f"]["winter_low"] + base_values["temp_f"]["summer_low"]) / 2
        high = (base_values["temp_f"]["winter_high"] + base_values["temp_f"]["summer_high"]) / 2
        return low, high

def time_of_day_factor(now_cst):
    """Return interpolation factor based on time-of-day spikes."""
    t = now_cst.time()
    # Early morning spike winter
    if time(4,30) <= t <= time(6,0):
        return 0.8
    # Afternoon spike winter
    elif time(15,15) <= t <= time(16,30):
        return 0.7
    # Daytime default
    elif time(10,0) <= t <= time(19,0):
        return 0.6
    # Night default
    else:
        return 0.4

def fetch_babbitt_wind():
    """Fetch wind speed/gust from nearby Babbitt PWS (JSON API)."""
    # This example uses a hypothetical API endpoint
    url = f"https://api.weather.com/v2/pws/observations/current?stationId={BABBitt_PWS_ID}&format=json&units=e&apiKey={BABBitt_API_KEY}"
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        wind_speed = float(data['observations'][0]['imperial']['windSpeed'])
        wind_gust = float(data['observations'][0]['imperial']['windGust'])
        return wind_speed, wind_gust
    except Exception as e:
        print("Error fetching Babbitt wind:", e)
        return 0.0, 0.0

# ---------------- MAIN ----------------
def main():
    # Current times
    now_utc = datetime.utcnow()
    now_cst = now_utc + timedelta(hours=CST_OFFSET)

    # Seasonal temperature
    temp_low, temp_high = get_seasonal_temp(now_cst)
    factor_temp = time_of_day_factor(now_cst)
    temp_f = fluctuate(interpolate(temp_low, temp_high, factor_temp), 3.0)

    # Wind interpolation
    base_wind_speed = interpolate(0.0, base_values["wind_speed"]["max"], factor_temp)
    base_wind_gust  = interpolate(0.0, base_values["wind_gust"]["max"], factor_temp)
    wind_speed = fluctuate(base_wind_speed, 5.0)
    wind_gust  = fluctuate(base_wind_gust, 7.0)

    # Pull real Babbitt wind data and use higher of two
    babbitt_wind, babbitt_gust = fetch_babbitt_wind()
    wind_speed = max(0, max(wind_speed, babbitt_wind))
    wind_gust  = max(0, max(wind_gust, babbitt_gust))

    # Other values
    rain_in    = interpolate(base_values["rain_in"], base_values["rain_in"], factor_temp)
    daily_rain = interpolate(base_values["daily_rain_in"], base_values["daily_rain_in"], factor_temp)
    baro_in    = fluctuate(base_values["baro_in"], 0.05)
    dewpt_f    = fluctuate(base_values["dewpt_f"], 2.0)
    humidity   = clamp(fluctuate(base_values["humidity"], 3.0), max_val=100)
    wind_dir   = fluctuate(230.0, 15.0)
    if wind_dir < 0:
        wind_dir = 359
    elif wind_dir >= 360:
        wind_dir = 0

    clouds = "BKN250"
    weather = "RA"
    software_type = "vws versionxx"
    uv_index = max(0, fluctuate(base_values["uv_index"], 0.3))
    sol_rad  = max(0, fluctuate(base_values["sol_rad"], 10.0))

    dateutc_str = now_utc.strftime("%Y-%m-%d %H:%M:%S")

    # Construct WU URL
    URL = (
        f"https://weatherstation.wunderground.com/weatherstation/updateweatherstation.php"
        f"?ID={STATION_ID}&PASSWORD={PASSWORD}&dateutc=now"
        f"&winddir={wind_dir:.0f}&windspeedmph={wind_speed:.1f}&windgustmph={wind_gust:.1f}"
        f"&tempf={temp_f:.1f}&rainin={rain_in:.2f}&dailyrainin={daily_rain:.2f}"
        f"&baromin={baro_in:.2f}&dewptf={dewpt_f:.1f}&humidity={humidity:.0f}"
        f"&uv={uv_index:.1f}&solarradiation={sol_rad:.1f}"
        f"&weather={weather}&clouds={clouds}"
        f"&softwaretype={software_type}&action=updateraw"
    )

    # Send update
    print("Sending weather update at CST:", now_cst.strftime("%Y-%m-%d %H:%M:%S"))
    print(f"Temp: {temp_f:.1f}F, Wind: {wind_speed:.1f}mph, Gust: {wind_gust:.1f}mph, Rain: {rain_in:.2f}in, Baro: {baro_in:.2f}, Dew: {dewpt_f:.1f}, Humidity: {humidity:.0f}%")
    try:
        r = requests.get(URL)
        print("Status:", r.status_code)
        print("Response:", r.text)
    except Exception as e:
        print("Error sending update:", e)

if __name__ == "__main__":
    main()
