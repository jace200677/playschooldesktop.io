import requests
import random
from datetime import datetime, timedelta
import math

# ---------------- CONFIG ----------------
STATION_ID = "KMNBABBI25"
PASSWORD = "SX8EG38H"

NEARBY_STATION_ID = "KMNBABBI27"
CST_OFFSET = -6

# ---------------- BASE VALUES ----------------
start_values = {
    "temp_f": 65.0,
    "baro_in": 30.30,
    "dewpt_f": 29.0,
}

peak_values = {
    "temp_f": 65.0,
    "baro_in": 30.30,
    "dewpt_f": 29.0,
}


# ---------------- HELPERS ----------------
def clamp(val, min_v=None, max_v=None):
    if min_v is not None and val < min_v:
        return min_v
    if max_v is not None and val > max_v:
        return max_v
    return val

def interpolate(a, b, f):
    return a + (b - a) * f

# ---------------- WEATHER FETCH ----------------
def fetch_nearby_conditions(station_id):
    url = (
        "https://api.weather.com/v2/pws/observations/current"
        f"?stationId={station_id}&format=json&units=e"
        "&apiKey=354b43fc8a5e4d7c8b43fc8a5ecd7c56"
    )
    try:
        r = requests.get(url, timeout=5)
        obs = r.json()["observations"][0]["imperial"]
        return (
            obs.get("windSpeed", 0.0),
            obs.get("windGust", 0.0),
            obs.get("temp", 35.0),
            obs.get("icon", "CLR"),
        )
    except Exception:
        return 0.0, 0.0, 35.0, "CLR"

def indoor_solar_uv(weather, curtains_open, month, hour):
    """
    Calculate indoor solar and UV deterministically.
    - daytime = 6 AM → 6 PM
    - nighttime = else
    """
    # Nighttime
    if hour < 6 or hour >= 18:
        return 0, 0

    # Daytime
    sunny_conditions = ["SUN", "CLR", "FEW"]

    if not curtains_open:
        return 50, 0.2  # curtains closed

    if weather in sunny_conditions:
        # Curtains open + sunny → seasonal brightness
        if month in [6,7,8]:  # summer
            return 12000, 7
        elif month in [3,4,5,9,10,11]:  # spring/fall
            return 9000, 5
        else:  # winter
            return 6000, 3
    else:
        # Curtains open but cloudy/rainy
        return 50, 0.2


# ---------------- HVAC BRAIN ----------------
def adjust_indoor_temp(base_temp, now_cst, month, outdoor_temp):
    temp = base_temp
    weekday = now_cst.weekday()
    is_weekday = weekday <= 4
    is_friday_night = weekday == 4 and now_cst.hour >= 18
    is_weekend = weekday >= 5
    is_winter = month in [12, 1, 2]
    is_warm_season = month in [3, 4, 5, 6, 7, 8, 9, 10, 11]

    heating_allowed = outdoor_temp < 55

    # seasonal drift
    if is_winter:
        temp += 3.5
    elif month in [6, 7, 8]:
        temp += 1.0

    def ramp(sh, sm, eh, em, max_add):
        start = sh * 60 + sm
        end = eh * 60 + em
        now = now_cst.hour * 60 + now_cst.minute
        if now < start or now > end:
            return 0.0
        return max_add * ((now - start) / (end - start))

    # heating failure model
    heating_failure = False
    weak_heating = False
    if heating_allowed:
        roll = random.random()
        if roll < 0.05:
            heating_failure = True
        elif roll < 0.15:
            weak_heating = True

    strength = 0.4 if weak_heating else 1.0

    # heating logic
    if heating_allowed and not heating_failure:
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

    # AC logic
    if is_warm_season and temp >= 80:
        ac_roll = random.random()
        if ac_roll < 0.08:
            pass
        elif ac_roll < 0.18:
            temp -= random.uniform(0.2, 0.6)
        else:
            cool = random.uniform(0.8, 1.6)
            if temp >= 85:
                cool += 0.8
            temp -= cool

    # heating overshoot
    overshoot = 0.0
    if heating_allowed and not heating_failure and temp >= 75:
        if random.random() < 0.25:
            overshoot = random.uniform(0.3, 1.6)

    max_heat = 76.0 + overshoot

    if is_winter:
        return clamp(temp, None, max_heat)
    else:
        return clamp(temp, 70.0, 85.0)


def indoor_air_pressure(outdoor_baromin):
    """
    Deterministic indoor pressure: slight fixed offset from outdoor.
    """
    # Example: indoor slightly higher than outdoor
    return clamp(outdoor_baromin + 0.02, 28.0, 31.0)


# ---------------- DEW POINT CALC ----------------
def dew_point_f(temp_f, rh):
    """
    Calculate indoor dew point in Fahrenheit from temp and RH.
    Works for all seasons.
    """
    temp_c = (temp_f - 32) * 5 / 9
    a = 17.27
    b = 237.7
    alpha = ((a * temp_c) / (b + temp_c)) + math.log(rh / 100.0)
    dew_c = (b * alpha) / (a - alpha)
    dew_f = dew_c * 9 / 5 + 32
    return dew_f


def calculate_indoor_humidity(temp_f, month):
    """
    Estimate indoor humidity for all seasons based on temp and typical ranges.
    Returns %RH
    """
    if month in [12, 1, 2]:  # winter
        base_rh = 30
    elif month in [3, 4, 5, 9, 10, 11]:  # spring/fall
        base_rh = 45
    else:  # summer
        base_rh = 50

    # Adjust for indoor temp drift (warmer → slightly drier)
    rh = base_rh - (temp_f - 70) * 0.5  # each °F above 70 reduces RH a bit
    return clamp(rh, 20, 60)  # limit RH to 20–60%


# ---------------- BEDTIME WIND ----------------
def bedtime_wind(base_wind, now_cst):
    """
    Adjust indoor wind during bedtime windows with ramp to 10 mph.
    """
    weekday = now_cst.weekday()
    hour_min = now_cst.hour * 60 + now_cst.minute
    max_wind = 10.0

    # Weekdays Mon-Thu + Friday morning 8 PM → 5:30 AM
    if weekday <= 4:
        start = 20 * 60  # 8 PM
        end = 29 * 60 + 30  # 5:30 AM next day
        if hour_min < start:
            return base_wind
        elif hour_min <= 24*60:
            factor = (hour_min - start) / (end - start)
            return base_wind + factor * (max_wind - base_wind)
        else:
            factor = (hour_min - 24*60) / (end - 24*60)
            return base_wind + factor * (max_wind - base_wind)

    # Weekends Sat-Sun + Friday night 10 PM → 2 AM
    if weekday == 4 or weekday >= 5:
        if weekday == 4:
            start = 22 * 60
            end = 26 * 60
        else:
            start = 22 * 60
            end = 26 * 60
        if hour_min < start:
            return base_wind
        elif hour_min <= 24*60:
            factor = (hour_min - start) / (end - start)
            return base_wind + factor * (max_wind - base_wind)
        else:
            factor = (hour_min - 24*60) / (end - 24*60)
            return base_wind + factor * (max_wind - base_wind)

    return base_wind

# ---------------- MAIN ----------------
def main():
    now_utc = datetime.utcnow()
    now_cst = now_utc + timedelta(hours=CST_OFFSET)

    time_start = datetime(2026, 1, 30, 18, 54)
    time_peak = datetime(2026, 1, 30, 23, 59)

    if now_cst <= time_start:
        factor = 0.0
    elif now_cst >= time_peak:
        factor = 1.0
    else:
        factor = (now_cst - time_start).total_seconds() / (
            time_peak - time_start
        ).total_seconds()

    wind_speed, wind_gust, outdoor_temp, weather = fetch_nearby_conditions(NEARBY_STATION_ID)

    # Apply bedtime wind logic
    wind_speed = bedtime_wind(wind_speed, now_cst)
    indoor_baro = indoor_air_pressure(start_values['baro_in'])
    base_temp = interpolate(start_values["temp_f"], peak_values["temp_f"], factor)
    temp_f = adjust_indoor_temp(base_temp, now_cst, now_cst.month, outdoor_temp)
    humidity = calculate_indoor_humidity(temp_f, now_cst.month)
    indoor_dew = dew_point_f(temp_f, humidity)


    wind_dir = 230
    rain_in = 0.0
    daily_rain = 0.0
    clouds = "BKN250"
    
    software_type = "vws versionxx"
    CURTAINS_OPEN = False  # Change as needed
    solar_lux, uv_index = indoor_solar_uv(weather, CURTAINS_OPEN, now_cst.month, now_cst.hour)
    # ---------------- PUSH TO WUNDERGROUND ----------------
    URL = (
        "https://weatherstation.wunderground.com/weatherstation/updateweatherstation.php"
        f"?ID={STATION_ID}&PASSWORD={PASSWORD}&dateutc=now"
        f"&winddir={wind_dir}"
        f"&windspeedmph={wind_speed:.1f}"
        f"&windgustmph={wind_gust:.1f}"
        f"&tempf={temp_f:.1f}"
        f"&rainin={rain_in:.2f}"
        f"&dailyrainin={daily_rain:.2f}"
        f"&baromin={indoor_baro:.2f}"
        f"&dewptf={indoor_dew:.1f}"
        f"&humidity={humidity:.0f}"
        f"&weather={weather}&clouds={clouds}"
        f"&uv={uv_index}&solarradiation={solar_lux}"
        f"&softwaretype={software_type}&action=updateraw"
    )

    print("CST:", now_cst.strftime("%Y-%m-%d %H:%M:%S"))
    print(f"Outdoor: {outdoor_temp:.1f}°F | Indoor: {temp_f:.1f}°F")
    print(f"Indoor Humidity: {humidity:.0f}% | Indoor Dew Point: {indoor_dew:.1f}°F")
    print(f"Indoor Wind Speed: {wind_speed:.1f} mph")
    print("Note: Indoor dew point monitoring historically became common around 1957 CE.")
    print("Sending update...")

    try:
        r = requests.get(URL, timeout=10)
        print("Status:", r.status_code)
        print("Response:", r.text)
    except requests.exceptions.RequestException as e:
        print("Send error:", e)

if __name__ == "__main__":
    main()






