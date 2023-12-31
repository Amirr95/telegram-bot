import database
from .table_generator import table
from .keyboards import view_advise_keyboard
import pandas as pd
import geopandas as gpd
from shapely import Point
import datetime
import jdatetime
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden
from telegram.ext import ContextTypes
from fiona.errors import DriverError
from .logger import logger
from .sms_funcs import missing_data_notification, sms_block

db = database.Database()

message = """
🟢 Changes:
✅ محاسبه نیاز سرمایی
✅ پیامک بلاک
✅ پیامک نرسیدن دیتای روزانه
✅ بزرگتر کردن فونت جداول
✅ تغییرات در متن پیامک‌ها
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
    ids = db.user_collection.distinct("_id")
    today = datetime.datetime.now().strftime("%Y%m%d")
    day2 = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y%m%d")
    day3 = (datetime.datetime.now() + datetime.timedelta(days=2)).strftime("%Y%m%d")
    jdate = jdatetime.datetime.now().strftime("%Y/%m/%d")
    jtomorrow = (jdatetime.datetime.now() + jdatetime.timedelta(days=1)).strftime("%Y/%m/%d")
    jday2 = (jdatetime.datetime.now() + jdatetime.timedelta(days=1)).strftime("%Y/%m/%d")
    jday3 = (jdatetime.datetime.now() + jdatetime.timedelta(days=2)).strftime("%Y/%m/%d")
    jday4 = (jdatetime.datetime.now() + jdatetime.timedelta(days=3)).strftime("%Y/%m/%d")
    villages = pd.read_excel("vilages.xlsx")
    weather_report_receiver_id = []
    weather_report_count = 0
    # advise_post_count = 0             # [ [day1], [day2], [day3] ]
    # advise_post_receiver_id = []  # [ [day1], [day2], [day3] ]
    # advise_pre_count = 0             # [ [day1], [day2], [day3] ]
    # advise_pre_receiver_id = []  # [ [day1], [day2], [day3] ]
    # jdates = [jdate, jday2, jday3]
    # advise_tags = ['امروز', 'فردا', 'پس فردا']
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
        # advise_pre_harvest = gpd.read_file(f"data/pesteh{today}_Advise_Bef.geojson")
        # advise_post_harvest = gpd.read_file(f"data/pesteh{today}_Advise_Aft.geojson")
        weather_data = gpd.read_file(f"data/Iran{today}_weather.geojson")
        # advise_data_tomorrow = gpd.read_file(f"data/pesteh{tomorrow}_2.geojson")
    # advise_data = advise_data.dropna(subset=['Adivse'])
        for id in ids:
            farms = db.get_farms(id)
            if not farms:
                logger.info(f"user {id} has no farms yet.")
            else:
                for farm in farms:
                    try:
                        longitude = farms[farm]["location"]["longitude"]
                        latitude = farms[farm]["location"]["latitude"]
                        if longitude is None and farms[farm]["village"]:
                            province = farms[farm]["province"]
                            city = farms[farm]["city"]
                            village = farms[farm]["village"]
                            row = villages.loc[
                                (villages["ProvincNam"] == province)
                                & (villages["CityName"] == city)
                                & (villages["NAME"] == village)
                            ]
                            if row.empty:
                                longitude = None
                                latitude = None
                            elif not row.empty and len(row) == 1:
                                longitude = row["X"]
                                latitude = row["Y"]
                                logger.info(f"village {village} was found in villages.xlsx, lon:{longitude}, lat: {latitude}")
                        elif longitude is None:
                            logger.info(f"\nLocation of farm:{farm} belonging to user:{id} was not found\n")
                        if latitude is not None and longitude is not None:
                            logger.info(f"Location of farm:{farm} belonging to user:{id} was found")
                            # Find the nearest point to the user's lat/long
                            point = Point(longitude, latitude)
                            threshold = 0.1  # degrees
                            idx_min_dist_weather = weather_data.geometry.distance(point).idxmin()
                            closest_coords_weather = weather_data.geometry.iloc[idx_min_dist_weather].coords[0]
                            # Send weather prediction to every farm
                            if point.distance(Point(closest_coords_weather)) <= threshold:
                                row = weather_data.iloc[idx_min_dist_weather]
                                tmin_values, tmax_values, rh_values, spd_values, rain_values = [], [], [], [], []
                                for key, value in row.items():
                                    if "tmin_Time=" in key:
                                        tmin_values.append(round(value, 1))
                                    elif "tmax_Time=" in key:
                                        tmax_values.append(round(value, 1))
                                    elif "rh_Time=" in key:
                                        rh_values.append(round(value, 1))
                                    elif "spd_Time=" in key:
                                        spd_values.append(round(value, 1))
                                    elif "rain_Time=" in key:
                                        rain_values.append(round(value, 1))
                                caption = f"""
        باغدار عزیز 
        پیش‌بینی وضعیت آب و هوای باغ شما با نام <b>#{farm.replace(" ", "_")}</b> در چهار روز آینده بدین صورت خواهد بود
        """
                                weather_report = f"""
        مقادیر ارسالی 
        وضعیت آب و هوای باغ با نام <{farm}> بین {jdate}-{jday4} بدین صورت بود:
        حداکثر دما: {tmax_values} درجه سانتیگراد
        حداقل دما: {tmin_values} درجه سانتیگراد
        رطوبت نسبی: {rh_values} 
        سرعت باد: {spd_values} کیلومتر بر ساعت
        احتمال بارش: {rain_values} درصد
        """
                                table([jdate, jday2, jday3, jday4], tmin_values, tmax_values, rh_values, spd_values, rain_values, "job-table.png")
                                try:
                                    with open('job-table.png', 'rb') as image_file:
                                        await context.bot.send_photo(chat_id=id, photo=image_file, caption=caption, reply_markup=db.find_start_keyboard(id), parse_mode=ParseMode.HTML)
                                    username = db.user_collection.find_one({"_id": id})["username"]
                                    db.set_user_attribute(id, "blocked", False)
                                    db.log_new_message(
                                        user_id=id,
                                        username=username,
                                        message=weather_report,
                                        function="send_weather_report",
                                    )
                                    logger.info(f"sent todays's weather info to {id}")
                                    weather_report_count += 1
                                    weather_report_receiver_id.append(id)
                                except Forbidden:
                                    db.set_user_attribute(id, "blocked", True)
                                    logger.info(f"user:{id} has blocked the bot!")
                                    if datetime.time(5).strftime("%H%M") <= datetime.datetime.now().strftime("%H%M") < datetime.time(19).strftime("%H%M"): 
                                        context.job_queue.run_once(sms_block, when=datetime.timedelta(minutes=30), chat_id=id, data={})
                                    else:
                                        context.job_queue.run_once(sms_block, when=datetime.time(4, 30), chat_id=id, data={}) 
                                except BadRequest:
                                    logger.info(f"user:{id} chat was not found!")
                            else:
                                logger.info(
                                    f"user's location: ({longitude},{latitude}) | distance in weather file: {point.distance(Point(closest_coords_weather))} > {threshold}"
                                )
                            # Define some Conditions before sending advice:
    #                         if not farms[farm]["product"]:
    #                             continue
    #                         if not farms[farm]["product"].startswith("پسته"):
    #                             continue
    #                         if farms[farm].get("harvest-off"):
    #                             advise_post_count += 1
    #                             advise_post_receiver_id.append(id)
    #                             idx_min_dist_advise = advise_post_harvest.geometry.distance(point).idxmin()
    #                             closest_coords_advise = advise_post_harvest.geometry.iloc[idx_min_dist_advise].coords[0]
    #                             ps_msg = ""
    #                             row = advise_post_harvest.iloc[idx_min_dist_advise]
    #                         elif farms[farm].get("harvest-off") == False or farms[farm].get("harvest-off") == None:
    #                             advise_pre_count += 1
    #                             advise_pre_receiver_id.append(id)
    #                             idx_min_dist_advise = advise_pre_harvest.geometry.distance(point).idxmin()
    #                             closest_coords_advise = advise_pre_harvest.geometry.iloc[idx_min_dist_advise].coords[0]
    #                             ps_msg = "در صورتی که برداشت محصولتان تکمیل شده و تمایل به دریافت روزانه توصیه‌های پس از برداشت دارید از دستور /harvest_off استفاده کرده و باغ خود را انتخاب کنید."
    #                             row = advise_pre_harvest.iloc[idx_min_dist_advise]
    #                         ################################################
    #                         # Send advice to all other farms
    #                         if point.distance(Point(closest_coords_advise)) <= threshold:

    #                             advise_3days = [row[f'Time={today}'], row[f'Time={day2}'], row[f'Time={day3}']]
    #                             # advise_3days_no_nan = ["" for text in advise_3days if pd.isna(text)]
    #                             # logger.info(f"{advise_3days}\n\n{advise_3days_no_nan}\n----------------------------")
    #                             db.set_user_attribute(id, f"farms.{farm}.advise", {"today": advise_3days[0], "day2": advise_3days[1], "day3":advise_3days[2]})
    #                             ############### NEW WAY
    #                             try:
    #                                 if pd.isna(advise_3days[0]):
    #                                     advise = f"""
    # باغدار عزیز 
    # توصیه زیر با توجه به وضعیت آب و هوایی باغ شما با نام <b>#{farm.replace(" ", "_")}</b> برای #{advise_tags[0]} مورخ <b>{jdates[0]}</b> ارسال می‌شود:

    # <pre>توصیه‌ای برای این تاریخ موجود نیست</pre>

    # <i>می‌توانید با استفاده از دکمه‌های زیر توصیه‌‌های مرتبط با فردا و پس‌فردا را مشاهده کنید.</i>

    # ----------------------------------------------------
    # {ps_msg}
    #     """
    #                                 else:
    #                                     advise = f"""
    # باغدار عزیز 
    # توصیه زیر با توجه به وضعیت آب و هوایی باغ شما با نام <b>#{farm.replace(" ", "_")}</b> برای #{advise_tags[0]} مورخ <b>{jdates[0]}</b> ارسال می‌شود:

    # <pre>{advise_3days[0]}</pre>

    # <i>می‌توانید با استفاده از دکمه‌های زیر توصیه‌‌های مرتبط با فردا و پس‌فردا را مشاهده کنید.</i>

    # ----------------------------------------------------
    # {ps_msg}
    #     """
    #                                 await context.bot.send_message(chat_id=id, text=advise, reply_markup=view_advise_keyboard(farm), parse_mode=ParseMode.HTML)
    #                                 username = db.user_collection.find_one({"_id": id})[
    #                                     "username"
    #                                 ]
    #                                 db.log_new_message(
    #                                     user_id=id,
    #                                     username=username,
    #                                     message=advise,
    #                                     function="send_advice",
    #                                     )
    #                                 # advise_count += 1
    #                                 # advise_receiver_id.append(id)
    #                             except Forbidden:
    #                                 db.set_user_attribute(id, "blocked", True)
    #                                 logger.info(f"user:{id} has blocked the bot!")
    #                             except BadRequest:
    #                                 logger.info(f"user:{id} chat was not found!")

                    except KeyError:
                        for admin in admin_list:
                            time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                            await context.bot.send_message(
                                chat_id=admin, text=f"KeyError caused by user: {id} farm: {farm}"
                            )

        db.log_sent_messages(weather_report_receiver_id, "send_weather_report")
        logger.info(f"sent weather report to {weather_report_count} people")

        # db.log_sent_messages(advise_post_receiver_id, "send_post_harvest_advice_to_users")
        # logger.info(f"sent today's post harvest advice to {advise_post_count} people")
        
        # db.log_sent_messages(advise_pre_receiver_id, "send_pre_harvest_advice_to_users")
        # logger.info(f"sent today's pre harvest advice to {advise_pre_count} people")

        for admin in admin_list:
            try:
                await context.bot.send_message(
                    chat_id=admin, text=f"وضعیت آب و هوای {weather_report_count} باغ ارسال شد"
                )
                await context.bot.send_message(chat_id=admin, text=f"{len(set(weather_report_receiver_id))}:\n{weather_report_receiver_id}")


                # await context.bot.send_message(
                #     chat_id=admin, text=f"توصیه پس از برداشت به {advise_post_count} باغ ارسال شد"
                # )
                # await context.bot.send_message(chat_id=admin, text=f"{len(set(advise_post_receiver_id))}:\n{advise_post_receiver_id}")


                # await context.bot.send_message(
                #     chat_id=admin, text=f"توصیه پیش از برداشت به {advise_pre_count} باغ ارسال شد"
                # )
                # await context.bot.send_message(chat_id=admin, text=f"{len(set(advise_pre_receiver_id))}:\n{advise_pre_receiver_id}")

            except BadRequest or Forbidden:
                    logger.warning(f"admin {admin} has deleted the bot")
    except DriverError:
        for admin in admin_list:
            time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            await context.bot.send_message(
                chat_id=admin,
                text=f"{time} file was not found!",
            )
        context.job_queue.run_once(missing_data_notification, when=datetime.timedelta(seconds=5), chat_id=5508856987, data={})
            
            

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
