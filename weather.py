import requests
from datetime import datetime, timedelta
import random

# ---------------- CONFIG ----------------
STATION_ID = "KMNBABBI25"
PASSWORD = "SX8EG38H"
SECRET = "my-secret-token"

# Nearby PWS for realistic wind values (replace with real nearby station ID if available)
NEARBY_STATION_ID = "KMNBABBI"  

# Timezone offset: CST is UTC-6
CST_OFFSET = -6

# Base start and peak values for interpolation
start_values = {
    "temp_f": 70.0,
    "wind_speed": 0.0,
    "wind_gust": 0.0,
    "rain_in": 0.0,
    "daily_rain_in": 0.0,
    "baro_in": 30.30,
    "dewpt_f": 29.0,
    "humidity": 100.0,
    "uv_index": 0.0,       
    "sol_rad": 0.0       
}

peak_values = {
    "temp_f": 20.0,
    "wind_speed": 15.0,
    "wind_gust": 30.0,
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

def adjust_indoor_temp(base_temp, now_cst, month):
    """Adjust indoor temperature based on season and time-of-day peaks."""
    temp = base_temp

    # Seasonal adjustment (MN example)
    if month in [12, 1, 2]:  # Winter
        temp += 5  # indoor heating effect
    elif month in [6, 7, 8]:  # Summer
        temp += 2  # indoor cooling effect

    # Early morning winter bump (4:30-6:00 AM)
    if now_cst.hour == 4 and now_cst.minute >= 30 or now_cst.hour == 5:
        temp += 2

    # Afternoon winter bump (3:15-4:30 PM)
    if now_cst.hour == 15 and now_cst.minute >= 15 or now_cst.hour == 16:
        temp += 1.5

    # Random fluctuation ±3°F
    temp += random.uniform(-3, 3)
    return temp

def fetch_nearby_wind(station_id):
    url = f"https://api.weather.com/v2/pws/observations/current?stationId={station_id}&format=json&units=e&apiKey=354b43fc8a5e4d7c8b43fc8a5ecd7c56"
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        wind_speed = data["observations"][0]["imperial"]["windSpeed"]
        wind_gust  = data["observations"][0]["imperial"]["windGust"]
        return wind_speed, wind_gust
    except Exception:
        return random.uniform(0, 5), random.uniform(0, 10)

# ---------------- MAIN SCRIPT ----------------
def main():
    # Current time in UTC and CST
    now_utc = datetime.utcnow()
    now_cst = now_utc + timedelta(hours=CST_OFFSET)

    # Define start and peak times (CST)
    time_start_cst = datetime(2026, 1, 30, 18, 54)
    time_peak_cst  = datetime(2026, 1, 30, 23, 59)

    # Compute interpolation factor
    if now_cst <= time_start_cst:
        factor = 0.0
    elif now_cst >= time_peak_cst:
        factor = 1.0
    else:
        total_seconds = (time_peak_cst - time_start_cst).total_seconds()
        elapsed_seconds = (now_cst - time_start_cst).total_seconds()
        factor = elapsed_seconds / total_seconds

    # Temperature with seasonal and time-of-day adjustments
    month = now_cst.month
    base_temp = interpolate(start_values["temp_f"], peak_values["temp_f"], factor)
    temp_f = adjust_indoor_temp(base_temp, now_cst, month)

    # Wind from nearby station
    wind_speed, wind_gust = fetch_nearby_wind(NEARBY_STATION_ID)
    wind_speed = clamp(wind_speed + random.uniform(-1, 1), 0, None)
    wind_gust  = clamp(max(wind_gust + random.uniform(-2, 2), wind_speed), 0, None)

    # Other interpolated variables
    rain_in     = interpolate(start_values["rain_in"], peak_values["rain_in"], factor)
    daily_rain  = interpolate(start_values["daily_rain_in"], peak_values["daily_rain_in"], factor)
    baro_in     = fluctuate(interpolate(start_values["baro_in"], peak_values["baro_in"], factor), 0.05)
    dewpt_f     = fluctuate(interpolate(start_values["dewpt_f"], peak_values["dewpt_f"], factor), 2.0)
    humidity    = clamp(100 - (temp_f - dewpt_f) * 2 + random.uniform(-3, 3), 0, 100)

    wind_dir = fluctuate(230.0, 15.0)
    wind_dir = wind_dir % 360

    clouds = "BKN250"
    weather = "RA"
    software_type = "vws versionxx"

    uv_index = interpolate(start_values["uv_index"], peak_values["uv_index"], factor)
    uv_index = max(0, uv_index + random.uniform(-0.3, 0.3))

    sol_rad = interpolate(start_values["sol_rad"], peak_values["sol_rad"], factor)
    sol_rad = max(0, sol_rad + random.uniform(-10, 10))

    dateutc_str = now_utc.strftime("%Y-%m-%d %H:%M:%S")

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

    print("Sending weather update at CST:", now_cst.strftime("%Y-%m-%d %H:%M:%S"))
    print(f"Temp: {temp_f:.1f}F, Wind: {wind_speed:.1f}mph, Gust: {wind_gust:.1f}mph, Rain: {rain_in:.2f}in, Baro: {baro_in:.2f}, Dew: {dewpt_f:.1f}, Humidity: {humidity:.0f}%")
    
    try:
        r = requests.get(URL, timeout=10)
        print("Status:", r.status_code)
        print("Response:", r.text)
    except requests.exceptions.RequestException as e:
        print("Error sending update:", e)

if __name__ == "__main__":
    main()



