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
    
    users = db.get_users_with_location()
    receivers = 0
    for user in users:
        message = f"""
کشاورزان و باغداران عزیز 

✅ جدول پیش‌بینی هواشناسی را با زدن دکمه «<b>🌦 پیش‌بینی هواشناسی</b>» دریافت کنید.
✅ ازین پس جدول پیش بینی به صورت اتوماتیک ارسال نمی‌شود.
✅ اطلاعات هواشناسی حوالی ساعت ۹ صبح هر روز به روز رسانی می‌شود.

راهنمایی: 
@agriiadmin
    """
        try:
            logger.info(f"sending today's data update message to {user}")
            await context.bot.send_message(chat_id=user, 
                                           text=message, 
                                           reply_markup=db.find_start_keyboard(user), 
                                           parse_mode=ParseMode.HTML, 
                                           read_timeout=30, 
                                           write_timeout=30, 
                                           connect_timeout=30)
            logger.info(f"sent today's data update message to {user}")
            username = db.user_collection.find_one({"_id": user})["username"]
            db.set_user_attribute(user, "blocked", False)
            db.log_new_message(
                user_id=user,
                username=username,
                message="پیش‌بینی آب و هوا",
                function="send_weather_report",
            )
            receivers += 1
        except Forbidden:
            db.set_user_attribute(user, "blocked", True)
            logger.info(f"user:{user} has blocked the bot!")
            if datetime.time(5).strftime("%H%M") <= datetime.datetime.now().strftime("%H%M") < datetime.time(19).strftime("%H%M"): 
                context.job_queue.run_once(sms_block, when=datetime.timedelta(minutes=30), chat_id=user, data={})
            else:
                context.job_queue.run_once(sms_block, when=datetime.time(4, 30), chat_id=user, data={}) 
        except BadRequest:
            logger.info(f"user:{user} chat was not found!")            
    
    for admin in admin_list:
        try:
            await context.bot.send_message(
                chat_id=admin, text=f"پیام به {receivers} نفر ارسال شد."
            )
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
