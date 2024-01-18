import asyncio
import openmeteo_requests
from retry_requests import retry
import datetime as dt
import numpy as np 

from telegram.ext import ContextTypes


from database import Database

db = Database()
located_farms = db.get_farms_with_location()

def get_weather_report(farms: list[dict[str, any]] = located_farms) -> None:
    """
    Get the weather report from openmeteo.org for all farms with location
    """
    retry_session = retry(retries=5, backoff_factor=0.5)
    om = openmeteo_requests.Client(session=retry_session)
    url = "https://api.open-meteo.com/v1/forecast"
    
    for i, farm in enumerate(farms):
        params = {
            "latitude": farm["location"]["latitude"],
            "longitude": farm["location"]["longitude"],
            "hourly": "relative_humidity_2m",
            "daily": ["temperature_2m_max","temperature_2m_min","precipitation_sum","precipitation_probability_max","wind_speed_10m_max","wind_direction_10m_dominant"],
            "timezone": "GMT"
        }
        responses = om.weather_api(url=url, params=params)
        response = responses[0]
        
        hourly = response.Hourly()
        relative_humidity = hourly.Variables(0).ValuesAsNumpy()
        relative_humidity = relative_humidity.reshape((7, 24))
        avg_humidity = np.mean(relative_humidity, axis=1)
        
        daily = response.Daily()
        max_temp = daily.Variables(0).ValuesAsNumpy()
        min_temp = daily.Variables(1).ValuesAsNumpy()
        precipitation_sum = daily.Variables(2).ValuesAsNumpy()
        precipitation_probability = daily.Variables(3).ValuesAsNumpy()
        wind_speed = daily.Variables(4).ValuesAsNumpy()
        wind_direction = daily.Variables(5).ValuesAsNumpy()
        
        avg_humidity = [round(float(x)) for x in avg_humidity]
        max_temp = [round(float(x)) for x in max_temp]
        min_temp = [round(float(x)) for x in min_temp]
        precipitation_sum = [round(float(x)) for x in precipitation_sum]
        precipitation_probability = [round(float(x)) for x in precipitation_probability]
        wind_speed = [round(float(x)) for x in wind_speed]
        wind_direction = [round(float(x)) for x in wind_direction]

        db.load_weather_data(farm["_id"], farm["farm"], dt.datetime.now(), max_temp, min_temp, precipitation_sum, precipitation_probability, wind_speed, wind_direction, avg_humidity)        
                
        
async def load_weather_to_db(context: ContextTypes.DEFAULT_TYPE):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, get_weather_report, located_farms)