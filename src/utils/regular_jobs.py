from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden
from telegram.ext import ContextTypes
import geopandas as gpd
from shapely import Point
from fiona.errors import DriverError

import os
import datetime
import jdatetime
from itertools import zip_longest

import database
from .logger import logger
from .sms_funcs import missing_data_notification, sms_block
from .weather_api import get_weather_report
from .table_generator import weather_table


db = database.Database()

message = """
🟢 Changes:
✅ افزودن پیش‌بینی‌های openMeteoWeather به بات
"""

# Incomplete registration
message_incomplete_reg = """
باغدار عزیز لطفا ثبت‌نام را تکمیل و باغ خود را ثبت کنید تا بتوانیم پیش‌بینی‌های ۴ روزه و توصیه‌های مختص باغ شما را ارسال کنیم.
برای شروع /start را بزنید.
راهنمایی بیشتر:
👉 @agriiadmin
"""
# No farms
message_no_farms = """
باغدار عزیز لطفا اطلاعات باغ خود را ثبت کنید تا بتوانیم توصیه‌های مختص باغ شما را ارسال کنیم.
لطفا /start را بزنید و سپس دکمه «اضافه‌کردن باغ» و اطلاعات خود را وارد کنید.
راهنمایی بیشتر:
👉 @agriiadmin
"""
# No Location
message_no_location = """
باغدار عزیز یک مرحله تا ارسال توصیه مخصوص باغ شما مانده.
لطفا موقعیت باغ خود را با زدن /start و از مسیر «مدیریت باغ» و در ادامه «ویرایش باغ» ویرایش کنید.
راهنمایی بیشتر:
👉 @agriiadmin
"""


admin_list = db.get_admins()

async def register_reminder(context: ContextTypes.DEFAULT_TYPE):
    user_id = context.job.chat_id
    username = context.job.data
    if not db.check_if_user_is_registered(user_id):
        try:
            await context.bot.send_message(chat_id=user_id, text=message_incomplete_reg)           
            db.log_new_message(user_id=user_id,
                           username=username,
                           message=message_incomplete_reg,
                           function="register reminder")
        except Forbidden:
            db.set_user_attribute(user_id, "blocked", True)
            logger.info(f"user:{user_id} has blocked the bot!")
            if datetime.time(5).strftime("%H%M") <= datetime.datetime.now().strftime("%H%M") < datetime.time(19).strftime("%H%M"): 
                context.job_queue.run_once(sms_block, when=datetime.timedelta(minutes=30), chat_id=user_id, data={})
            else:
                context.job_queue.run_once(sms_block, when=datetime.time(4, 30), chat_id=user_id, data={}) 
        except BadRequest:
            logger.info(f"user:{user_id} chat was not found!")

async def no_farm_reminder(context: ContextTypes.DEFAULT_TYPE):
    user_id = context.job.chat_id
    username = context.job.data
    if db.check_if_user_is_registered(user_id) and not db.get_farms(user_id):
        try:
            await context.bot.send_message(chat_id=user_id, text=message_no_farms)           
            db.log_new_message(user_id=user_id,
                            username=username,
                            message=message_no_farms,
                            function="no farm reminder")
        except Forbidden:
            db.set_user_attribute(user_id, "blocked", True)
            logger.info(f"user:{user_id} has blocked the bot!")
            if datetime.time(5).strftime("%H%M") <= datetime.datetime.now().strftime("%H%M") < datetime.time(19).strftime("%H%M"): 
                context.job_queue.run_once(sms_block, when=datetime.timedelta(minutes=30), chat_id=user_id, data={})
            else:
                context.job_queue.run_once(sms_block, when=datetime.time(4, 30), chat_id=user_id, data={}) 
        except BadRequest:
            logger.info(f"user:{user_id} chat was not found!")

async def no_location_reminder(context: ContextTypes.DEFAULT_TYPE):
    user_id = context.job.chat_id
    username = context.job.data
    farms = db.get_farms(user_id)
    if farms:
        if all([farm[1].get('location')['longitude']==None for farm in farms.items()]):
            try:
                await context.bot.send_message(chat_id=user_id, text=message_no_location)           
                db.log_new_message(user_id=user_id,
                                username=username,
                                message=message_no_location,
                                function="no location reminder")
            except Forbidden:
                db.set_user_attribute(user_id, "blocked", True)
                logger.info(f"user:{user_id} has blocked the bot!")
                if datetime.time(5).strftime("%H%M") <= datetime.datetime.now().strftime("%H%M") < datetime.time(19).strftime("%H%M"): 
                    context.job_queue.run_once(sms_block, when=datetime.timedelta(minutes=30), chat_id=user_id, data={})
                else:
                    context.job_queue.run_once(sms_block, when=datetime.time(4, 30), chat_id=user_id, data={}) 
            except BadRequest:
                logger.info(f"user:{user_id} chat was not found!")


async def send_todays_data(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.datetime.now().strftime("%Y%m%d")
    for admin in admin_list:
            time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            try:
                await context.bot.send_message(
                    chat_id=admin,
                    text=f"در حال ارسال پیام به کاربران...",
                )
            except (Forbidden, BadRequest):
                await context.bot.send_message(
                    chat_id=103465015,
                    text=f"admin user {admin} has blocked the bot"
                )
                
    try:         
        weather_data = gpd.read_file(f"data/Iran{today}_weather.geojson")
    except DriverError:
        for admin in admin_list:
            time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            await context.bot.send_message(
                chat_id=admin,
                text=f"{time} file was not found!",
            )
        context.job_queue.run_once(missing_data_notification, when=datetime.timedelta(seconds=5), chat_id=5508856987, data={}, job_kwargs={"misfire_grace_time":3600})
        weather_data = None
    
    farms_list = db.get_farms_with_location() #  [ {_id, farm, location: {latitude, longitude} }, {...}, ...]
    receivers = 0
    fails = {}
    logger.info(farms_list)
    for item in farms_list:
        user_id = item["_id"]
        farm_name = item["farm"]
        latitude = item["location"]["latitude"]
        longitude = item["location"]["longitude"]
        
        if weather_data is not None:
            point = Point(longitude, latitude)
            threshold = 0.1  # degrees
            idx_min_dist = weather_data.geometry.distance(point).idxmin()
            closest_coords = weather_data.geometry.iloc[idx_min_dist].coords[0]
            if point.distance(Point(closest_coords)) <= threshold:
                row = weather_data.iloc[idx_min_dist]
                tmin_values , tmax_values , rh_values , spd_values , rain_values = [], [], [], [], []
                for key, value in row.items():
                    if "tmin_Time=" in key:
                        tmin_values.append(round(value))
                    elif "tmax_Time=" in key:
                        tmax_values.append(round(value))
                    elif "rh_Time=" in key:
                        rh_values.append(round(value))
                    elif "spd_Time=" in key:
                        spd_values.append(round(value))
                    elif "rain_Time=" in key:
                        rain_values.append(round(value))
                oskooei_predictions = {
                    'tmin': tmin_values, 'tmax': tmax_values,
                    'rh': rh_values, 'wind': spd_values,
                    'rain': rain_values
                }
                open_meteo_predictions = db.query_weather_prediction(user_id, farm_name)
        else:
            oskooei_predictions = {'tmin': [None], 'tmax': [None], 'rh': [None], 'wind': [None], 'rain': [None]}
            open_meteo_predictions = db.query_weather_prediction(user_id, farm_name)
        
        if not open_meteo_predictions:
            get_weather_report([item])
            open_meteo_predictions = db.query_weather_prediction(user_id, farm_name)
            if not open_meteo_predictions:
                logger.warning(f"OpenMeteo API call was not successful for {user_id} - {farm_name}")
                fails[user_id] = fails.get(user_id, []) + [farm_name]
                continue
        
        labels, tmax_values, tmin_values, rain_sum_values, snow_sum_values, precip_probability_values, wind_speed_values, wind_direction_values, relative_humidity_values = open_meteo_predictions
        days = [item for item in labels for _ in range(2)]
        source = ['اروپا', 'ایران'] * len(labels)
        tmin = [item for pair in zip_longest(tmin_values, oskooei_predictions['tmin']) for item in pair]
        tmin = [item if item is not None else "--" for item in tmin]
        tmax = [item for pair in zip_longest(tmax_values, oskooei_predictions['tmax']) for item in pair]
        tmax = [item if item is not None else "--" for item in tmax]
        wind_speed = [item for pair in zip_longest(wind_speed_values, oskooei_predictions['wind']) for item in pair]
        wind_speed = [item if item is not None else "--" for item in wind_speed]
        wind_direction = [item for pair in zip_longest(wind_direction_values, oskooei_predictions.get('wind_direction', [])) for item in pair]
        wind_direction = [item if item is not None else "--" for item in wind_direction]
        precip_probability = [item for pair in zip_longest(precip_probability_values, oskooei_predictions.get('precip_prob', [])) for item in pair]
        precip_probability = [item if item is not None else "--" for item in precip_probability]
        rain_sum = [item for pair in zip_longest(rain_sum_values, oskooei_predictions.get('rain', [])) for item in pair]
        rain_sum = [item if item is not None else "--" for item in rain_sum]
        snow_sum = [item for pair in zip_longest(snow_sum_values, oskooei_predictions.get('snow', [])) for item in pair]
        snow_sum = [item if item is not None else "--" for item in snow_sum]
        rh = [item for pair in zip_longest(relative_humidity_values, oskooei_predictions['rh'], ) for item in pair]
        rh = [item if item else "--" for item in rh]
        weather_table(days=days, 
                      source=source, 
                      tmin=tmin, 
                      tmax=tmax, 
                      wind_speed=wind_speed, 
                      wind_direction=wind_direction, 
                      precip_probability=precip_probability, 
                      rain_sum=rain_sum, 
                      snow_sum=snow_sum,
                      rh=rh, 
                      direct_comparisons=len([item for item in oskooei_predictions['tmin'] if item is not None]))
        caption = f"""
    باغدار عزیز 
    پیش‌بینی وضعیت آب و هوای باغ شما با نام <b>#{farm_name.replace(" ", "_")}</b> در روزهای آینده بدین صورت خواهد بود
    """
        try: 
            logger.info(f"sending weather info to {user_id}-{farm_name}")
            with open('table.png', 'rb') as image_file:
                await context.bot.send_photo(chat_id=user_id, photo=image_file, caption=caption, reply_markup=db.find_start_keyboard(user_id), parse_mode=ParseMode.HTML, read_timeout=15, write_timeout=30)
            username = db.user_collection.find_one({"_id": user_id})["username"]
            db.set_user_attribute(user_id, "blocked", False)
            db.log_new_message(
                user_id=user_id,
                username=username,
                message="پیش‌بینی آب و هوا",
                function="send_weather_report",
            )
            logger.info(f"sent todays's weather info to {user_id}")
            receivers += 1
            os.system("rm table.png")
        except Forbidden:
            db.set_user_attribute(user_id, "blocked", True)
            logger.info(f"user:{user_id} has blocked the bot!")
            if datetime.time(5).strftime("%H%M") <= datetime.datetime.now().strftime("%H%M") < datetime.time(19).strftime("%H%M"): 
                context.job_queue.run_once(sms_block, when=datetime.timedelta(minutes=30), chat_id=user_id, data={})
            else:
                context.job_queue.run_once(sms_block, when=datetime.time(4, 30), chat_id=user_id, data={}) 
        except BadRequest:
            logger.info(f"user:{user_id} chat was not found!")            
        except TimeoutError:
            logger.info(f"timeout error for user {user_id}")
            fails[user_id] = fails.get(user_id, []) + [farm_name]
            continue
    
    for admin in admin_list:
        try:
            await context.bot.send_message(
                chat_id=admin, text=f"وضعیت آب و هوای {receivers} باغ ارسال شد"
            )
            if fails:
                await context.bot.send_message(chat_id=admin, text=f"fails:\n{fails}")
        except BadRequest or Forbidden:
            logger.warning(f"admin {admin} has deleted the bot")
                
            

async def send_up_notice(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Sent up notice to admins...")
    for admin in admin_list:
        try:
            await context.bot.send_message(chat_id=admin, text="بات دوباره راه‌اندازی شد"+"\n"+ message)
        except BadRequest or Forbidden:
            logger.warning(f"admin {admin} has deleted the bot")

async def get_member_count(context: ContextTypes.DEFAULT_TYPE):
    members = db.number_of_members()
    blockde_members = db.number_of_blocks()
    member_count = members - blockde_members
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    logger.info(f"Performed member count: {member_count}")
    db.log_member_changes(members=member_count, time=current_time)
