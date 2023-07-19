import json
import logging
from logging.handlers import RotatingFileHandler
import datetime
import jdatetime
import geopandas as gpd
from shapely.geometry import Point
import pandas as pd
from telegram import Bot, Location, KeyboardButton, Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, CallbackContext,\
      ConversationHandler, PicklePersistence, Dispatcher
from telegram.error import BadRequest, Unauthorized, NetworkError
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from fiona.errors import DriverError
import warnings
import database
from keyboards import start_keyboard, stats_keyboard, get_product_keyboard, get_province_keyboard, return_keyboard, farms_list
warnings.filterwarnings("ignore", category=UserWarning)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding='utf-8',
    level=logging.INFO,
    handlers=[
        RotatingFileHandler('bot_logs.log', maxBytes=512000, backupCount=5),  # File handler to write logs to a file
        logging.StreamHandler()  # Stream handler to display logs in the console
    ]
)
logger = logging.getLogger("agriWeather-bot")

# Constants for ConversationHandler states
BROADCAST = 0
ASK_PRODUCT, ASK_PROVINCE, ASK_CITY, ASK_VILLAGE, ASK_AREA, ASK_LOCATION, HANDLE_LOCATION = range(7)
EDIT_PROVINCE, EDIT_CITY, EDIT_VILLAGE, EDIT_AREA, EDIT_LOCATION, HANDLE_LOCATION_EDIT = range(6)
ASK_PHONE, HANDLE_PHONE = range(2)

TOKEN = os.environ["AGRIWEATHBOT_TOKEN"]

db = database.Database()
# db.populate_mongodb_from_pickle()
REQUIRED_KEYS = ['products', 'provinces', 'cities', 'villages', 'areas', 'locations', 'name', 'phone-number']
PROVINCES = ['کرمان', 'خراسان رضوی', 'خراسان جنوبی', 'یزد', 'فارس', 'سمنان', 'سایر']
PRODUCTS = ['پسته اکبری', 'پسته اوحدی', 'پسته احمدآقایی', 'پسته بادامی', 'پسته فندقی', 'پسته کله قوچی', 'پسته ممتاز', 'سایر']
ADMIN_LIST = [103465015, 31583686]

def start(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = context.user_data 
    # Check if the user has already signed up
    if not db.check_if_user_exists(user_id=user.id):
        user_data['username'] = user.username
        user_data['blocked'] = False
        db.add_new_user(user_id=user.id, username=user.username)
        logger.info(f"{user.username} (id: {user.id}) started the bot.")
        reply_text = """
باغدار عزیز سلام
از این که به ما اعتماد کردید متشکریم.
برای دریافت توصیه‌های کاربردی هواشناسی از قبیل سرمازدگی، گرمازدگی و آفتاب‌سوختگی، خسارت باد، نیاز سرمایی و … با استفاده
از /register اقدام به ثبت نام کنید.
سپس با /add باغ خود را ثبت کنید.
راه‌های ارتباطی با ما:
ادمین: @agriiadmin
تلفن ثابت: 02164063399
                """
        update.message.reply_text(reply_text, reply_markup=start_keyboard())
        return ASK_PROVINCE
    else:
        reply_text = """
راهنما:
ثبت نام در بات هواشناسی کشاورزی /register
اضافه کردن باغ  /add
ویرایش باغ‌های ثبت شده /edit
حذف باغ /delete
راه‌های ارتباطی با ما:
ادمین: @agriiadmin
شماره ثابت: 02164063399
        """
        update.message.reply_text(reply_text, reply_markup=start_keyboard())
        return ConversationHandler.END 


# def handle_name_old(update: Update, context: CallbackContext):
#     user = update.effective_user
#     user_data = context.user_data
#     if not update.message.text or update.message.text=="/start":
#         update.message.reply_text("نام و نام خانودگی خود را وارد کنید:")
#         return HANDLE_NAME
#     name = update.message.text.strip()
#     user_data['name'] = name
#     db.set_user_attribute(user.id, "name", name)
#     db.set_user_attribute(user.id, "finished-sign-up", datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
#     logger.info(f"{update.effective_user.username} (id: {update.effective_user.id}) Finished sign up.")
#     reply_text = """
# از ثبت نام شما در بات هواشناسی کشاورزی متشکریم.
# در روزهای آینده توصیه‌های کاربردی هواشناسی محصول پسته برای شما ارسال می‌شود.
# همراه ما باشید.
# راه‌های ارتباطی با ما:
# ادمین: @agriiadmin
# شماره ثابت: 02164063399
#     """
#     # persistence.update_user_data(user_id=update.effective_user.id, data = user_data)
#     update.message.reply_text(reply_text)
#     return ConversationHandler.END


def send(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in ADMIN_LIST:    
        update.message.reply_text('لطفا پیام مورد نظرتان را بنویسید یا برای لغو /cancel را بزنید:',)
        return BROADCAST
    else:
        return ConversationHandler.END

def broadcast(update: Update, context: CallbackContext):
    # user_data = db.user_collection.find()
    ids = db.user_collection.distinct("_id")
    i = 0
    receivers = []
    message = update.message.text
    if message == "/cancel":
        update.message.reply_text("عملیات کنسل شد!")
        return ConversationHandler.END
    if not message:
        update.message.reply_text('لطفا پیام مورد نظرتان را بنویسید:',)
        return BROADCAST
    for user_id in ids:    
        try:
            context.bot.send_message(user_id, message)
            username = db.user_collection.find_one( {"_id": user_id} )["username"]
            db.log_new_message(user_id=user_id, username=username, message=message, function="broadcast")
            receivers.append(user_id)
            i += 1            
        except Unauthorized:
            logger.error(f"user {user_id} blocked the bot")
        except BadRequest:
            logger.error(f"chat with {user_id} not found.")
    db.log_sent_messages(receivers, "broadcast")
    for id in ADMIN_LIST:
        context.bot.send_message(id, f"پیام برای {i} نفر از {len(ids)} نفر ارسال شد.")
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("عملیات کنسل شد!")
    return ConversationHandler.END

def bot_stats(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in ADMIN_LIST:    
        update.message.reply_text(
            'آمار مورد نظر را انتخاب کنید',
            reply_markup=stats_keyboard()
        )
    
def button(update: Update, context: CallbackContext):
    stat = update.callback_query
    id = update.effective_user.id
    if stat.data == "member_count":
        member_count = db.bot_collection.find_one()["num-members"][-1]
        context.bot.send_message(chat_id=id, text=f"تعداد کل اعضا: {member_count}")
    elif stat.data == "member_count_change":
        members_doc = db.bot_collection.find_one()
        if len(members_doc['time-stamp']) < 15:
            plt.plot(members_doc['time-stamp'], members_doc['num-members'], 'r-')
        else:
            plt.plot(members_doc['time-stamp'][-15:], members_doc['num-members'][-15:], 'r-')
        plt.xlabel('Time')
        plt.ylabel('Members')
        plt.title('Bot Members Over Time')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig("member-change.png")
        photo = open("member-change.png", "rb")
        context.bot.send_photo(chat_id=id, photo=photo)
        photo.close()
        os.remove("member-change.png")
    elif stat.data == "excel_download":
        output_file="member-data.xlsx"
        db.to_excel(output_file=output_file)
        doc = open(output_file, 'rb')
        context.bot.send_document(chat_id=id, document=doc)
        doc.close()
        os.remove(output_file)

def get_member_count(bot: Bot):
    user_data = db.user_collection.distinct("_id")
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    member_count = len(user_data)
    db.log_member_changes(members=member_count, time=current_time)


def send_advice_to_users(bot: Bot):
    ids = db.user_collection.distinct("_id")
    current_day = datetime.datetime.now().strftime("%Y%m%d")
    villages = pd.read_excel("vilages.xlsx")
    message_count = 0
    receiver_id = []
    try:
        advise_data = gpd.read_file(f"pesteh{current_day}_1.geojson")
        with open("manual_location.json", "r") as f:
            manual_location_data = json.load(f)  
        # advise_data = advise_data.dropna(subset=['Adivse'])
        for id in ids:
            user_document = db.user_collection.find_one( {"_id": id} )
            # if user_data[id].get("province") == prov:
            if str(id) in manual_location_data:
                longitude = manual_location_data[str(id)]['longitude']
                latitude = manual_location_data[str(id)]['latitude']
            elif user_document["locations"][0].get("longitude"):
                logger.info(f"LOCATION: {user_document.get('locations')}")
                longitude = user_document["locations"][0]["longitude"]
                latitude = user_document["locations"][0]["latitude"]
            elif not user_document["locations"][0].get("longitude") and user_document["villages"][0] != '':
                province = user_document["provinces"][0]
                city = user_document["cities"][0]
                village = user_document["villages"][0]
                row = villages.loc[(villages["ProvincNam"] == province) & (villages["CityName"] == city) & (villages["NAME"] == village)]
                if row.empty:
                    longitude = None
                    latitude = None
                elif not row.empty and len(row)==1:
                    longitude = row["X"]
                    latitude = row["Y"]
                    logger.info(f"village {village} was found in villages.xlsx")
            else:
                logger.info(f"Location of user:{id} was not found")
                latitude = None
                longitude = None
            
            if latitude is not None and longitude is not None: 
                logger.info(f"Location of user:{id} was found")
                # Find the nearest point to the user's lat/long
                point = Point(longitude, latitude)
                threshold = 0.1 # degrees
                idx_min_dist = advise_data.geometry.distance(point).idxmin()
                closest_coords = advise_data.geometry.iloc[idx_min_dist].coords[0]
                if point.distance(Point(closest_coords)) <= threshold:
                    logger.info(f"user's location: ({longitude},{latitude}) | closest point in dataset: ({closest_coords[0]},{closest_coords[1]}) | distance: {point.distance(Point(closest_coords))}")
                    advise = advise_data.iloc[idx_min_dist]["Adivse"]
                    message = f"""
باغدار عزیز 
توصیه زیر با توجه به وضعیت آب و هوایی امروز باغ شما ارسال می‌شود:

{advise}
                    """
                    # logger.info(message)
                    if pd.isna(advise):
                        logger.info(f"No advice for user {id} with location (long:{longitude}, lat:{latitude}). Closest point in advise data "
                                    f"is index:{idx_min_dist} - {advise_data.iloc[idx_min_dist]['geometry']}")
                    if not pd.isna(advise):
                        try: 
                            # bot.send_message(chat_id=id, location=Location(latitude=latitude, longitude=longitude))
                            bot.send_message(chat_id=id, text=message)
                            username = db.user_collection.find_one({"_id": id})["username"]
                            db.log_new_message(user_id=id, username=username, message=message, function="send_advice")
                            logger.info(f"sent recommendation to {id}")
                            message_count += 1
                            receiver_id.append(id)
                            # bot.send_location(chat_id=id, location=Location(latitude=latitude, longitude=longitude))
                        except Unauthorized:
                            db.set_user_attribute(id, "blocked", True)
                            logger.info(f"user:{id} has blocked the bot!")
                            for admin in ADMIN_LIST:
                                bot.send_message(chat_id=admin, text=f"user: {id} has blocked the bot!")
                        except BadRequest:
                            logger.info(f"user:{id} chat was not found!")
                else:
                    logger.info(f"user's location: ({longitude},{latitude}) | closest point in dataset: ({closest_coords[0]},{closest_coords[1]}) | distance: {point.distance(Point(closest_coords))}")
        db.log_sent_messages(receiver_id, "send_advice_to_users")
        logger.info(f"sent advice info to {message_count} people")
        for admin in ADMIN_LIST:
            bot.send_message(chat_id=admin, text=f"توصیه به {message_count} کاربر ارسال شد")
            bot.send_message(chat_id=admin, text=receiver_id)
    except DriverError:
        for admin in ADMIN_LIST:
            time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            bot.send_message(chat_id=admin, text=f"{time} file pesteh{current_day}.geojson was not found!")
    except KeyError:
        for admin in ADMIN_LIST:
            time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            bot.send_message(chat_id=admin, text=f"key error in file pesteh{current_day}_1.geojson!")
    

def send_todays_weather(bot: Bot):
    ids = db.user_collection.distinct("_id")
    current_day = datetime.datetime.now().strftime("%Y%m%d")
    jdate = jdatetime.datetime.now().strftime("%Y/%m/%d")
    villages = pd.read_excel("vilages.xlsx")
    message_count = 0
    receiver_id = []
    try:
        advise_data = gpd.read_file(f"pesteh{current_day}_1.geojson")
        with open("manual_location.json", "r") as f:
            manual_location_data = json.load(f)  
        # advise_data = advise_data.dropna(subset=['Adivse'])
        for id in ids:
            user_document = db.user_collection.find_one( {"_id": id} )
            try: 
                user_document["locations"][0].get("longitude")
            except IndexError:
                db.set_user_attribute(id, "locations", {}, array=True)
                logger.info(f"added an empty dict to {id} locations array")
            # if user_data[id].get("province") == prov:
            if str(id) in manual_location_data:
                longitude = manual_location_data[str(id)]['longitude']
                latitude = manual_location_data[str(id)]['latitude']
            elif user_document["locations"][0].get("longitude"):
                logger.info(f"LOCATION: {user_document.get('locations')}")
                longitude = user_document["locations"][0]["longitude"]
                latitude = user_document["locations"][0]["latitude"]
            elif not user_document["locations"][0].get("longitude") and user_document["villages"][0]!='':
                province = user_document["provinces"][0]
                city = user_document["cities"][0]
                village = user_document["villages"][0]
                row = villages.loc[(villages["ProvincNam"] == province) & (villages["CityName"] == city) & (villages["NAME"] == village)]
                if row.empty:
                    longitude = None
                    latitude = None
                elif not row.empty and len(row)==1:
                    longitude = row["X"]
                    latitude = row["Y"]
                    logger.info(f"village {village} was found in villages.xlsx")
            else:
                logger.info(f"Location of user:{id} was not found")
                latitude = None
                longitude = None
            
            if latitude is not None and longitude is not None: 
                logger.info(f"Location of user:{id} was found")
                # Find the nearest point to the user's lat/long
                point = Point(longitude, latitude)
                threshold = 0.1 # degrees
                idx_min_dist = advise_data.geometry.distance(point).idxmin()
                closest_coords = advise_data.geometry.iloc[idx_min_dist].coords[0]
                if point.distance(Point(closest_coords)) <= threshold:
                    logger.info(f"user's location: ({longitude},{latitude}) | closest point in dataset: ({closest_coords[0]},{closest_coords[1]}) | distance: {point.distance(Point(closest_coords))}")
                    tmax = round(advise_data.iloc[idx_min_dist][f"tmax_Time={current_day}"], 2)
                    tmin = round(advise_data.iloc[idx_min_dist][f"tmin_Time={current_day}"], 2)
                    rh = round(advise_data.iloc[idx_min_dist][f"rh_Time={current_day}"], 2)
                    spd = round(advise_data.iloc[idx_min_dist][f"spd_Time={current_day}"], 2)
                    rain = round(advise_data.iloc[idx_min_dist][f"rain_Time={current_day}"], 2)
                    message = f"""
باغدار عزیز سلام
وضعیت آب و هوای باغ شما امروز {jdate} بدین صورت خواهد بود:
حداکثر دما: {tmax} درجه سانتیگراد
حداقل دما: {tmin} درجه سانتیگراد
رطوبت نسبی: {rh} 
سرعت باد: {spd} کیلومتر بر ساعت
احتمال بارش: {rain} درصد
                    """
                    # logger.info(message)
                    # if pd.isna(advise):
                    #     logger.info(f"No advice for user {id} with location (long:{longitude}, lat:{latitude}). Closest point in advise data "
                    #                 f"is index:{idx_min_dist} - {advise_data.iloc[idx_min_dist]['geometry']}")
                    # if not pd.isna(advise):
                    try: 
                        # bot.send_message(chat_id=id, location=Location(latitude=latitude, longitude=longitude))
                        bot.send_message(chat_id=id, text=message)
                        username = db.user_collection.find_one({"_id": id})["username"]
                        db.log_new_message(user_id=id, username=username, message=message, function="send_weather")
                        logger.info(f"sent todays's weather info to {id}")
                        message_count += 1
                        receiver_id.append(id)
                        # bot.send_location(chat_id=id, location=Location(latitude=latitude, longitude=longitude))
                    except Unauthorized:
                        db.set_user_attribute(id, "blocked", True)
                        logger.info(f"user:{id} has blocked the bot!")
                        for admin in ADMIN_LIST:
                            bot.send_message(chat_id=admin, text=f"user: {id} has blocked the bot!")
                    except BadRequest:
                        logger.info(f"user:{id} chat was not found!")
                else:
                    logger.info(f"user's location: ({longitude},{latitude}) | closest point in dataset: ({closest_coords[0]},{closest_coords[1]}) | distance: {point.distance(Point(closest_coords))}")
        db.log_sent_messages(receiver_id, "send_todays_weather")
        logger.info(f"sent todays's weather info to {message_count} people")
        for admin in ADMIN_LIST:
            bot.send_message(chat_id=admin, text=f"وضعیت آب و هوای {message_count} کاربر ارسال شد")
            bot.send_message(chat_id=admin, text=receiver_id)
    except DriverError:
        for admin in ADMIN_LIST:
            time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            bot.send_message(chat_id=admin, text=f"{time} file pesteh{current_day}_1.geojson was not found!")
    except KeyError:
        for admin in ADMIN_LIST:
            time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            bot.send_message(chat_id=admin, text=f"key error in file pesteh{current_day}_1.geojson!")
    
def send_tomorrows_weather(bot: Bot):
    ids = db.user_collection.distinct("_id")
    current_day = datetime.datetime.now().strftime("%Y%m%d")
    tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
    tomorrow = tomorrow.strftime("%Y%m%d")
    jtomorrow = jdatetime.datetime.now() + jdatetime.timedelta(days=1)
    jtomorrow = jtomorrow.strftime("%Y/%m/%d")
    villages = pd.read_excel("vilages.xlsx")
    message_count = 0
    receiver_id = []
    try:
        advise_data = gpd.read_file(f"pesteh{current_day}_1.geojson")
        with open("manual_location.json", "r") as f:
            manual_location_data = json.load(f)  
        # advise_data = advise_data.dropna(subset=['Adivse'])
        for id in ids:
            user_document = db.user_collection.find_one( {"_id": id} )
            # if user_data[id].get("province") == prov:
            if str(id) in manual_location_data:
                longitude = manual_location_data[str(id)]['longitude']
                latitude = manual_location_data[str(id)]['latitude']
            elif user_document["locations"][0].get("longitude"):
                logger.info(f"LOCATION: {user_document.get('locations')}")
                longitude = user_document["locations"][0]["longitude"]
                latitude = user_document["locations"][0]["latitude"]
            elif not user_document["locations"][0].get("longitude") and user_document["villages"][0]!='':
                province = user_document["provinces"][0]
                city = user_document["cities"][0]
                village = user_document["villages"][0]
                row = villages.loc[(villages["ProvincNam"] == province) & (villages["CityName"] == city) & (villages["NAME"] == village)]
                if row.empty:
                    longitude = None
                    latitude = None
                elif not row.empty and len(row)==1:
                    longitude = row["X"]
                    latitude = row["Y"]
                    logger.info(f"village {village} was found in villages.xlsx")
            else:
                logger.info(f"Location of user:{id} was not found")
                latitude = None
                longitude = None
            
            if latitude is not None and longitude is not None: 
                logger.info(f"Location of user:{id} was found")
                # Find the nearest point to the user's lat/long
                point = Point(longitude, latitude)
                threshold = 0.1 # degrees
                idx_min_dist = advise_data.geometry.distance(point).idxmin()
                closest_coords = advise_data.geometry.iloc[idx_min_dist].coords[0]
                if point.distance(Point(closest_coords)) <= threshold:
                    logger.info(f"user's location: ({longitude},{latitude}) | closest point in dataset: ({closest_coords[0]},{closest_coords[1]}) | distance: {point.distance(Point(closest_coords))}")
                    tmax = round(advise_data.iloc[idx_min_dist][f"tmax_Time={tomorrow}"], 2)
                    tmin = round(advise_data.iloc[idx_min_dist][f"tmin_Time={tomorrow}"], 2)
                    rh = round(advise_data.iloc[idx_min_dist][f"rh_Time={tomorrow}"], 2)
                    spd = round(advise_data.iloc[idx_min_dist][f"spd_Time={tomorrow}"], 2)
                    rain = round(advise_data.iloc[idx_min_dist][f"rain_Time={tomorrow}"], 2)
                    message = f"""
باغدار عزیز 
وضعیت آب و هوای باغ شما فردا {jtomorrow} بدین صورت خواهد بود:
حداکثر دما: {tmax} درجه سانتیگراد
حداقل دما: {tmin} درجه سانتیگراد
رطوبت نسبی: {rh} 
سرعت باد: {spd} کیلومتر بر ساعت
احتمال بارش: {rain} درصد
                    """
                    # logger.info(message)
                    # if pd.isna(advise):
                    #     logger.info(f"No advice for user {id} with location (long:{longitude}, lat:{latitude}). Closest point in advise data "
                    #                 f"is index:{idx_min_dist} - {advise_data.iloc[idx_min_dist]['geometry']}")
                    # if not pd.isna(advise):
                    try: 
                        # bot.send_message(chat_id=id, location=Location(latitude=latitude, longitude=longitude))
                        bot.send_message(chat_id=id, text=message)
                        username = db.user_collection.find_one({"_id": id})["username"]
                        db.log_new_message(user_id=id, username=username, message=message, function="send_weather")
                        logger.info(f"sent tomorrow's weather info to {id}")
                        message_count += 1
                        receiver_id.append(id)
                        # bot.send_location(chat_id=id, location=Location(latitude=latitude, longitude=longitude))
                    except Unauthorized:
                        db.set_user_attribute(id, "blocked", True)
                        logger.info(f"user:{id} has blocked the bot!")
                        for admin in ADMIN_LIST:
                            bot.send_message(chat_id=admin, text=f"user: {id} has blocked the bot!")
                    except BadRequest:
                        logger.info(f"user:{id} chat was not found!")
                else:
                    logger.info(f"user's location: ({longitude},{latitude}) | closest point in dataset: ({closest_coords[0]},{closest_coords[1]}) | distance: {point.distance(Point(closest_coords))}")
        db.log_sent_messages(receiver_id, "send_todays_weather")
        logger.info(f"sent tomorrow's weather info to {message_count} people")
        for admin in ADMIN_LIST:
            bot.send_message(chat_id=admin, text=f"وضعیت آب و هوای {message_count} کاربر ارسال شد")
            bot.send_message(chat_id=admin, text=receiver_id)
    except DriverError:
        for admin in ADMIN_LIST:
            time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            bot.send_message(chat_id=admin, text=f"{time} file pesteh{current_day}_1.geojson was not found!")
    except KeyError:
        for admin in ADMIN_LIST:
            time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            bot.send_message(chat_id=admin, text=f"key error in file pesteh{current_day}_1.geojson!")
    

def send_up_notice(bot: Bot):
    for admin in ADMIN_LIST:
        bot.send_message(chat_id=admin, text="بات دوباره راه‌اندازی شد")      
        

# Function to send personalized scheduled messages
def send_location_guide(update: Update, context: CallbackContext, bot: Bot):
    # Retrieve all user data
    ids = db.user_collection.distinct("_id")
    i = 0
    for user_id in ids:
            chat = context.bot.getChat(user_id)
            username = chat.username
            # user_data[user_id]['username'] = username
            # if not "location" in user_data[user_id]:
            message = """
باغدار عزیز برای ارسال توصیه‌های هواشناسی، به لوکیشن (موقعیت جغرافیایی) باغ شما نیاز داریم.
لطفا با ارسال لوکیشن باغ، ثبت نام خود را از طریق /start تکمیل کنید.

برای راهنمایی به @agriiadmin پیام دهید.
                """
            try:
                bot.send_message(user_id, message) ##, parse_mode=telegram.ParseMode.MARKDOWN_V2)
                db.log_new_message(user_id, message)
                # user_data[user_id]["blocked"] = False
                # user_data[user_id]['send-location-date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                i += 1
                
            except Unauthorized:
                logger.info(f"user {user_id} blocked the bot")
                db.set_user_attribute(user_id, "blocked", True)
                # user_data[user_id]["blocked"] = True
                # user_data[user_id]['block-date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"send_location_data succeeded for {i} out of {len(ids)} users.")
    # with open("location_guide_data.pickle", "wb") as job_data:
    #     pickle.dump(user_data, job_data)
            

def error_handler(update: Update, context: CallbackContext):
    logger.error('Update "%s" caused error "%s"', update, context.error)

# START OF REGISTER CONVERSATION
def register(update: Update, context: CallbackContext):
    user = update.effective_user
    if db.check_if_user_is_registered(user_id=user.id):
        update.message.reply_text("شما قبلا ثبت نام کرده‌اید. می‌توانید با استفاده از /add به ثبت باغ‌های خود اقدام کنید")
        return ConversationHandler.END
    logger.info("entered register")
    update.message.reply_text("لطفا نام و نام خانوادگی خود را وارد کنید", reply_markup=ReplyKeyboardRemove())
    return ASK_PHONE

def ask_phone(update: Update, context: CallbackContext):
    logger.info("entered ask_phone")
    user = update.effective_user
    user_data = context.user_data
    # Get the answer to the area question
    if not update.message.text or update.message.text=="/start":
        update.message.reply_text("لطفا نام و نام خانوادگی خود را وارد کنید")
        return ASK_PHONE  
    name = update.message.text.strip()
    user_data['name'] = name
    db.set_user_attribute(user_id=user.id, key="name", value=name)
    # db.set_user_attribute(user.id, 'products', user_data['product'], array=True)
    # db.set_user_attribute(user.id, 'provinces', user_data['province'], array=True)
    # db.set_user_attribute(user.id, 'cities', user_data['city'], array=True)
    # db.set_user_attribute(user.id, 'villages', user_data['village'], array=True)
    # db.set_user_attribute(user.id, 'areas', user_data['area'], array=True)
    update.message.reply_text("لطفا شماره تلفن خود را وارد کنید:")
    return HANDLE_PHONE

def handle_phone(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = context.user_data
    # Get the answer to the area question
    phone = update.message.text
    if not phone or len(phone)!=11 or phone=="/start":
        update.message.reply_text("لطفا شماره تلفن خود را وارد کنید:")
        return HANDLE_PHONE  
    user_data['phone'] = phone
    db.set_user_attribute(user_id=user.id, key="phone-number", value=phone)
    reply_text = """
از ثبت نام شما در بات هواشناسی کشاورزی متشکریم.
لطفا با استفاده از /add نسبت به ثبت باغ‌های خود اقدام کنید.
راه‌های ارتباطی با ما:
ادمین: @agriiadmin
شماره ثابت: 02164063399
    """
    update.message.reply_text(reply_text)
    return ConversationHandler.END

# START OF ADD_FARM CONVERSATION
def add(update: Update, context: CallbackContext):
    user = update.effective_user
    logger.info(db.check_if_user_exists(user.id))
    if not db.check_if_user_is_registered(user_id=user.id):
        update.message.reply_text("لطفا پیش از افزودن باغ از طریق /register ثبت نام کنید", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    reply_text = """
لطفا برای تشخیص این باغ یک نام انتخاب کنید:
مثلا باغ شماره 1
"""
    update.message.reply_text(reply_text, reply_markup=ReplyKeyboardRemove())
    # 
    return ASK_PRODUCT

def ask_product(update: Update, context: CallbackContext): # HANDLES THE NAME RECEIVED FROM USER
    user = update.effective_user
    user_data = context.user_data
    if db.user_collection.find_one({"_id": user.id}).get("farms"):
        used_farm_names = db.user_collection.find_one({"_id": user.id})["farms"].keys()
    if not update.message.text or update.message.text=="/start":
        reply_text = """
لطفا برای دسترسی ساده‌تر به این باغ یک نام انتخاب کنید:
مثلا باغ شماره 1
"""
        update.message.reply_text(reply_text)
        return ASK_PRODUCT
    elif update.message.text in used_farm_names:
        reply_text = "شما قبلا از این نام استفاده کرده‌اید. لطفا یک نام جدید انتخاب کنید."
        update.message.reply_text(reply_text)
        return ASK_PRODUCT
    name = update.message.text.strip()

    user_data['farm_name'] = name
    # db.set_user_attribute(user.id, "name", name)
    # db.set_user_attribute(user.id, "finished-sign-up", datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    # logger.info(f"{update.effective_user.username} (id: {update.effective_user.id}) Finished sign up.")
    update.message.reply_text("لطفا محصول باغ را انتخاب کنید", reply_markup=get_product_keyboard())
    return ASK_PROVINCE

def ask_province(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = context.user_data
    # Get the answer to the province question
    if not update.message.text or update.message.text not in PRODUCTS:
        update.message.reply_text("لطفا محصول باغ را انتخاب کنید", reply_markup=get_product_keyboard())
        return ASK_PROVINCE
    product = update.message.text.strip()
    user_data['product'] = product
    update.message.reply_text("لطفا استان محل باغ خود را انتخاب کنید:", reply_markup=get_province_keyboard())
    return ASK_CITY

def ask_city(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = context.user_data
    # Get the answer to the province question
    if not update.message.text or update.message.text not in PROVINCES:
        update.message.reply_text("لطفا استان محل باغ خود را انتخاب کنید:", reply_markup=get_province_keyboard())
        return ASK_CITY
    province = update.message.text.strip()
    user_data['province'] = province
    update.message.reply_text("لطفا شهرستان محل باغ را وارد کنید:", reply_markup=ReplyKeyboardRemove())
    return ASK_VILLAGE

def ask_village(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = context.user_data
    # Get the answer to the province question
    if not update.message.text or update.message.text=="/start":
        update.message.reply_text("لطفا شهرستان محل باغ را وارد کنید:", reply_markup=ReplyKeyboardRemove())
        return ASK_VILLAGE    
    city = update.message.text.strip()
    user_data['city'] = city
    update.message.reply_text("لطفا روستای محل باغ را وارد کنید:", reply_markup=ReplyKeyboardRemove())
    return ASK_AREA

def ask_area(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = context.user_data
    # Get the answer to the village question
    if not update.message.text or update.message.text=="/start":
        update.message.reply_text("لطفا روستای محل باغ را وارد کنید:", reply_markup=ReplyKeyboardRemove())
        return ASK_AREA 
    village = update.message.text.strip()
    user_data['village'] = village
    update.message.reply_text("لطفا سطح زیر کشت خود را به هکتار وارد کنید:")
    return ASK_LOCATION

def ask_location(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = context.user_data
    # Get the answer to the phone number question
    if not update.message.text or update.message.text=="/start":
        update.message.reply_text("لطفا سطح زیر کشت خود را به هکتار وارد کنید:")
        return ASK_LOCATION  
    area = update.message.text.strip()
    user_data['area'] = area
    reply_text = "لطفا موقعیت باغ (لوکیشن باغ) خود را بفرستید."
    keyboard = [[KeyboardButton("ارسال لوکیشن آنلاین (الان در باغ هستم)", request_location=True)],
                [KeyboardButton("از نقشه (گوگل مپ) انتخاب میکنم")]]
    update.message.reply_text(reply_text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return HANDLE_LOCATION

def handle_location(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = context.user_data
    farm_name = user_data["farm_name"]
    farm_product = user_data["product"]
    farm_province = user_data["province"]
    farm_city = user_data["city"]
    farm_village = user_data["village"]
    farm_area = user_data["area"]
    
    # Get the user's location
    location = update.message.location
    text = update.message.text
    if location:
        logger.info(f"{update.effective_user.id} chose: ersal location online")
        user_data['location'] = {
        'latitude': location.latitude,
        'longitude': location.longitude
    }
        farm_location = user_data["location"]
        new_farm_dict = {
            'product': farm_product,
            'province': farm_province,
            'city': farm_city,
            'village': farm_village,
            'area': farm_area,
            'location': farm_location
        }
        db.add_new_farm(user_id=user.id, farm_name=farm_name, new_farm= new_farm_dict)
        reply_text = f"""
باغ شما با نام <{farm_name}> با موفقیت ثبت شد.
توصیه‌های مرتبط با شرایط آب‌و‌هوایی از روزهای آینده برای شما ارسال خواهد  
برای ویرایش اطلاعات باغ از /edit استفاده کنید.
"""
        update.message.reply_text(reply_text, reply_markup=start_keyboard())
        return ConversationHandler.END
    if not location and text != "از نقشه (گوگل مپ) انتخاب میکنم":
        logger.info(f"{update.effective_user.id} didn't send location successfully")
        reply_text = "ارسال موقعیت باغ (لوکیشن باغ) با موفقیت انجام نشد."
        user_data['location'] = ''
        farm_location = user_data["location"]
        new_farm_dict = {
            'product': farm_product,
            'province': farm_province,
            'city': farm_city,
            'village': farm_village,
            'area': farm_area,
            'location': farm_location
        }
        db.add_new_farm(user_id=user.id, farm_name=farm_name, new_farm= new_farm_dict)
        keyboard = [[KeyboardButton("ارسال لوکیشن آنلاین (الان در باغ هستم)", request_location=True)],
                    [KeyboardButton("از نقشه (گوگل مپ) انتخاب میکنم")]]
        update.message.reply_text(reply_text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return HANDLE_LOCATION
    elif text == "از نقشه (گوگل مپ) انتخاب میکنم":
        logger.info(f"{update.effective_user.id} chose: az google map entekhab mikonam")
        reply_text = """
        مطابق فیلم راهنما موقعیت لوکیشن باغ خود را انتخاب کنید
        
        👉  https://t.me/agriweath/2
        """ 
        update.message.reply_text(reply_text, reply_markup=ReplyKeyboardRemove())
        return HANDLE_LOCATION


def main():
    updater = Updater(TOKEN, use_context=True) # , request_kwargs={'proxy_url': PROXY_URL})

    # Get the dispatcher to register handlers
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("register", register))
    # dp.add_handler(CommandHandler("add", add))
    # Add handlers to the dispatcher
    register_conv = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex('ثبت نام'), register)],
        states={
            ASK_PHONE: [MessageHandler(Filters.text & ~Filters.command, ask_phone)],
            HANDLE_PHONE: [MessageHandler(Filters.text & ~Filters.command, handle_phone)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    dp. add_handler(register_conv)

    add_conv = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex('اضافه کردن باغ'), add)],
        states={
            ASK_PRODUCT: [MessageHandler(Filters.text, ask_product)],
            ASK_PROVINCE: [MessageHandler(Filters.text, ask_province)],
            ASK_CITY: [MessageHandler(Filters.text, ask_city)],
            ASK_VILLAGE: [MessageHandler(Filters.text, ask_village)],
            ASK_AREA: [MessageHandler(Filters.all, ask_area)],
            ASK_LOCATION: [MessageHandler(Filters.all, ask_location)],
            HANDLE_LOCATION: [MessageHandler(Filters.all, handle_location)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    dp.add_handler(add_conv)

    add_conv2 = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex('add'), add)],
        states={
            ASK_PRODUCT: [MessageHandler(Filters.text, ask_product)],
            ASK_PROVINCE: [MessageHandler(Filters.text, ask_province)],
            ASK_CITY: [MessageHandler(Filters.text, ask_city)],
            ASK_VILLAGE: [MessageHandler(Filters.text, ask_village)],
            ASK_AREA: [MessageHandler(Filters.all, ask_area)],
            ASK_LOCATION: [MessageHandler(Filters.all, ask_location)],
            HANDLE_LOCATION: [MessageHandler(Filters.all, handle_location)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    dp.add_handler(add_conv2)

    broadcast_handler = ConversationHandler(
        entry_points=[CommandHandler('send', send)],
        states={
            BROADCAST: [MessageHandler(Filters.all, broadcast)],            
        },
    fallbacks=[CommandHandler('cancel', cancel)]
    )

    dp.add_error_handler(error_handler)

    dp.add_handler(CommandHandler('stats', bot_stats))
    dp.add_handler(CallbackQueryHandler(button))

    dp.add_handler(broadcast_handler)
    # dp.add_handler(CommandHandler("stats", bot_stats, filters=Filters.user))
    # Start the bot
    updater.start_polling()

    # Schedule periodic messages
    job_queue = updater.job_queue
    # job_queue.run_repeating(lambda context: send_scheduled_messages(updater, context, context.bot), 
    #                         interval=datetime.timedelta(seconds=5).total_seconds())
    # job_queue.run_once(lambda context: send_location_guide(updater, context, context.bot), when=60)    
    job_queue.run_repeating(lambda context: get_member_count(context.bot), interval=7200, first=60)
    job_queue.run_repeating(lambda context: send_todays_weather(context.bot),
                            interval=datetime.timedelta(days=1),
                            first=datetime.time(10, 25))
    job_queue.run_repeating(lambda context: send_tomorrows_weather(context.bot),
                            interval=datetime.timedelta(days=1),
                            first=datetime.time(10, 26))
    job_queue.run_repeating(lambda context: send_advice_to_users(context.bot),
                            interval=datetime.timedelta(days=1),
                            first=datetime.time(10, 27))
    job_queue.run_once(lambda context: send_up_notice(context.bot), when=5)
    # Run the bot until you press Ctrl-C or the process receives SIGINT, SIGTERM, or SIGABRT
    updater.idle()
    
if __name__ == '__main__':
    try:
        main()
    except NetworkError:
        logger.error("A network error was encountered!")
    except ConnectionRefusedError:
        logger.error("A ConnectionRefusedError was encountered!")
