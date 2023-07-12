import logging
from logging.handlers import RotatingFileHandler
import datetime
# import jdatetime
import pickle
import geopandas as gpd
from shapely.geometry import Point
import pandas as pd
from telegram import Bot, Location, KeyboardButton, Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, CallbackContext, \
    BasePersistence, ConversationHandler, PicklePersistence, Dispatcher
from telegram.error import BadRequest, Unauthorized, NetworkError
import os
from data_utils import to_excel
# import matplotlib
# matplotlib.use("Agg")
# import matplotlib.pyplot as plt
from fiona.errors import DriverError
import warnings
import database

warnings.filterwarnings("ignore", category=UserWarning)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        RotatingFileHandler('bot_logs.log', maxBytes=512000, backupCount=5),  # File handler to write logs to a file
        logging.StreamHandler()  # Stream handler to display logs in the console
    ]
)
logger = logging.getLogger("agriWeather-bot")

# Constants for ConversationHandler states
BROADCAST = 0
ASK_PROVINCE, ASK_CITY, ASK_VILLAGE, ASK_AREA, ASK_PHONE, ASK_LOCATION, ASK_NAME, HANDLE_NAME = range(8)

TOKEN = os.environ["AGRIWEATHBOT_TOKEN"]

db = database.Database()

REQUIRED_KEYS = ['produce', 'province', 'city', 'area', 'location', 'name', 'phone']
PROVINCES = ['کرمان', 'خراسان رضوی', 'خراسان جنوبی', 'یزد', 'فارس', 'سمنان', 'سایر']
PRODUCTS = ['پسته اکبری', 'پسته اوحدی', 'پسته احمدآقایی', 'پسته بادامی', 'پسته فندقی', 'پسته کله قوچی', 'پسته ممتاز', 'سایر']
ADMIN_LIST = [103465015, 31583686]

def start(update: Update, context: CallbackContext):
    user = update.effective_user
    name = user.username
    # update.message.reply_text(f"id: {user.id}, username: {user.username}")
    # persistence_data = persistence.user_data # {103465015: {'produce': 'محصول 3', 'province': 'استان 4', 'city': 'اردستان', 'area': '۵۴۳۳۴۵۶', 'location': {'latitude': 35.762059, 'longitude': 51.476923}, 'name': 'امیررضا', 'phone': '۰۹۱۳۳۶۴۷۹۹۱'}})
    user_data = context.user_data # {'produce': 'محصول 3', 'province': 'استان 4', 'city': 'اردستان', 'area': '۵۴۳۳۴۵۶', 'location': {'latitude': 35.762059, 'longitude': 51.476923}, 'name': 'امیررضا', 'phone': '۰۹۱۳۳۶۴۷۹۹۱'}
    user_data['username'] = update.effective_user.username
    user_data['blocked'] = False
    user_data['first-seen'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Check if the user has already signed up
    if db.check_if_user_is_signed_up(user.id):
    # if user.id in persistence.user_data:
        if all(key in user_data and user_data[key] for key in REQUIRED_KEYS):
            reply_text = """
ثبت نام شما تکمیل شده است.
در روزهای آینده توصیه‌های کاربردی هواشناسی محصولتان برای شما ارسال می‌شود.
همراه ما باشید.
راه‌های ارتباطی با ما:
ادمین: @agriiadmin
شماره ثابت: 02164063399
        """
            update.message.reply_text(reply_text)
            return ConversationHandler.END
    logger.info(f"{update.effective_user.username} (id: {update.effective_user.id}) started the bot.")
    # reply_text = f"Hello, {user.first_name}! Please provide your ID, phone number, and answer the following questions."
    reply_text = """
باغدار عزیز سلام
از این که به ما اعتماد کردید متشکریم.
برای دریافت توصیه‌های کاربردی هواشناسی از قبیل سرمازدگی، گرمازدگی و آفتاب‌سوختگی، خسارت باد، نیاز سرمایی و … به سوالات پاسخ دهید.
راه‌های ارتباطی با ما:
ادمین: @agriiadmin
تلفن ثابت: 02164063399
                """
    update.message.reply_text(reply_text)
    update.message.reply_text("لطفا نوع محصول خود را انتخاب کنید:", reply_markup=get_produce_keyboard())
    return ASK_PROVINCE


def ask_province(update: Update, context: CallbackContext):
    user_data = context.user_data
    # Get the answer to the province question
    if not update.message.text or update.message.text not in PRODUCTS:
        update.message.reply_text("لطفا نوع محصول خود را انتخاب کنید:", reply_markup=get_produce_keyboard())
        return ASK_PROVINCE
    produce = update.message.text.strip()
    user_data['product'] = produce
    update.message.reply_text("لطفا استان محل باغ خود را انتخاب کنید:", reply_markup=get_province_keyboard())
    return ASK_CITY


def ask_city(update: Update, context: CallbackContext):
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
    user_data = context.user_data

    # Get the answer to the village question
    if not update.message.text or update.message.text=="/start":
        update.message.reply_text("لطفا روستای محل باغ را وارد کنید:", reply_markup=ReplyKeyboardRemove())
        return ASK_AREA
    
    village = update.message.text.strip()
    user_data['village'] = village

    update.message.reply_text("لطفا سطح زیر کشت خود را به هکتار وارد کنید:")
    return ASK_PHONE


def ask_phone(update: Update, context: CallbackContext):
    user_data = context.user_data

    if not update.message.text or update.message.text=="/start":
        update.message.reply_text("لطفا سطح زیر کشت خود را به هکتار وارد کنید:")
        return ASK_PHONE
    
    area = update.message.text.strip()
    user_data['area'] = area

    update.message.reply_text("لطفا شماره تلفن خود را وارد کنید:")
    return ASK_LOCATION


def ask_location(update: Update, context: CallbackContext):
    user_data = context.user_data

    # Get the answer to the area question
    var = update.message.text
    if not var or len(var) != 11 or var=="/start":
        update.message.reply_text("لطفا شماره تلفن خود را وارد کنید:")
        return ASK_LOCATION
    phone = var.strip()
    user_data['phone-number'] = phone

    # persistence.update_user_data(user_id=update.effective_user.id, data = user_data)
    reply_text = "لطفا موقعیت باغ (لوکیشن باغ) خود را بفرستید."
    keyboard = [[KeyboardButton("ارسال لوکیشن آنلاین (الان در باغ هستم)", request_location=True)],
                [KeyboardButton("از نقشه (گوگل مپ) انتخاب میکنم")]]
    update.message.reply_text(reply_text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return ASK_NAME


def ask_name(update: Update, context: CallbackContext):
    user_data = context.user_data
    # update.message.reply_text("Please share your location!")

    # Get the user's location
    location = update.message.location
    if location:
        logger.info(f"{update.effective_user.id} chose: ersal location online")
    text = update.message.text
    # logger.info(f"location: {update.message.location}")
    if not location and text != "از نقشه (گوگل مپ) انتخاب میکنم":
        logger.info(f"{update.effective_user.id} didn't send location successfully")
        reply_text = "لطفا موقعیت باغ (لوکیشن باغ) خود را بفرستید."
        keyboard = [[KeyboardButton("ارسال لوکیشن آنلاین (الان در باغ هستم)", request_location=True)],
                    [KeyboardButton("از نقشه (گوگل مپ) انتخاب میکنم")]]
        update.message.reply_text(reply_text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

        return ASK_NAME
    elif text == "از نقشه (گوگل مپ) انتخاب میکنم":
        logger.info(f"{update.effective_user.id} chose: az google map entekhab mikonam")
        reply_text = """
        مطابق فیلم راهنما موقعیت لوکیشن باغ خود را انتخاب کنید
        
        👉  https://t.me/agriweath/2
        """ 
        update.message.reply_text(reply_text, reply_markup=ReplyKeyboardRemove())
        return ASK_NAME

    user_data['location'] = {
        'latitude': location.latitude,
        'longitude': location.longitude
    }

    update.message.reply_text("نام و نام خانودگی خود را وارد کنید:", reply_markup=ReplyKeyboardRemove())
    return HANDLE_NAME


def handle_name(update: Update, context: CallbackContext):
    user_data = context.user_data

    if not update.message.text or update.message.text=="/start":
        update.message.reply_text("نام و نام خانودگی خود را وارد کنید:")
        return HANDLE_NAME
    
    name = update.message.text.strip()
    user_data['name'] = name
    logger.info(f"{update.effective_user.username} (id: {update.effective_user.id}) Finished sign up.")
    reply_text = """
از ثبت نام شما در بات هواشناسی کشاورزی متشکریم.
در روزهای آینده توصیه‌های کاربردی هواشناسی محصول پسته برای شما ارسال می‌شود.
همراه ما باشید.
راه‌های ارتباطی با ما:
ادمین: @agriiadmin
شماره ثابت: 02164063399
    """
    # persistence.update_user_data(user_id=update.effective_user.id, data = user_data)
    update.message.reply_text(reply_text)
    db.add_new_user(user_id=update.effective_user.id, username=user_data["username"], product=user_data["product"],
                    province=user_data["province"], city=user_data["city"], village=user_data["village"],
                    phone_number=user_data["phone-number"], name=user_data["name"], location=user_data["location"])
    return ConversationHandler.END


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
            db.log_message_to_user(user_id=user_id, message=message)
            i += 1            
        except Unauthorized:
            logger.error(f"user {user_id} blocked the bot")
        except BadRequest:
            logger.error(f"chat with {user_id} not found.")
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
        with open("bot_members_data.pickle", "rb") as f:
            member_count = pickle.load(f)
        # stat.edit_message_text(text=f"تعداد کل اعضا: {member_count['member_count'][-1]}")
        context.bot.send_message(chat_id=id, text=f"تعداد کل اعضا: {member_count['member_count'][-1]}")
    # elif stat.data == "member_count_change":
    #     with open("bot_members_data.pickle", "rb") as f:
    #         data = pickle.load(f)
    #     if len(data['time']) < 15:
    #         pass
    #         plt.plot(data['time'], data['member_count'], 'ro')
    #     else:
    #         pass
    #         # plt.plot(data['time'][-15:], data['member_count'][-15:], 'r-')
    #     # plt.xlabel('Time')
    #     # plt.ylabel('Members')
    #     # plt.title('Bot Members Over Time')
    #     # plt.xticks(rotation=45)
    #     # plt.tight_layout()
    #     # plt.savefig("member-change.png")
    #     # photo = open("member-change.png", "rb")
    #     # context.bot.send_photo(chat_id=id, photo=photo)
    #     # photo.close()
    #     # os.remove("member-change.png")
    elif stat.data == "excel_download":
        input_file="bot_data.pickle"
        output_file="member-data.xlsx"
        to_excel(input_file, output_file)
        doc = open(output_file, 'rb')
        context.bot.send_document(chat_id=id, document=doc)
        doc.close()
        os.remove(output_file)


def stats_keyboard():
    keyboard = [
    [
        InlineKeyboardButton("تعداد اعضا", callback_data='member_count'),
        InlineKeyboardButton("تغییرات تعداد اعضا", callback_data='member_count_change'),
    ],
    [
        InlineKeyboardButton("دانلود فایل اکسل", callback_data='excel_download'),
    ],
]
    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup

def return_keyboard():
    keyboard = ["back"]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
# Function to get the multi-choice keyboard for provinces
def get_province_keyboard():
    keyboard = [['کرمان', 'خراسان رضوی', 'خراسان جنوبی'], ['یزد', 'فارس', 'سمنان'], ['سایر']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)


# Function to get the multi-choice keyboard for produce
def get_produce_keyboard():
    keyboard = [['پسته اکبری', 'پسته اوحدی', 'پسته احمدآقایی'], ['پسته بادامی', 'پسته فندقی', 'پسته کله قوچی'], ['پسته ممتاز', 'سایر']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, input_field_placeholder="salam")


def get_member_count(bot: Bot):
    user_data = db.user_collection.find()
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    member_count = len(user_data)
    try:
        with open("bot_members_data.pickle", "rb") as f:
            data = pickle.load(f)
            logger.info("opened the file")
    except FileNotFoundError:
        data = {'time':[], 'member_count':[]}
        logger.info("file doesn't exist")
    # logger.info(f"old file: {data}")
    data['time'].append(current_time)
    data['member_count'].append(member_count)
    logger.info(f"member count: {member_count}")
    # logger.info(f"new file: {data}")
    with open("bot_members_data.pickle", "wb") as f:
        pickle.dump(data, f)
    # Append new data to DataFrame


def send_advice_to_users(bot: Bot):
    user_data = db.user_collection.find()
    ids = db.user_collection.distinct("_id")
    current_day = datetime.datetime.now().strftime("%Y%m%d")
    villages = pd.read_excel("vilages.xlsx")
    message_count = 0
    receiver_id = []
    try:
        advise_data = gpd.read_file(f"pesteh{current_day}.geojson")
        # advise_data = advise_data.dropna(subset=['Adivse'])
        for id in ids:
            # if user_data[id].get("province") == prov:
            longitude = 61
            latitude = 37.7
            # if id==103465015 or id==350606186:
            #     longitude = 55.64867451
            #     latitude = 30.53236301
            # elif id==117133536:
            #     longitude = 55.834766
            #     latitude = 29.265048
            # elif id==6210067446:  
            #     longitude = 56.7328547
            #     latitude = 30.3160766
            # elif id==147021441:  
            #     longitude = 56.74348157151028
            #     latitude = 30.583021105790174
            # elif user_data[id].get("location"):
            #     longitude = user_data[id]["location"]["longitude"]
            #     latitude = user_data[id]["location"]["latitude"]
            # elif not user_data[id].get("location") and user_data[id].get("village"):
            #     province = user_data[id]["province"]
            #     city = user_data[id]["city"]
            #     village = user_data[id]["village"]
            #     row = villages.loc[(villages["ProvincNam"] == province) & (villages["CityName"] == city) & (villages["NAME"] == village)]
            #     if row.empty:
            #         longitude = None
            #         latitude = None
            #     elif not row.empty and len(row)==1:
            #         longitude = row["X"]
            #         latitude = row["Y"]
            #         logger.info(f"village {village} was found in villages.xlsx")
            # else:
            #     logger.info(f"Location of user:{id} was not found")
            #     latitude = None
            #     longitude = None
            
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
                    باغدار عزیز سلام
                    توصیه زیر با توجه به وضعیت آب و هوایی باغ شما ارسال می‌شود:

                    {advise}
                    """
                    logger.info(message)
                    if pd.isna(advise):
                        logger.info(f"No advice for user {id} with location (long:{longitude}, lat:{latitude}). Closest point in advise data "
                                    f"is index:{idx_min_dist} - {advise_data.iloc[idx_min_dist]['geometry']}")
                    if not pd.isna(advise):
                        try: 
                            # bot.send_message(chat_id=id, location=Location(latitude=latitude, longitude=longitude))
                            bot.send_message(chat_id=id, text=message)
                            db.log_new_message(user_id=id, message=message)
                            logger.info(f"sent recommendation to {id}")
                            message_count += 1
                            receiver_id.append(id)
                            # bot.send_location(chat_id=id, location=Location(latitude=latitude, longitude=longitude))
                        except Unauthorized:
                            logger.info(f"user:{id} has blocked the bot!")
                            for admin in ADMIN_LIST:
                                bot.send_message(chat_id=admin, text=f"user: {id} has blocked the bot!")
                        except BadRequest:
                            logger.info(f"user:{id} chat was not found!")
                else:
                    logger.info(f"user's location: ({longitude},{latitude}) | closest point in dataset: ({closest_coords[0]},{closest_coords[1]}) | distance: {point.distance(Point(closest_coords))}")
        for admin in ADMIN_LIST:
            bot.send_message(chat_id=admin, text=f"توصیه به {message_count} کاربر ارسال شد")
            bot.send_message(chat_id=admin, text=receiver_id)
    except DriverError:
        for admin in ADMIN_LIST:
            time = datetime.datetime.now().strftime("%Y-%m-%d %H:%m")
            bot.send_message(chat_id=admin, text=f"{time} file pesteh{current_day}.geojson was not found!")
    # except:
    #     for admin in ADMIN_LIST:
    #         time = datetime.datetime.now().strftime("%Y-%m-%d %H:%m")
    #         bot.send_message(chat_id=admin, text=f"{time} unexpected error reading pesteh{current_day}.geojson")        
    

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
                # user_data[user_id]["blocked"] = False
                # user_data[user_id]['send-location-date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                i += 1
                
            except Unauthorized:
                logger.info(f"user {user_id} blocked the bot")
                # user_data[user_id]["blocked"] = True
                # user_data[user_id]['block-date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"send_location_data succeeded for {i} out of {len(ids)} users.")
    # with open("location_guide_data.pickle", "wb") as job_data:
    #     pickle.dump(user_data, job_data)
            

def error_handler(update: Update, context: CallbackContext):
    logger.error('Update "%s" caused error "%s"', update, context.error)
def main():
        updater = Updater(TOKEN, use_context=True) # , request_kwargs={'proxy_url': PROXY_URL})

        # Get the dispatcher to register handlers
        dp = updater.dispatcher

        # Add handlers to the dispatcher
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', start)],
            states={
                ASK_PROVINCE: [MessageHandler(Filters.text, ask_province)],
                ASK_CITY: [MessageHandler(Filters.text, ask_city)],
                ASK_VILLAGE: [MessageHandler(Filters.text, ask_village)],
                ASK_AREA: [MessageHandler(Filters.all, ask_area)],
                ASK_PHONE: [MessageHandler(Filters.all, ask_phone)],
                ASK_LOCATION: [MessageHandler(Filters.all, ask_location)],
                ASK_NAME: [MessageHandler(Filters.all, ask_name)],
                HANDLE_NAME: [MessageHandler(Filters.all, handle_name)]
            },
            fallbacks=[CommandHandler('cancel', cancel)]
        )


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

        dp.add_handler(conv_handler)
        dp.add_handler(broadcast_handler)
        # dp.add_handler(CommandHandler("stats", bot_stats, filters=Filters.user))
        # Start the bot
        updater.start_polling()

        # Schedule periodic messages
        job_queue = updater.job_queue
        # job_queue.run_repeating(lambda context: send_scheduled_messages(updater, context, context.bot), 
        #                         interval=datetime.timedelta(seconds=5).total_seconds())
        # job_queue.run_once(lambda context: send_location_guide(updater, context, context.bot), when=60)    
        job_queue.run_repeating(lambda context: get_member_count(context.bot), interval=3600, first=10)
        job_queue.run_repeating(lambda context: send_advice_to_users(context.bot),
                                interval=datetime.timedelta(days=1),
                                first=datetime.timedelta(seconds=20))
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
