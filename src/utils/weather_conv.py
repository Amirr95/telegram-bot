import logging
from logging.handlers import RotatingFileHandler
import datetime
import jdatetime
import geopandas as gpd
import rasterio
from rasterio.transform import rowcol
import numpy as np
import pandas as pd
from shapely.geometry import Point
from telegram import Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from telegram.error import Forbidden, BadRequest

import os
from itertools import zip_longest
from fiona.errors import DriverError
import warnings
import database
from pg_sync import query_frost_temp, query_frost_wind
from .keyboards import (
    farms_list_reply,
    view_sp_advise_keyboard,
    view_ch_advise_keyboard,
    weather_keyboard
)
from .weather_api import get_weather_report
from .table_generator import weather_table, spring_frost_table
from .message_generator import generate_messages
from telegram.constants import ParseMode

warnings.filterwarnings("ignore", category=UserWarning)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    encoding="utf-8",
    level=logging.INFO,
    handlers=[
        RotatingFileHandler(
            "bot_logs.log", maxBytes=512000, backupCount=5
        ),  # File handler to write logs to a file
        logging.StreamHandler(),  # Stream handler to display logs in the console
    ],
)
logger = logging.getLogger("agriWeather-bot")
logging.getLogger("httpx").setLevel(logging.WARNING)

# Constants for ConversationHandler states

RECV_WEATHER, RECV_SP, RECV_CH, RECV_GDD = range(4)
MENU_CMDS = ['✍️ ثبت نام', '📤 دعوت از دیگران', '🖼 مشاهده کشت‌ها', '➕ اضافه کردن کشت', '🗑 حذف کشت', '✏️ ویرایش کشت‌ها', '🌦 درخواست اطلاعات هواشناسی', '/start', '/stats', '/send', '/set']
###################################################################
####################### Initialize Database #######################
db = database.Database()

# START OF REQUEST WEATHER CONVERSATION
async def req_weather_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "request weather")
    user_farms = db.get_farms(user.id)
    if user_farms:
        await context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return RECV_WEATHER
    else:
        db.log_activity(user.id, "error - no farm for weather report")
        await context.bot.send_message(
            chat_id=user.id,
            text="شما هنوز باغی ثبت نکرده اید",
            reply_markup=db.find_start_keyboard(user.id),
        )
        return ConversationHandler.END
    
async def req_sp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "request sp")
    user_farms = db.get_farms(user.id)
    if user_farms:
        await context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return RECV_SP
    else:
        db.log_activity(user.id, "error - no farm for sp report")
        await context.bot.send_message(
            chat_id=user.id,
            text="شما هنوز باغی ثبت نکرده اید",
            reply_markup=db.find_start_keyboard(user.id),
        )
        return ConversationHandler.END

async def req_ch_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "request ch")
    user_farms = db.get_farms(user.id)
    if user_farms:
        await context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id, pesteh_kar=True),
        )
        return RECV_CH
    else:
        db.log_activity(user.id, "error - no farm for ch report")
        await context.bot.send_message(
            chat_id=user.id,
            text="شما هنوز باغی ثبت نکرده اید",
            reply_markup=db.find_start_keyboard(user.id),
        )
        return ConversationHandler.END

async def req_gdd_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "request gdd")
    if not db.check_if_user_has_pesteh(user.id):
        await context.bot.send_message(
            chat_id=user.id,
            text="شما هنوز باغ پسته‌ای ثبت نکرده‌اید",
            reply_markup=db.find_start_keyboard(user.id),
        )
        return ConversationHandler.END
    else:
        await context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id, pesteh_kar=True),
        )
        return RECV_GDD

async def recv_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    farm = update.message.text
    user_farms = db.get_farms(user.id)
    today = datetime.datetime.now().strftime("%Y%m%d")
    day2 = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y%m%d")
    day3 = (datetime.datetime.now() + datetime.timedelta(days=2)).strftime("%Y%m%d")
    day4 = (datetime.datetime.now() + datetime.timedelta(days=3)).strftime("%Y%m%d")
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y%m%d")
    jtoday = jdatetime.datetime.now().strftime("%Y/%m/%d")
    jday2 = (jdatetime.datetime.now() + jdatetime.timedelta(days=1)).strftime("%Y/%m/%d")
    jday3 = (jdatetime.datetime.now() + jdatetime.timedelta(days=2)).strftime("%Y/%m/%d")
    jday4 = (jdatetime.datetime.now() + jdatetime.timedelta(days=3)).strftime("%Y/%m/%d")
    if farm == '↩️ بازگشت':
        db.log_activity(user.id, "back")
        await update.message.reply_text("عملیات لغو شد", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif farm not in list(user_farms.keys()):
        db.log_activity(user.id, "error - chose farm for weather report" , farm)
        await update.message.reply_text("لطفا دوباره تلاش کنید. نام باغ اشتباه بود", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif farm in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", farm)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    db.log_activity(user.id, "chose farm for weather report", farm)
    longitude = user_farms[farm]["location"]["longitude"]
    latitude = user_farms[farm]["location"]["latitude"]
    
    if longitude is not None:
        if datetime.time(5, 32).strftime("%H%M") <= datetime.datetime.now().strftime("%H%M") < datetime.time(20, 30).strftime("%H%M"):    
            try:
                weather_data = gpd.read_file(f"data/Iran{today}_weather.geojson")
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
                    open_meteo_predictions = db.query_weather_prediction(user.id, farm)
                else:
                    await context.bot.send_message(chat_id=user.id, text="متاسفانه اطلاعات هواشناسی باغ شما در حال حاضر موجود نیست", reply_markup=db.find_start_keyboard(user.id))
                    return ConversationHandler.END
            except DriverError:
                oskooei_predictions = {'tmin': [None], 'tmax': [None], 'rh': [None], 'wind': [None], 'rain': [None]}
                open_meteo_predictions = db.query_weather_prediction(user.id, farm)
        else:
            try:
                weather_data = gpd.read_file(f"data/Iran{yesterday}_weather.geojson")
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
                        'tmin': tmin_values[1:], 'tmax': tmax_values[1:],
                        'rh': rh_values[1:], 'wind': spd_values[1:],
                        'rain': rain_values[1:]
                    }
                    open_meteo_predictions = db.query_weather_prediction(user.id, farm)
                else:
                    await context.bot.send_message(chat_id=user.id, text="متاسفانه اطلاعات هواشناسی باغ شما در حال حاضر موجود نیست", reply_markup=db.find_start_keyboard(user.id))
                    return ConversationHandler.END
            except DriverError:
                oskooei_predictions = {'tmin': [None], 'tmax': [None], 'rh': [None], 'wind': [None], 'rain': [None]}
                open_meteo_predictions = db.query_weather_prediction(user.id, farm)
                # You have created the data (oskooei & OpenMeteo, now process it):
            
        if not open_meteo_predictions:
            farm_document = db.get_farms(user.id)[farm]
            latitude = farm_document.get('location', {}).get('latitude')
            longitude = farm_document.get('location', {}).get('longitude')
            farm_dict = {
                "_id": user.id,
                "farm": farm,
                "location": {"latitude": latitude, "longitude": longitude}
            }
            get_weather_report([farm_dict])
            open_meteo_predictions = db.query_weather_prediction(user.id, farm)
            if not open_meteo_predictions:
                logger.warning(f"{user.id} requested weather prediction for {farm}. OpenMeteo API call was not successful!")
                await context.bot.send_message(chat_id=user.id ,text="متاسفانه اطلاعات باغ شما در حال حاضر موجود نیست. لطفا پس از مدتی دوباره امتحان کنید.", reply_markup=db.find_start_keyboard(user.id))
                return ConversationHandler.END
            
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
پیش‌بینی وضعیت آب و هوای باغ شما با نام <b>#{farm.replace(" ", "_")}</b> در روزهای آینده بدین صورت خواهد بود
"""
        with open('table.png', 'rb') as image_file:
            await context.bot.send_photo(chat_id=user.id, photo=image_file, caption=caption, reply_markup=db.find_start_keyboard(user.id), parse_mode=ParseMode.HTML, read_timeout=15, write_timeout=30)
        os.system("rm table.png")
        username = user.username
        db.log_new_message(
            user_id=user.id,
            username=username,
            message=caption,
            function="req_weather",
            )
        db.log_activity(user.id, "received weather prediction")
        return ConversationHandler.END
                
    elif user_farms[farm].get("link-status") == "To be verified":
        reply_text = "لینک لوکیشن ارسال شده توسط شما هنوز تایید نشده است.\nلطفا تا بررسی ادمین آباد شکیبا باشید."
        await context.bot.send_message(chat_id=user.id, text=reply_text,reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    else:
        await context.bot.send_message(chat_id=user.id, text="موقعیت باغ شما ثبت نشده است. لظفا پیش از درخواست اطلاعات هواشناسی نسبت به ثبت موققعیت اقدام فرمایید.",
                                 reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END

async def recv_sp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    farm = update.message.text
    user_farms = db.get_farms(user.id)
    today = datetime.datetime.now().strftime("%Y%m%d")
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y%m%d")
    day2 = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y%m%d")
    day3 = (datetime.datetime.now() + datetime.timedelta(days=2)).strftime("%Y%m%d")
    jdate = jdatetime.datetime.now().strftime("%Y/%m/%d")
    date_tag = 'امروز'

    if farm == '↩️ بازگشت':
        db.log_activity(user.id, "back")
        await update.message.reply_text("عملیات لغو شد", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif farm not in list(user_farms.keys()):
        db.log_activity(user.id, "error - chose farm for sp report" , farm)
        await update.message.reply_text("لطفا دوباره تلاش کنید. نام باغ اشتباه بود", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif farm in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", farm)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    db.log_activity(user.id, "chose farm for sp report", farm)
    longitude = user_farms[farm]["location"]["longitude"]
    latitude = user_farms[farm]["location"]["latitude"]
    if longitude is not None:
        try:
            if datetime.time(7, 0).strftime("%H%M") <= datetime.datetime.now().strftime("%H%M") < datetime.time(20, 30).strftime("%H%M"):    
                sp_data = gpd.read_file(f"data/Iran{today}_AdviseSP.geojson")
            else:
                sp_data = gpd.read_file(f"data/Iran{yesterday}_AdviseSP.geojson")
                day3 = day2
                day2 = today
                today = yesterday
            # sp_data = gpd.read_file(f"data/pesteh{today}_AdviseSP.geojson")
            point = Point(longitude, latitude)
            threshold = 0.1  # degrees
            idx_min_dist = sp_data.geometry.distance(point).idxmin()
            closest_coords = sp_data.geometry.iloc[idx_min_dist].coords[0]
            if point.distance(Point(closest_coords)) <= threshold:
                row = sp_data.iloc[idx_min_dist]
                sp_3days = [row[f'Time={today}'], row[f'Time={day2}'], row[f'Time={day3}']]
                        # advise_3days_no_nan = ["" for text in advise_3days if pd.isna(text)]
                        # logger.info(f"{advise_3days}\n\n{advise_3days_no_nan}\n----------------------------")
                db.set_user_attribute(user.id, f"farms.{farm}.sp-advise", {"today": sp_3days[0], "day2": sp_3days[1], "day3":sp_3days[2]})
                try:
                    if pd.isna(sp_3days[0]):
                        advise = f"""
باغدار عزیز 
توصیه محلول‌‌پاشی زیر با توجه به وضعیت آب و هوایی باغ شما با نام <b>#{farm.replace(" ", "_")}</b> برای #{date_tag} مورخ <b>{jdate}</b> ارسال می‌شود:

<pre>توصیه‌ای برای این تاریخ موجود نیست</pre>

<i>می‌توانید با استفاده از دکمه‌های زیر توصیه‌‌های مرتبط با فردا و پس‌فردا را مشاهده کنید.</i>
"""
                    else:
                        advise = f"""
باغدار عزیز 
توصیه محلول‌‌پاشی زیر با توجه به وضعیت آب و هوایی باغ شما با نام <b>#{farm.replace(" ", "_")}</b> برای #{date_tag} مورخ <b>{jdate}</b> ارسال می‌شود:

<pre>{sp_3days[0]}</pre>

<i>می‌توانید با استفاده از دکمه‌های زیر توصیه‌‌های مرتبط با فردا و پس‌فردا را مشاهده کنید.</i>
"""
                    await context.bot.send_message(chat_id=user.id, text=advise, reply_markup=view_sp_advise_keyboard(farm), parse_mode=ParseMode.HTML)
                    username = user.username
                    db.log_new_message(
                        user_id=user.id,
                        username=username,
                        message=advise,
                        function="send_advice",
                        )
                    db.log_activity(user.id, "received sp advice")
                except Forbidden:
                    db.set_user_attribute(user.id, "blocked", True)
                    logger.info(f"user:{user.id} has blocked the bot!")
                except BadRequest:
                    logger.info(f"user:{user.id} chat was not found!")
                finally:
                    return ConversationHandler.END
            else:
                await context.bot.send_message(chat_id=user.id, text="متاسفانه باغ شما از محدوده پوشش آباد خارج است.", reply_markup=db.find_start_keyboard(user.id))
                return ConversationHandler.END
        except DriverError:
            logger.info(f"{user.id} requested today's weather. pesteh{today}_AdviseSP.geojson was not found!")
            await context.bot.send_message(chat_id=user.id, text="متاسفانه اطلاعات باغ شما در حال حاضر موجود نیست", reply_markup=db.find_start_keyboard(user.id))
            return ConversationHandler.END
    elif user_farms[farm].get("link-status") == "To be verified":
        reply_text = "لینک لوکیشن ارسال شده توسط شما هنوز تایید نشده است.\nلطفا تا بررسی ادمین آباد شکیبا باشید."
        await context.bot.send_message(chat_id=user.id, text=reply_text,reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    else:
        await context.bot.send_message(chat_id=user.id, text="موقعیت باغ شما ثبت نشده است. لظفا پیش از درخواست اطلاعات هواشناسی نسبت به ثبت موققعیت اقدام فرمایید.",
                                 reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END

async def recv_ch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    farm = update.message.text
    user_farms = db.get_farms(user.id)
    today = datetime.datetime.now().strftime("%Y%m%d")
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y%m%d")
    
    day1 = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y%m%d")
    day2 = (datetime.datetime.now() + datetime.timedelta(days=2)).strftime("%Y%m%d")
    day3 = (datetime.datetime.now() + datetime.timedelta(days=3)).strftime("%Y%m%d")
    
    jdate = (jdatetime.datetime.now() + jdatetime.timedelta(days=1)).strftime("%Y/%m/%d")
    date_tag = 'فردا'

    if farm == '↩️ بازگشت':
        db.log_activity(user.id, "back")
        await update.message.reply_text("عملیات لغو شد", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif farm not in list(user_farms.keys()):
        db.log_activity(user.id, "error - chose farm for ch report" , farm)
        await update.message.reply_text("لطفا دوباره تلاش کنید. نام باغ اشتباه بود", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif farm in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", farm)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    db.log_activity(user.id, "chose farm for ch report", farm)
    longitude = user_farms[farm]["location"]["longitude"]
    latitude = user_farms[farm]["location"]["latitude"]
    if longitude is not None:
        frost_temp = query_frost_temp(latitude, longitude)
        labels = frost_temp.get("labels")
        frost_temp = frost_temp.get("frost-temp")
        frost_wind = query_frost_wind(latitude, longitude).get("frost-wind")
        # frost_temp = [3,2,2,3,2,1,2,3,2,1,2,3]
        # frost_wind = [0,1,2,0,1,2,0,1,2,0,1,2]
        # frost_labels = ["day1", "day2", "day3"]
        # print(labels, "\n", frost_temp, "\n", frost_wind)
        frost_advice = None
        messages = None
        if frost_temp and frost_wind and labels:
            caption = f"""
باغدار عزیز 
پیش‌بینی سرمازدگی بهاره در باغ شما با نام <b>#{farm.replace(" ", "_")}</b> در روزهای آینده بدین صورت خواهد بود
"""
            frost_advice = zip(
                labels,
                frost_temp[::4], frost_wind[::4], frost_temp[1::4], frost_wind[1::4], frost_temp[2::4], frost_wind[2::4], frost_temp[3::4], frost_wind[3::4]
                )
            messages = generate_messages(frost_temp, frost_wind, labels)
            # if messages:
            #     caption = caption + "\n" + "\n".join(messages)
            spring_frost_table(frost_advice=frost_advice, messages=messages)
            with open('frost-table.png', 'rb') as image_file:
                await context.bot.send_photo(chat_id=user.id, photo=image_file, caption=caption, reply_markup=db.find_start_keyboard(user.id), parse_mode=ParseMode.HTML, read_timeout=15, write_timeout=30)
            if messages:
                try:
                    parsed_messages = [f"<pre>{msg}</pre>" for msg in messages]
                    await context.bot.send_message(chat_id=user.id, text="\n".join(parsed_messages), reply_markup=db.find_start_keyboard(user.id), parse_mode=ParseMode.HTML)
                except BadRequest:
                    logger.error("messages were too long")
                    new_messages = [messages[i: i+3] for i in range(0, len(messages), 3)]
                    for message in new_messages:
                        message = [f"<pre>{msg}</pre>" for msg in message]
                        await context.bot.send_message(chat_id=user.id, text="\n".join(message), reply_markup=db.find_start_keyboard(user.id), parse_mode=ParseMode.HTML)
            return ConversationHandler.END
        else:
            logger.info(f"{user.id} requested spring frost advice. Data was not found!")
            await context.bot.send_message(chat_id=user.id, text="متاسفانه اطلاعات باغ شما در حال حاضر موجود نیست", reply_markup=db.find_start_keyboard(user.id))
            return ConversationHandler.END
    elif user_farms[farm].get("link-status") == "To be verified":
        reply_text = "لینک لوکیشن ارسال شده توسط شما هنوز تایید نشده است.\nلطفا تا بررسی ادمین آباد شکیبا باشید."
        await context.bot.send_message(chat_id=user.id, text=reply_text,reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    else:
        await context.bot.send_message(chat_id=user.id, text="موقعیت باغ شما ثبت نشده است. لظفا پیش از درخواست اطلاعات نسبت به ثبت موققعیت اقدام فرمایید.",
                                 reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END

async def recv_gdd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    farm = update.message.text
    user_farms = db.get_farms(user.id)
    today = datetime.datetime.now().strftime("%Y%m%d")
    jdate = (jdatetime.datetime.now() + jdatetime.timedelta(days=1)).strftime("%Y/%m/%d")
    if farm == '↩️ بازگشت':
        db.log_activity(user.id, "back")
        await update.message.reply_text("عملیات لغو شد", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif farm not in list(user_farms.keys()):
        db.log_activity(user.id, "error - chose farm for gdd report" , farm)
        await update.message.reply_text("لطفا دوباره تلاش کنید. نام باغ اشتباه بود", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif not user_farms[farm].get('product', '').startswith('پسته'):
        db.log_activity(user.id, "error - chose a farm that doesn't have pesteh", farm)
        await update.message.reply_text("عملیات لغو شد. این اطلاعات فقط برای باغ‌های پسته موجود است.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif farm in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", farm)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    db.log_activity(user.id, "chose farm for gdd report", farm)
    longitude = user_farms[farm]["location"]["longitude"]
    latitude = user_farms[farm]["location"]["latitude"]
    if longitude is not None:
        try:
            hours = {}
            for method in ["GDD", "GDD2"]:
                with rasterio.open(f"data/Daily_{method}.tif") as src:
                    row, col = rowcol(src.transform, longitude, latitude)
                    pixel_values = []
                    for band in range(1, src.count + 1):
                        pixel_values.append(src.read(band)[row, col])
                pixel_values_filtered = np.array(pixel_values)[~np.isnan(pixel_values)]
                hours[method] = round(sum(pixel_values_filtered))
            
            try:
                msg = f"""
میزان نیاز حرارتی تامین شده برای ظهور شفیره پروانه چوبخوار پسته در باغ شما با نام <b>#{farm.replace(" ", "_")}</b> تا تاریخ <b>{jdate}</b>:
<pre>{hours.get("GDD")} درجه روز</pre>

میزان نیاز حرارتی تامین شده برای حشره بالغ:
<pre>{hours.get("GDD2")} درجه روز</pre>
"""
                await context.bot.send_message(chat_id=user.id, text=msg, reply_markup=db.find_start_keyboard(user.id), parse_mode=ParseMode.HTML)
                username = user.username
                db.log_new_message(
                    user_id=user.id,
                    username=username,
                    message=msg,
                    function="send_advice",
                    )
                db.log_activity(user.id, "received gdd advice")
            except Forbidden:
                db.set_user_attribute(user.id, "blocked", True)
                logger.info(f"user:{user.id} has blocked the bot!")
            except BadRequest:
                logger.info(f"user:{user.id} chat was not found!")
            finally:
                return ConversationHandler.END
            
        except IndexError:
            logger.info(f"{user.id} requested today's gdd data for {farm} which is outside Iran\nLocation:(lat:{latitude}, lng: {longitude})!")
            msg = """
            متاسفانه مکان باغ شما خارج از مناطق تحت پوشش آباد است. شما می‌توانید از مسیر
            <b>بازگشت به خانه --> مدیریت کشت‌ها --> ویرایش کشت‌ها</b> لوکیشن باغ خود را ویرایش کنید.
            """
            await context.bot.send_message(chat_id=user.id, text=msg, reply_markup=db.find_start_keyboard(user.id), parse_mode=ParseMode.HTML)
            return ConversationHandler.END
        except OSError:
            logger.info(f"{user.id} requested today's gdd advice. Geotiff file was not found!")
            await context.bot.send_message(chat_id=user.id, text="متاسفانه اطلاعات باغ شما در حال حاضر موجود نیست", reply_markup=db.find_start_keyboard(user.id))
            return ConversationHandler.END
    elif user_farms[farm].get("link-status") == "To be verified":
        reply_text = "لینک لوکیشن ارسال شده توسط شما هنوز تایید نشده است.\nلطفا تا بررسی ادمین آباد شکیبا باشید."
        await context.bot.send_message(chat_id=user.id, text=reply_text,reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    else:
        await context.bot.send_message(chat_id=user.id, text="موقعیت باغ شما ثبت نشده است. لظفا پیش از درخواست اطلاعات نسبت به ثبت موققعیت اقدام فرمایید.",
                                 reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END



async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات کنسل شد!")
    return ConversationHandler.END   

weather_req_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('🌦 پیش‌بینی هواشناسی'), req_weather_data),
                      MessageHandler(filters.Regex('🧪 شرایط محلول‌پاشی'), req_sp_data),
                      MessageHandler(filters.Regex('⚠️ هشدار سرمازدگی بهاره'), req_ch_data),
                      MessageHandler(filters.Regex('🌡 نیاز حرارتی پروانه چوبخوار'), req_gdd_data)],
        states={
            RECV_WEATHER: [MessageHandler(filters.TEXT , recv_weather)],
            RECV_SP: [MessageHandler(filters.TEXT , recv_sp)],
            RECV_CH: [MessageHandler(filters.TEXT , recv_ch)],
            RECV_GDD: [MessageHandler(filters.TEXT , recv_gdd)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )