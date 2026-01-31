import requests
from datetime import datetime, timedelta
import random
# ---------------- CONFIG ----------------
STATION_ID = "KMNBABBI25"
PASSWORD = "SX8EG38H"
SECRET = "my-secret-token"

# Nearby PWS for realistic wind values
NEARBY_STATION_ID = "KMNBABBI27"

# Timezone offset: CST is UTC-6
CST_OFFSET = -6

# Base start and peak values for interpolation
start_values = {
    "temp_f": 65.0,
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
    "temp_f": 65.0,
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

def clamp(value, min_val=None, max_val=None):
    if min_val is not None and value < min_val:
        return min_val
    if max_val is not None and value > max_val:
        return max_val
    return value

def adjust_indoor_temp(base_temp, now_cst, month, outdoor_temp):
    temp = base_temp

    weekday = now_cst.weekday()  # 0=Mon ... 6=Sun
    is_weekday = weekday <= 4
    is_friday_night = weekday == 4 and now_cst.hour >= 18
    is_weekend = weekday >= 5

    is_winter = month in [12, 1, 2]
    is_warm_season = month in [3, 4, 5, 6, 7, 8, 9, 10, 11]

    # -------------------------------------------------
    # 🔥 HEATING ENABLE CHECK
    # -------------------------------------------------
    heating_allowed = outdoor_temp < 55

    # -------------------------------------------------
    # 🌡️ BASE SEASONAL DRIFT
    # -------------------------------------------------
    if is_winter:
        temp += 3.5
    elif month in [6, 7, 8]:
        temp += 1.0

    def ramp(start_h, start_m, end_h, end_m, ramp_max):
        start = start_h * 60 + start_m
        end = end_h * 60 + end_m
        now = now_cst.hour * 60 + now_cst.minute

        if now < start or now > end:
            return 0.0

        factor = (now - start) / (end - start)
        return ramp_max * factor

    # -------------------------------------------------
    # 🔥 HEATING FAILURE MODEL (ALL SEASONS)
    # -------------------------------------------------
    heating_failure = False
    weak_heating = False

    if heating_allowed:
        roll = random.random()
        if roll < 0.05:
            heating_failure = True          # 5% hard failure
        elif roll < 0.15:
            weak_heating = True             # 10% weak output

    # -------------------------------------------------
    # 🔥 HEATING LOGIC
    # -------------------------------------------------
    if heating_allowed and not heating_failure:
        strength = 0.4 if weak_heating else 1.0

        if is_weekday:
            temp += ramp(4, 30, 6, 0, 6.0 * strength)
            temp += ramp(15, 15, 16, 30, 4.5 * strength)

        if is_weekend or is_friday_night:
            if outdoor_temp < 15:
                temp += 7 * strength
            elif outdoor_temp < 28:
                temp += 5 * strength
            elif outdoor_temp < 38:
                temp += 3 * strength

    # -------------------------------------------------
    # ❄️ AIR CONDITIONING (80°F+ ONLY, NON-WINTER)
    # -------------------------------------------------
    if is_warm_season and temp >= 80.0:
        ac_roll = random.random()

        if ac_roll < 0.08:
            pass  # AC failed
        elif ac_roll < 0.18:
            temp -= random.uniform(0.2, 0.6)
        else:
            cool_strength = random.uniform(0.8, 1.6)
            if temp >= 85:
                cool_strength += 0.8
            temp -= cool_strength

    # -------------------------------------------------
    # 🔥 HEATING OVERSHOOT (INERTIA)
    # -------------------------------------------------
    overshoot = 0.0
    if heating_allowed and not heating_failure and temp >= 75:
        if random.random() < 0.25:
            overshoot = random.uniform(0.3, 1.6)

    max_heat_temp = 76.0 + overshoot

    # -------------------------------------------------
    # 🧯 FINAL CLAMPS
    # -------------------------------------------------
    if is_winter:
        return clamp(temp, None, max_heat_temp)
    else:
        return clamp(temp, 70.0, 85.0)

# ---------------- KEEP OLD FETCH_NEARBY_WIND ----------------
def fetch_nearby_wind(station_id):
    url = f"https://api.weather.com/v2/pws/observations/current?stationId={station_id}&format=json&units=e&apiKey=354b43fc8a5e4d7c8b43fc8a5ecd7c56"
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        wind_speed = data["observations"][0]["imperial"]["windSpeed"]
        wind_gust  = data["observations"][0]["imperial"]["windGust"]
        return wind_speed, wind_gust
    except Exception:
        return 0.0, 0.0

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

    month = now_cst.month

    # Temperature
    base_temp = interpolate(start_values["temp_f"], peak_values["temp_f"], factor)
    temp_f = adjust_indoor_temp(base_temp, now_cst, month)

    # Wind
    wind_speed, wind_gust = fetch_nearby_wind(NEARBY_STATION_ID)
    wind_speed = clamp(wind_speed, 0, None)
    wind_gust = clamp(max(wind_gust, wind_speed), 0, None)

    # Other deterministic interpolated values
    rain_in = interpolate(start_values["rain_in"], peak_values["rain_in"], factor)
    daily_rain = interpolate(start_values["daily_rain_in"], peak_values["daily_rain_in"], factor)
    baro_in = interpolate(start_values["baro_in"], peak_values["baro_in"], factor)
    dewpt_f = interpolate(start_values["dewpt_f"], peak_values["dewpt_f"], factor)
    humidity = clamp(100 - (temp_f - dewpt_f) * 2, 0, 100)
    wind_dir = 230 % 360
    clouds = "BKN250"
    weather = "RA"
    software_type = "vws versionxx"
    uv_index = interpolate(start_values["uv_index"], peak_values["uv_index"], factor)
    sol_rad = interpolate(start_values["sol_rad"], peak_values["sol_rad"], factor)

    # URL for Weather Underground
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






