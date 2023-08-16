import logging
from logging.handlers import RotatingFileHandler
import datetime
import jdatetime
import geopandas as gpd
from shapely.geometry import Point
from telegram import (
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Updater,
    ApplicationHandlerStop,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    ApplicationBuilder
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden, NetworkError
import os
import requests
import re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from fiona.errors import DriverError
import warnings
import random
import string
import html
import json
import traceback
import database
from regular_jobs import send_todays_data, send_up_notice, get_member_count
from keyboards import (
    start_keyboard,
    stats_keyboard,
    get_product_keyboard,
    get_province_keyboard,
    farms_list_reply,
    edit_keyboard_reply,
    conf_del_keyboard,
    back_button,
    choose_role
)
from table_generator import table


warnings.filterwarnings("ignore", category=UserWarning)

######################### Enable logging ###############################
########################################################################
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

########################################################################
################################ CONVERSATION STATES ###################
CHOOSE_RECEIVERS, HANDLE_IDS, BROADCAST = range(3)
ASK_SS, HANDLE_SS = range(2)
HANDLE_INV_LINK = 0
HANDLE_COUPON = 0
(
    ASK_PRODUCT,
    ASK_PROVINCE,
    ASK_CITY,
    ASK_VILLAGE,
    ASK_AREA,
    ASK_LOCATION,
    HANDLE_LOCATION,
    HANDLE_LINK
) = range(8)
(
    EDIT_PROVINCE,
    EDIT_CITY,
    EDIT_VILLAGE,
    EDIT_AREA,
    EDIT_LOCATION,
    HANDLE_LOCATION_EDIT,
) = range(6)
ASK_FARM_NAME, ASK_LONGITUDE, ASK_LATITUDE, HANDLE_LAT_LONG = range(4)
ASK_PHONE, HANDLE_PHONE = range(2)
VIEW_FARM = range(1)
RECV_WEATHER = range(1)
CHOOSE_ATTR, EDIT_FARM, HANDLE_EDIT, HANDLE_EDIT_LINK = range(4)
CONFIRM_DELETE, DELETE_FARM = range(2)
########################################################################
################################ CONSTANTS #############################
TOKEN = os.environ["AGRIWEATHBOT_TOKEN"]
PAYMENT_PLANS = {"یک ساله - 500000 تومان": "https://packpay.ir/abad",}
INITIAL_PRICE = 500000
PROVINCES = ["کرمان", "خراسان رضوی", "خراسان جنوبی", "یزد", "فارس", "سمنان", "مرکزی", "تهران", "اصفهان", "قزوین", "سیستان و بلوچستان", "قم", "سایر"]
PRODUCTS = [
    "پسته اکبری",
    "پسته اوحدی",
    "پسته احمدآقایی",
    "پسته بادامی",
    "پسته فندقی",
    "پسته کله قوچی",
    "پسته ممتاز",
    "سایر",
]
ADMIN_LIST = [103465015, 31583686, 391763080, 216033407]
MENU_CMDS = ['✍️ ثبت نام', '💰 پرداخت', '✅ ارسال فیش پرداخت', '📤 دعوت از دیگران', '🖼 مشاهده باغ ها', '➕ اضافه کردن باغ', '🗑 حذف باغ ها', '✏️ ویرایش باغ ها', '🌦 درخواست اطلاعات هواشناسی', '/start', '/stats', '/send', '/set']
########################################################################
db = database.Database()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    # Check if the user has already signed up
    if not db.check_if_user_exists(user_id=user.id):
        user_data["username"] = user.username
        user_data["blocked"] = False
        db.add_new_user(user_id=user.id, username=user.username)
        logger.info(f"{user.username} (id: {user.id}) started the bot.")
        reply_text = """
باغدار عزیز سلام
از این که به ما اعتماد کردید متشکریم.
برای دریافت توصیه‌های کاربردی هواشناسی از قبیل سرمازدگی، گرمازدگی و آفتاب‌سوختگی، خسارت باد، نیاز سرمایی و … ابتدا ثبت نام خود را کامل کرده
و سپس باغ های خود را ثبت کنید.
راه‌های ارتباطی با ما:
ادمین: @agriiadmin
تلفن ثابت: 02164063399
                """
        args = context.args
        if args:
            db.log_token_use(user.id, args[0])
        await update.message.reply_text(reply_text, reply_markup=start_keyboard())
        return ConversationHandler.END
    else:
        reply_text = """
باغدار عزیز سلام
از این که به ما اعتماد کردید متشکریم.
برای دریافت توصیه‌های کاربردی هواشناسی از قبیل سرمازدگی، گرمازدگی و آفتاب‌سوختگی، خسارت باد، نیاز سرمایی و … باغ های خد را در بات ثبت کنید.
راه‌های ارتباطی با ما:
ادمین: @agriiadmin
تلفن ثابت: 02164063399
                """
        await update.message.reply_text(reply_text, reply_markup=start_keyboard())
        return ConversationHandler.END


# START OF /send CMD CONVERSATION
async def send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db.log_activity(user_id, "used /send")
    if user_id in ADMIN_LIST:
        await update.message.reply_text(
            "گیرنده پیام کیست؟",
            reply_markup=choose_role()
        )
        return CHOOSE_RECEIVERS
    else:
        db.log_activity(user_id, "used /send", f"{user_id} is not an admin")
        return ConversationHandler.END

async def choose_receivers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # user_data = db.user_collection.find()
    user_data = context.user_data
    user = update.effective_user
    message_text = update.message.text
    if message_text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", message_text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif not message_text:
        await update.message.reply_text(
            "گیرنده پیام کیست؟",
            reply_markup=choose_role()
        )
        return CHOOSE_RECEIVERS
    elif message_text == "/cancel":
        db.log_activity(user.id, "/cancel")
        await update.message.reply_text("عملیات کنسل شد!", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif message_text == "بازگشت":
        db.log_activity(user.id, "back")
        await update.message.reply_text("عملیات کنسل شد!", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif message_text == "تمام کاربران":
        db.log_activity(user.id, "chose /send to all users")
        user_data["receiver_list"] = db.user_collection.distinct("_id")
        user_data["receiver_type"] = "to All Users"
        await update.message.reply_text("لطفا پیام مورد نظرتان را بنویسید یا برای لغو /cancel را بزنید:", 
                                  reply_markup=back_button())
        return BROADCAST
    elif message_text == 'تعیین id': 
        db.log_activity(user.id, "chose /send to custom user list")
        await update.message.reply_text("آیدی کاربران مورد نظر را با یک فاصله وارد کن یا /cancel را بزن. مثلا: \n103465015 1547226 7842159", 
                                  reply_markup=back_button())
        return HANDLE_IDS
    elif message_text == "لوکیشن دار":
        db.log_activity(user.id, "chose /send to users with location")
        users = db.get_users_with_location()
        user_data["receiver_list"] = users
        user_data["receiver_type"] = "to Users With Location"
        await update.message.reply_text("لطفا پیام مورد نظرتان را بنویسید یا برای لغو /cancel را بزنید:", 
                                  reply_markup=back_button())
        return BROADCAST
    elif message_text == "بدون لوکیشن":
        db.log_activity(user.id, "chose /send to users without location")
        users = db.get_users_without_location()
        user_data["receiver_list"] = users
        user_data["receiver_type"] = "to Users W/O Location"
        await update.message.reply_text("لطفا پیام مورد نظرتان را بنویسید یا برای لغو /cancel را بزنید:", 
                                  reply_markup=back_button())
        return BROADCAST
    elif message_text == "بدون شماره تلفن":
        db.log_activity(user.id, "chose /send to users without phone number")
        users = db.get_users_without_phone()
        user_data["receiver_list"] = users
        user_data["receiver_type"] = "to Users W/O Phone Number"
        await update.message.reply_text("لطفا پیام مورد نظرتان را بنویسید یا برای لغو /cancel را بزنید:", 
                                  reply_markup=back_button())
        return BROADCAST
    else:
        db.log_activity(user.id, "invalid receivers chosen")
        await update.message.reply_text("عملیات کنسل شد!", reply_markup=start_keyboard())
        return ConversationHandler.END

async def handle_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ids = update.message.text
    user = update.effective_user
    user_data = context.user_data
    if ids in MENU_CMDS or not ids:
        db.log_activity(user.id, "error - answer in menu_cmd list", ids)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif ids == "بازگشت":
        db.log_activity(user.id, "back")
        await update.message.reply_text("گیرنده پیام را انتخاب کن", reply_markup=choose_role())
        return CHOOSE_RECEIVERS
    else:
        db.log_activity(user.id, "entered custom list of users", ids)
        user_ids = [int(user_id) for user_id in ids.split(" ")]
        user_data["receiver_list"] = user_ids
        user_data["receiver_type"] = "Admin Chose Receivers"
        await update.message.reply_text("لطفا پیام مورد نظرتان را بنویسید یا برای لغو /cancel را بزنید:", 
                                  reply_markup=back_button())
        return BROADCAST

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    user = update.effective_user
    message_text = update.message.text
    message_poll = update.message.poll
    chat_id = update.message.chat_id
    message_id = update.message.message_id
    receiver_list = user_data['receiver_list']
    i = 0
    receivers = []
    if message_text == "/cancel":
        await update.message.reply_text("عملیات کنسل شد!", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif message_text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", message_text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif message_text == "بازگشت":
        await update.message.reply_text(
            "گیرنده پیام کیست؟",
            reply_markup=choose_role()
        )
        return CHOOSE_RECEIVERS
    else:
        for user_id in receiver_list:
            try:
                if message_poll:
                    await context.bot.forward_message(chat_id=user_id, from_chat_id=chat_id, message_id=message_id)
                else:
                    await context.bot.copy_message(chat_id=user_id, from_chat_id=chat_id, message_id=message_id)
                # await context.bot.send_message(user_id, message)
                username = db.user_collection.find_one({"_id": user_id})["username"]
                db.set_user_attribute(user_id, "blocked", False)
                db.log_new_message(
                    user_id=user_id,
                    username=username,
                    message=message_text,
                    function=f"broadcast {user_data['receiver_type']}"
                )
                receivers.append(user_id)
                i += 1
            except Forbidden:
                logger.error(f"user {user_id} blocked the bot")
                await context.bot.send_message(chat_id=user.id, text=f"{user_id} blocked the bot")
                db.set_user_attribute(user_id, "blocked", True)
            except BadRequest:
                logger.error(f"chat with {user_id} not found.")
                await context.bot.send_message(chat_id=user.id, text=f"{user_id} was not found")
        db.log_sent_messages(receivers, f"broadcast {user_data['receiver_type']}")
        for id in ADMIN_LIST:
            await context.bot.send_message(id, f"پیام برای {i} نفر از {len(receiver_list)} نفر ارسال شد."
                                    , reply_markup=start_keyboard())
        return ConversationHandler.END


# START OF /set CMD CONVERSATION
async def set_loc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in ADMIN_LIST:
        await update.message.reply_text("""
لطفا شناسه کاربر مورد نظر را بنویسید یا برای لغو /cancel را بزنید
اگر قصد تعیین لوکیشن بیش از یک کاربر دارید به صورت زیر وارد شود:
10354451
951412545
1594745
""",
        )
        return ASK_FARM_NAME
    else:
        return ConversationHandler.END

async def ask_farm_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    user = update.effective_user
    target_id = update.message.text
    if target_id == "/cancel":
        await update.message.reply_text("عملیات کنسل شد!")
        return ConversationHandler.END
    elif target_id in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", target_id)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif not target_id:
        await update.message.reply_text(
             "لطفا شناسه کاربر مورد نظر را بنویسید یا برای لغو /cancel را بزنید:",
        )
        return ASK_FARM_NAME
    elif len(target_id.split('\n'))==1 and not db.check_if_user_exists(int(target_id)):
        await update.message.reply_text("چنین کاربری در دیتابیس وجود نداشت. دوباره تلاش کنید. \n/cancel")
        return ASK_FARM_NAME
    user_data["target"] = target_id.split("\n")
    await update.message.reply_text("""
نام باغ را واد کنید:
اگر قصد تعیین لوکیشن بیش از یک کاربر دارید به صورت زیر وارد شود:
باغ 1
باغ 2
باغ 3
دقت کنید که دقیقا نام باغ کاربر باشد. حتی اعداد فارسی با انگلیسی جابجا نشود.
""")
    return ASK_LONGITUDE

async def ask_longitude(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    user = update.effective_user
    farm_name = update.message.text
    if len(farm_name.split("\n"))==1:
        farm_names = list(db.get_farms(int(user_data['target'][0])))
        if farm_name not in farm_names:
            await update.message.reply_text(f"نام باغ اشتباه است. دوباره تلاش کنید. \n/cancel")
            return ASK_LONGITUDE
        else:
            await update.message.reply_text(f"مقدار longitude را وارد کنید. \n/cancel")
            user_data["farm_name"] = farm_name
            return ASK_LATITUDE
    elif farm_name == "/cancel":
        await update.message.reply_text("عملیات کنسل شد!")
        return ConversationHandler.END
    elif farm_name in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", farm_name)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif not farm_name:
        await update.message.reply_text(f"نام باغ چیست؟ \n/cancel")
        return ASK_LONGITUDE
    elif len(user_data['target']) != len(farm_name.split('\n')):
        db.log_activity(user.id, "error - farm_name list not equal to IDs", farm_name)
        await update.message.reply_text("تعداد آی‌دی‌ها و نام باغ ها یکسان نیست. لطفا دوباره شروع کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    user_data["farm_name"] = farm_name.split('\n')
    await update.message.reply_text("""
لینک‌های گوگل مپ مرتبط را وارد کنید.
هر لینک در یک خط باشد. تنها لینکهایی که مانند زیر باشند قابل قبول هستند
https://goo.gl/maps/3Nx2zh3pevaz9vf16
""")
    return ASK_LATITUDE

async def ask_latitude(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    user = update.effective_user
    target = user_data["target"]
    farm_name = user_data["farm_name"]
    longitude = update.message.text
    if longitude == "/cancel":
        await update.message.reply_text("عملیات کنسل شد!")
        return ConversationHandler.END
    elif longitude in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", longitude)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif not longitude:
        await update.message.reply_text("""
اگر یک آیدی وارد کردید حالا مقدار longitude را وارد کنید. اگر بیش از یک آیدی داشتید لینک‌های گوگل مپ مرتبط را وارد کنید.
هر لینک در یک خط باشد. تنها لینکهایی که مانند زیر باشند قابل قبول هستند
https://goo.gl/maps/3Nx2zh3pevaz9vf16
""")
        return ASK_LATITUDE
    elif len(target) == 1:
        user_data["long"] = longitude
        await update.message.reply_text(f"what's the latitude of {user_data['target']}?\ndo you want to /cancel ?")
        return HANDLE_LAT_LONG
    else:
        links = longitude.split("\n")
        if len(user_data['target']) != len(links):
            db.log_activity(user.id, "error - links list not equal to IDs", farm_name)
            await update.message.reply_text("تعداد لینک ها و آیدی ها یکسان نیست. لطفا دوباره شروع کنید.", reply_markup=start_keyboard())
            return ConversationHandler.END
        elif not all(link.startswith("https://goo.gl") for link in links):
            db.log_activity(user.id, "error - links not valid", farm_name)
            await update.message.reply_text("لینک ها مورد قبول نیستند. لطفا دوباره شروع کنید.", reply_markup=start_keyboard())
            return ConversationHandler.END
        with requests.session() as s:
            final_url = [s.head(link, allow_redirects=True).url for link in links]
        result = [re.search("/@-?(\d+\.\d+),(\d+\.\d+)", url) for url in final_url]
        for i, user_id in enumerate(user_data['target']):
            try:
                db.set_user_attribute(int(user_id), f"farms.{user_data['farm_name'][i]}.location.latitude", float(result[i].group(1)))
                db.set_user_attribute(int(user_id), f"farms.{user_data['farm_name'][i]}.location.longitude", float(result[i].group(2)))
                await context.bot.send_message(chat_id=int(user_id), text=f"لوکیشن باغ شما با نام {user_data['farm_name'][i]} ثبت شد.")
                await context.bot.send_location(chat_id=int(user_id), latitude=float(result[i].group(1)), longitude=float(result[i].group(2)))
                await context.bot.send_message(chat_id=user.id, text=f"لوکیشن باغ {user_id} با نام {user_data['farm_name'][i]} ثبت شد.")
                await context.bot.send_location(chat_id=user.id, latitude=float(result[i].group(1)), longitude=float(result[i].group(2)))
            except Forbidden:
                await context.bot.send_message(chat_id=user.id, text=f"{user_id} blocked the bot")
                db.set_user_attribute(user_id, "blocked", True)
            except BadRequest:
                await context.bot.send_message(chat_id=user.id, text=f"chat with {user_id} not found. was the user id correct?")
            except KeyError:
                await context.bot.send_message(chat_id=user.id, text=f"{user_id} doesn't have a farm called\n {user_data['farm_name'][i]} \nor user doesn't exist.")
        return ConversationHandler.END

async def handle_lat_long(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    latitude = update.message.text
    if latitude == "/cancel":
        await update.message.reply_text("عملیات کنسل شد!")
        return ConversationHandler.END
    elif latitude in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", latitude)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif not latitude:
        await update.message.reply_text(f"what's the latitude of {latitude}? \ndo you want to /cancel ?")
        return HANDLE_LAT_LONG
    user_data["lat"] = latitude
    db.set_user_attribute(int(user_data["target"][0]), f"farms.{user_data['farm_name']}.location.longitude", float(user_data["long"]))
    db.set_user_attribute(int(user_data["target"][0]), f"farms.{user_data['farm_name']}.location.latitude", float(user_data["lat"]))
    await context.bot.send_location(chat_id=user.id, latitude=float(user_data["lat"]), longitude=float(user_data["long"]))
    await context.bot.send_message(chat_id=int(user_data["target"][0]), text=f"لوکیشن باغ شما با نام {user_data['farm_name']} ثبت شد.")
    await context.bot.send_location(chat_id=int(user_data["target"][0]), latitude=float(user_data["lat"]), longitude=float(user_data["long"]))
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات کنسل شد!")
    return ConversationHandler.END

async def bot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in ADMIN_LIST:
        await update.message.reply_text(
            "آمار مورد نظر را انتخاب کنید", reply_markup=stats_keyboard()
        )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stat = update.callback_query
    id = update.effective_user.id
    if stat.data == "member_count":
        member_count = db.number_of_members() - db.number_of_blocks()
        await context.bot.send_message(chat_id=id, text=f"تعداد اعضا: {member_count}")
    elif stat.data == "member_count_change":
        members_doc = db.bot_collection.find_one()
        if len(members_doc["time-stamp"]) < 15:
            plt.plot(members_doc["time-stamp"], members_doc["num-members"], "r-")
        else:
            plt.plot(
                members_doc["time-stamp"][-15:], members_doc["num-members"][-15:], "r-"
            )
        plt.xlabel("Time")
        plt.ylabel("Members")
        plt.title("Bot Members Over Time")
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig("member-change.png")
        photo = open("member-change.png", "rb")
        await context.bot.send_photo(chat_id=id, photo=photo)
        photo.close()
        os.remove("member-change.png")
    elif stat.data == "excel_download":
        try:
            output_file = "member-data.xlsx"
            db.to_excel(output_file=output_file)
            doc = open(output_file, "rb")
            await context.bot.send_document(chat_id=id, document=doc)
            doc.close()
            os.remove(output_file)
        except:
            logger.info("encountered error during excel download!")
    elif stat.data == "block_count":
        blocked_count = db.number_of_blocks()
        await context.bot.send_message(chat_id=id, text=f"تعداد بلاک‌ها: {blocked_count}")
    elif stat.data == "no_location_count":
        no_location_users = db.get_users_without_location()
        await context.bot.send_message(chat_id=id, text=f"تعداد بدون لوکیشن: {len(no_location_users)}")
    elif stat.data == "no_phone_count":
        no_phone_users = db.get_users_without_phone()
        await context.bot.send_message(chat_id=id, text=f"تعداد بدون شماره تلفن: {len(no_phone_users)}")

# CREATE PERSONALIZED INVITE LINK FOR A USER
async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "chose invite-link menu option")
    random_string = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(10))
    db.set_user_attribute(user.id, "invite-links", random_string, array=True)
    db.add_token(user.id, random_string)
    link = f"https://t.me/agriweathbot?start={random_string}"
    await update.message.reply_text(f"""
می‌توانید از این لینک برای دعوت دوستان خود استفاده کرده و از مزایای آن بهره‌مند شوید:
{link}
""", reply_markup=start_keyboard())

async def invite_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "chose invite-link menu option")
    keyboard = [['مشاهده لینک های قبلی'], ['ایجاد لینک دعوت جدید'], ['بازگشت']]
    await update.message.reply_text("لطفا انتخاب کنید:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True))
    return HANDLE_INV_LINK

async def handle_invite_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = update.message.text
    if message_text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", message_text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif message_text=="بازگشت":
        db.log_activity(user.id, "back")
        await update.message.reply_text("عمیلات قبلی لغو شد.", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif message_text=="مشاهده لینک های قبلی":
        db.log_activity(user.id, "chose to view previous links")
        links = db.get_user_attribute(user.id, "invite-links")
        if links:
            await update.message.reply_text(links, reply_markup=start_keyboard())
            return ConversationHandler.END
        else:
            await update.message.reply_text("شما هنوز لینک دعوت نساخته‌اید.", reply_markup=start_keyboard())
            ConversationHandler.END
    elif message_text=="ایجاد لینک دعوت جدید":
        random_string = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(5))
        db.set_user_attribute(user.id, "invite-links", random_string, array=True)
        link = f"https://t.me/amir_test_bot?start={random_string}"
        await update.message.reply_text(f"""
می‌توانید از این لینک برای دعوت دوستان خود استفاده کرده و از مزایای آن بهره‌مند شوید:
{link}
""", reply_markup=start_keyboard())
        return ConversationHandler.END
    else: 
        db.log_activity(user.id, "error - option not valid", message_text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END


# START OF VIEW CONVERSATION
async def view_farm_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "chose view farms")
    user_farms = db.get_farms(user.id)
    if user_farms:
        await context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return VIEW_FARM
    else:
        await context.bot.send_message(
            chat_id=user.id,
            text="شما هنوز باغی ثبت نکرده اید",
            reply_markup=start_keyboard(),
        )
        return ConversationHandler.END

async def view_farm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    farm = update.message.text
    # farm = f"view{farm}"
    user = update.effective_user
    user_farms = db.get_farms(user.id)
    user_farms_names = list(db.get_farms(user.id).keys())
    if farm in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", farm)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    if farm not in user_farms_names and farm != "↩️ بازگشت":
        db.log_activity(user.id, "error - chose wrong farm to view", farm)
        await context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return VIEW_FARM
    if farm == "↩️ بازگشت":
        db.log_activity(user.id, "back")
        await context.bot.send_message(
            chat_id=user.id, text="عملیات کنسل شد!", reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    if not user_farms[farm].get("location") == {}:
        latitude = user_farms[farm].get("location").get("latitude")
        longitude = user_farms[farm].get("location").get("longitude")
    else:
        latitude = None
        longitude = None
    message_id = update.effective_message.message_id
    try:
        text = f"""
<b>{farm}</b>
محصول باغ: {user_farms[farm].get("product")}
مساحت: {user_farms[farm].get("area")}
آدرس انتخاب شده ⬇️
"""
        await context.bot.send_message(chat_id=user.id, text=text, parse_mode=ParseMode.HTML)
        if latitude and longitude:
            await context.bot.send_location(
                chat_id=user.id,
                latitude=latitude,
                longitude=longitude,
                reply_markup=farms_list_reply(db, user.id),
            )
        else:
            await context.bot.send_message(
                chat_id=user.id,
                text=f"متاسفانه موقعیت <{farm}> ثبت نشده است. "
                "می توانید از طریق گزینه ویرایش باغ موقعیت آن را ثبت کنید.",
                reply_markup=farms_list_reply(db, user.id),
            )
        db.log_activity(user.id, "viewed a farm", farm)
    except KeyError:
        logger.info(f"key {farm} doesn't exist.")
        return ConversationHandler.END


## PAYMENT FUNCS
async def payment_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "chose payment from menu")
    user_data = context.user_data
    keyboard = [[InlineKeyboardButton("درگاه پرداخت", url=PAYMENT_PLANS[key]) for key in list(PAYMENT_PLANS.keys())]]
    code = ''.join(random.choice(string.digits) for _ in range(5))
    user_data["code"] = code
    user_data["payment-message"] = await update.message.reply_text(f"""
می‌توانید از درگاه پرداخت زیر نسبت به خرید اشتراک اقدام کنید.
اگر کد تخفیف دارید با استفاده از دستور /off آن را ثبت کنید.
پس از پرداخت، تصویر پرداخت خود را همراه با کد {code} در بات ثبت کنید.
مبلغ اشتراک یک ساله: 500000 تومان
""",
                                     reply_markup=InlineKeyboardMarkup(keyboard))
    db.log_activity(user.id, "received payment message")
    db.log_payment(user.id, code=code)
    db.set_user_attribute(user.id, "payment-msg-id", user_data["payment-message"]["message_id"])
    db.set_user_attribute(user.id, "used-coupon", False)

# start of /off conversation
async def ask_coupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    pay_message_id = db.get_user_attribute(user.id, "payment-msg-id")
    if not pay_message_id:
        db.log_activity(user.id, "used /off before starting payment process")
        await context.bot.send_message(chat_id=user.id, text="لطفا ابتدا فرایند پرداخت را از منوی بات در /start آغاز کنید")
        return ConversationHandler.END
    else:
        await context.bot.send_message(chat_id=user.id, text="لطفا کد تخفیف خود را وارد کنید:")
        return HANDLE_COUPON

async def handle_coupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    coupon = update.message.text
    if not coupon:
        await context.bot.send_message(chat_id=user.id, text="ثبت کد تخفیف ناموفق بود. می‌توانید دوباره امتحان کنید /off")
        db.log_activity(user.id, "error - coupon message has no text")
        return ConversationHandler.END
    elif coupon in MENU_CMDS:
        db.log_activity(user.id, "error - coupon in menu_cmd list", coupon)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif db.verify_coupon(coupon):
        if not db.get_user_attribute(user.id, "used-coupon"):
            db.set_user_attribute(user.id, "used-coupon", True)
            db.log_activity(user.id, "used a coupon", coupon)
            final_price = db.apply_coupon(coupon, INITIAL_PRICE)
            keyboard = [[InlineKeyboardButton("درگاه پرداخت", url=PAYMENT_PLANS[key]) for key in list(PAYMENT_PLANS.keys())]]
            code = user_data["code"]
            db.add_coupon_to_payment_dict(user.id, code, coupon)
            db.modify_final_price_in_payment_dict(user.id, code, final_price)
            await context.bot.edit_message_text(chat_id=user.id, 
                                                message_id=user_data.get("payment-message")["message_id"],
                                                parse_mode=ParseMode.HTML,
                                                reply_markup= InlineKeyboardMarkup(keyboard),
                                                text=f"""
می‌توانید از درگاه پرداخت زیر نسبت به خرید اشتراک اقدام کنید.
اگر کد تخفیف دارید با استفاده از دستور /off آن را ثبت کنید.
پس از پرداخت، تصویر پرداخت خود را همراه با کد {code} در بات ثبت کنید.
<s> اشتراک یک ساله: 500000 تومان</s>
 اشتراک یک ساله: {final_price} تومان
""")
            await context.bot.send_message(chat_id=user.id, text="تخفیف اعمال شد", 
                                        reply_to_message_id=db.get_user_attribute(user.id, "payment-msg-id"))
            return ConversationHandler.END
        else:
            await context.bot.send_message(chat_id=user.id, text="شما قبلا از کد تخفیف استفاده کرده‌اید.")
    else:
        await context.bot.send_message(chat_id=user.id, text="کد تخفیف معتبر نیست")
        return ConversationHandler.END

############ start of payment verification conversation ##################
async def ask_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg_id = db.get_user_attribute(user.id, "payment-msg-id")
    await context.bot.send_message(chat_id=user.id, text="لطفا کد پرداخت موجود در پیام را وارد کنید.",
                                   reply_to_message_id=msg_id)
    return ASK_SS

async def ask_ss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    code = update.message.text
    payments = db.get_user_attribute(user.id, "payments")
    all_codes = [payment['code'] for payment in payments]
    if not payments:
        await context.bot.send_message(chat_id=user.id, text="لطفا ابتدا نسبت به پرداخت اقدام کنید.")
        return ConversationHandler.END
    elif not code or code in MENU_CMDS:
        db.log_activity(user.id, "error - payment code in menu_cmd list", code)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif code not in all_codes:
        await context.bot.send_message(chat_id=user.id, text="کد وارد شده اشتباه است.")
        return ConversationHandler.END
    else:
        await context.bot.send_message(chat_id=user.id, text="لطفا تصویر مبلغ پرداختی خود را ارسال فرمایید")
        user_data["verification-code"] = code
        return HANDLE_SS
    
async def handle_ss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    ss = update.message.photo
    text = update.message.text
    if text in MENU_CMDS:
        db.log_activity(user.id, "error - text in menu_cmd list", text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif not ss:
        db.log_activity(user.id, "error - no screenshot")
        await update.message.reply_text("تصویری دریافت نشد. در صورت تمایل دوباره از دکمه ارسال فیش استفاده کنید", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif ss:
        db.log_activity(user.id, "sent screenshot")
        message_id = update.message.message_id
        await update.message.reply_text("تصویر فیش شما دریافت شد. لطفا در انتظار تایید ادمین بمانید. نتیجه بررسی به شما اعلام خواهد شد.", reply_markup=start_keyboard())
        for admin in ADMIN_LIST:
            await context.bot.send_message(chat_id=admin, text=f"""درخواست تایید پرداخت:
user: {user.id} 
username: {user.username}
code: {user_data["verification-code"]}
final price: {db.get_final_price(user.id, user_data["verification-code"])}
""" )
            await context.bot.forward_message(chat_id=admin,
                                              from_chat_id=user.id,
                                              message_id=message_id)
        return ConversationHandler.END
    else:
        db.log_activity(user.id, "error - no valid input")
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END

async def verify_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    if user.id in ADMIN_LIST:
        if not args or len(args) != 2:
            await context.bot.send_message(chat_id=user.id, text="""
نحوه استفاده:
/verify userID paymentCode
example:
/verify 103465015 12345
""")
        else:
            db.verify_payment(int(args[0]), args[1])
            await context.bot.send_message(chat_id=user.id, text="پرداخت کاربر تایید شد.")
            await context.bot.send_message(chat_id=int(args[0]), text="پرداخت شما با موفقیت تایید شد. از اعتماد شما متشکریم.")


async def create_coupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user.id in ADMIN_LIST:
        return ApplicationHandlerStop
    args = context.args
    if not len(args)==2:
        await context.bot.send_message(chat_id=user.id, text="""
نحوه استفاده:
/coupon text value(toman)
مثلا کد تخفیف off-eslami به ارزش 50000 تومن اینجوری درست میشه:
/coupon off-eslami 50000
""")
    else:
        if db.save_coupon(args[0], args[1]):
            await context.bot.send_message(chat_id=user.id, text=f"{args[0]} {args[1]} was saved.")
        else:
            await context.bot.send_message(chat_id=user.id, text="کد تکراری بود")
# START OF EDIT CONVERSATION
async def edit_farm_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "start edit")
    user_farms = db.get_farms(user.id)
    if user_farms:
        # await context.bot.send_message(chat_id=user.id, text="یکی از باغ های خود را ویرایش کنید", reply_markup=farms_list(db, user.id, view=False, edit=True))
        await context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را ویرایش کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CHOOSE_ATTR
    else:
        await context.bot.send_message(
            chat_id=user.id,
            text="شما هنوز باغی ثبت نکرده اید",
            reply_markup=start_keyboard(),
        )
        return ConversationHandler.END

async def choose_attr_to_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # farm = update.callback_query.data
    farm = update.message.text

    user = update.effective_user
    user_data = context.user_data
    user_data["selected_farm"] = farm
    user_farms = list(db.get_farms(user.id).keys())
    if farm in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", farm)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    if farm not in user_farms and farm != "↩️ بازگشت":
        db.log_activity(user.id, "error - chose wrong farm", farm)
        await context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را ویرایش کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CHOOSE_ATTR
    if farm == "↩️ بازگشت":
        db.log_activity(user.id, "back")
        await context.bot.send_message(
            chat_id=user.id, text="عملیات کنسل شد!", reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    db.log_activity(user.id, "chose farm to edit", farm)
    message_id = update.effective_message.message_id
    try:
        # await context.bot.edit_message_text(chat_id=user.id, message_id=message_id, text=f"انتخاب مولفه برای ویرایش در {farm}", reply_markup=edit_keyboard())
        await context.bot.send_message(
            chat_id=user.id,
            text=f"انتخاب مولفه برای ویرایش در {farm}",
            reply_markup=edit_keyboard_reply(),
        )
        return EDIT_FARM
    except KeyError:
        logger.info(f"key {farm} doesn't exist.")
        return ConversationHandler.END

async def edit_farm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    user = update.effective_user
    message_id = update.effective_message.message_id
    # attr = update.callback_query.data
    attr = update.message.text
    if attr == "بازگشت به لیست باغ ها":
        db.log_activity(user.id, "back")
        # await context.bot.edit_message_text(chat_id=user.id, message_id=message_id, text="یکی از باغ های خود را انتخاب کنید",
        #                                reply_markup=farms_list_reply(db, user.id))
        await context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CHOOSE_ATTR
    if attr == "تغییر محصول":
        db.log_activity(user.id, "chose edit product")
        user_data["attr"] = attr
        await context.bot.send_message(
            chat_id=user.id,
            text="لطفا محصول جدید باغ را انتخاب کنید",
            reply_markup=get_product_keyboard(),
        )
        return HANDLE_EDIT
    elif attr == "تغییر استان":
        db.log_activity(user.id, "chose edit province")
        user_data["attr"] = attr
        await context.bot.send_message(
            chat_id=user.id,
            text="لطفا استان جدید باغ را انتخاب کنید",
            reply_markup=get_province_keyboard(),
        )
        return HANDLE_EDIT
    elif attr == "تغییر شهرستان":
        db.log_activity(user.id, "chose edit city")
        user_data["attr"] = attr
        await context.bot.send_message(chat_id=user.id, text="لطفا شهر جدید باغ را وارد کنید", reply_markup=back_button())
        return HANDLE_EDIT
    elif attr == "تغییر روستا":
        db.log_activity(user.id, "chose edit village")
        user_data["attr"] = attr
        await context.bot.send_message(
            chat_id=user.id, text="لطفا روستای جدید باغ را وارد کنید", reply_markup=back_button()
        )
        return HANDLE_EDIT
    elif attr == "تغییر مساحت":
        db.log_activity(user.id, "chose edit area")
        user_data["attr"] = attr
        await context.bot.send_message(
            chat_id=user.id, text="لطفا مساحت جدید باغ را وارد کنید", reply_markup=back_button()
        )
        return HANDLE_EDIT
    elif attr == "تغییر موقعیت":
        db.log_activity(user.id, "chose edit location")
        user_data["attr"] = attr
        text = "لطفا موقعیت باغ (لوکیشن باغ) خود را بفرستید."
        keyboard = [
            [KeyboardButton("ارسال لینک آدرس (گوگل مپ یا نشان)")],
            [
                KeyboardButton(
                    "ارسال لوکیشن آنلاین (الان در باغ هستم)", request_location=True
                )
            ],
            [KeyboardButton("از نقشه داخل تلگرام انتخاب میکنم")],
            [KeyboardButton("بازگشت")]
        ]
        await context.bot.send_message(
            chat_id=user.id,
            text=text,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
        return HANDLE_EDIT
    else:
        db.log_activity(user.id, "error - chose wrong value to edit", attr)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END

async def handle_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    attr = user_data["attr"]
    farm = user_data["selected_farm"]
    user_farms = db.get_farms(user.id)
    ## handle the new value of attr
    if attr == "تغییر محصول":
        new_product = update.message.text
        if new_product == "بازگشت":
            db.log_activity(user.id, "back")
            await context.bot.send_message(chat_id=user.id, text = "انتخاب مولفه برای ویرایش", reply_markup=edit_keyboard_reply())
            return EDIT_FARM
        if not new_product or new_product not in PRODUCTS:
            db.log_activity(user.id, "error - edit product", new_product)
            await update.message.reply_text(
                "لطفا محصول جدید باغ را انتخاب کنید",
                reply_markup=get_product_keyboard(),
            )
            return HANDLE_EDIT
        db.set_user_attribute(user.id, f"farms.{farm}.product", new_product)
        reply_text = f"محصول جدید {farm} با موفقیت ثبت شد."
        db.log_activity(user.id, "finish edit product")
        await context.bot.send_message(
            chat_id=user.id, text=reply_text, reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    elif attr == "تغییر استان":
        new_province = update.message.text
        if new_province == "بازگشت":
            await context.bot.send_message(chat_id=user.id, text = "انتخاب مولفه برای ویرایش", reply_markup=edit_keyboard_reply())
            return EDIT_FARM
        if not new_province or new_province not in PROVINCES:
            db.log_activity(user.id, "error - edit province", new_province)
            await update.message.reply_text(
                "لطفا استان جدید باغ را انتخاب کنید",
                reply_markup=get_province_keyboard(),
            )
            return HANDLE_EDIT
        db.set_user_attribute(user.id, f"farms.{farm}.province", new_province)
        reply_text = f"استان جدید {farm} با موفقیت ثبت شد."
        db.log_activity(user.id, "finish edit province")
        await context.bot.send_message(
            chat_id=user.id, text=reply_text, reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    elif attr == "تغییر شهرستان":
        new_city = update.message.text
        if new_city == "بازگشت":
            await context.bot.send_message(chat_id=user.id, text = "انتخاب مولفه برای ویرایش", reply_markup=edit_keyboard_reply())
            return EDIT_FARM
        if new_city in MENU_CMDS:
            db.log_activity(user.id, "error - answer in menu_cmd list", new_city)
            await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
            return ConversationHandler.END
        if not new_city:
            db.log_activity(user.id, "error - edit city")
            await update.message.reply_text("لطفا شهرستان جدید باغ را انتخاب کنید")
            return HANDLE_EDIT
        db.set_user_attribute(user.id, f"farms.{farm}.city", new_city)
        reply_text = f"شهرستان جدید {farm} با موفقیت ثبت شد."
        db.log_activity(user.id, "finish edit city")
        await context.bot.send_message(
            chat_id=user.id, text=reply_text, reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    elif attr == "تغییر روستا":
        new_village = update.message.text
        if new_village == "بازگشت":
            await context.bot.send_message(chat_id=user.id, text = "انتخاب مولفه برای ویرایش", reply_markup=edit_keyboard_reply())
            return EDIT_FARM
        if new_village in MENU_CMDS:
            db.log_activity(user.id, "error - answer in menu_cmd list", new_village)
            await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
            return ConversationHandler.END
        if not new_village:
            db.log_activity(user.id, "error - edit village")
            await update.message.reply_text("لطفا روستای جدید باغ را انتخاب کنید")
            return HANDLE_EDIT
        db.set_user_attribute(user.id, f"farms.{farm}.village", new_village)
        reply_text = f"روستای جدید {farm} با موفقیت ثبت شد."
        db.log_activity(user.id, "finish edit village")
        await context.bot.send_message(
            chat_id=user.id, text=reply_text, reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    elif attr == "تغییر مساحت":
        new_area = update.message.text
        if new_area == "بازگشت":
            await context.bot.send_message(chat_id=user.id, text = "انتخاب مولفه برای ویرایش", reply_markup=edit_keyboard_reply())
            return EDIT_FARM
        if new_area in MENU_CMDS:
            db.log_activity(user.id, "error - answer in menu_cmd list", new_area)
            await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
            return ConversationHandler.END
        if not new_area:
            db.log_activity(user.id, "error - edit area")
            await update.message.reply_text("لطفا مساحت جدید باغ را انتخاب کنید")
            return HANDLE_EDIT
        db.set_user_attribute(user.id, f"farms.{farm}.area", new_area)
        reply_text = f"مساحت جدید {farm} با موفقیت ثبت شد."
        db.log_activity(user.id, "finish edit area")
        await context.bot.send_message(
            chat_id=user.id, text=reply_text, reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    elif attr == "تغییر موقعیت":
        new_location = update.message.location
        text = update.message.text
        if text == "بازگشت":
            db.log_activity(user.id, "back")
            await context.bot.send_message(chat_id=user.id, text = "انتخاب مولفه برای ویرایش", reply_markup=edit_keyboard_reply())
            return EDIT_FARM
        if text == "ارسال لینک آدرس (گوگل مپ یا نشان)":
            db.log_activity(user.id, "chose to edit location with link")
            await update.message.reply_text("لطفا لینک آدرس باغ خود را ارسال کنید.", reply_markup=back_button())
            return HANDLE_EDIT_LINK
        if new_location:
            logger.info(f"{update.effective_user.id} chose: ersal new_location online")
            db.set_user_attribute(
                user.id, f"farms.{farm}.location.longitude", new_location.longitude
            )
            db.set_user_attribute(
                user.id, f"farms.{farm}.location.latitude", new_location.latitude
            )
            reply_text = f"موقعیت جدید {farm} با موفقیت ثبت شد."
            db.log_activity(user.id, "finish edit location", f"long: {new_location.longitude}, lat: {new_location.latitude}")
            await context.bot.send_message(
                chat_id=user.id, text=reply_text, reply_markup=start_keyboard()
            )
            return ConversationHandler.END
        if not new_location and text != "از نقشه داخل تلگرام انتخاب میکنم":
            logger.info(
                f"{update.effective_user.id} didn't send new_location successfully"
            )
            reply_text = "ارسال موقعیت جدید باغ با موفقیت انجام نشد."
            db.log_activity(user.id, "error - edit location", text)
            await context.bot.send_message(
                chat_id=user.id, text=reply_text, reply_markup=edit_keyboard_reply()
            )
            return EDIT_FARM
        elif text == "از نقشه داخل تلگرام انتخاب میکنم":
            db.log_activity(user.id, "chose to send location from map")
            logger.info(
                f"{update.effective_user.id} chose: az google map entekhab mikonam"
            )
            reply_text = """
مطابق فیلم راهنما موقعیت جدید باغ خود را انتخاب کنید
    
👉  https://t.me/agriweath/2
            """
            await context.bot.send_message(
                chat_id=user.id, text=reply_text, reply_markup=ReplyKeyboardRemove()
            )
            return HANDLE_EDIT

async def handle_edit_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    text = update.message.text
    if text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    if not text:
        db.log_activity(user.id, "error - no location link")
        await update.message.reply_text("لطفا لینک آدرس باغ خود را ارسال کنید.", reply_markup=back_button())
        return HANDLE_EDIT_LINK
    elif text == "بازگشت":
        db.log_activity(user.id, "back")
        reply_text = "لطفا موقعیت باغ (لوکیشن باغ) خود را بفرستید."
        keyboard = [
        [KeyboardButton("ارسال لینک آدرس (گوگل مپ یا نشان)")],
        [
            KeyboardButton(
                "ارسال لوکیشن آنلاین (الان در باغ هستم)", request_location=True
            )
        ],
        [KeyboardButton("از نقشه داخل تلگرام انتخاب میکنم")],
        [KeyboardButton("بازگشت")]
        ]
        await update.message.reply_text(
            reply_text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return HANDLE_EDIT
    reply_text = "ارسال لینک آدرس باغ با موفقیت انجام شد. لطفا منتظر تایید ادمین باشید. با تشکر."
    db.log_activity(user.id, "finish edit location with link")
    await update.message.reply_text(reply_text, reply_markup=start_keyboard())
    for admin in ADMIN_LIST:
        await context.bot.send_message(chat_id=admin, text=f"user {user.id} sent us a link for\nname:{user_data['selected_farm']}\n{text}")
    return ConversationHandler.END


# START OF DELETE CONVERSATION
async def delete_farm_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "start delete process")
    user_farms = db.get_farms(user.id)
    if user_farms:
        await update.message.reply_text(
            "یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CONFIRM_DELETE
    else:
        await update.message.reply_text(
            "شما هنوز باغی ثبت نکرده اید", reply_markup=start_keyboard()
        )
        return ConversationHandler.END

async def confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    farm = update.message.text
    user_data["farm_to_delete"] = farm
    user = update.effective_user
    user_farms = db.get_farms(user.id)
    user_farms_names = list(db.get_farms(user.id).keys())
    if farm in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", farm)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    if farm not in user_farms_names and farm != "↩️ بازگشت":
        db.log_activity(user.id, "error - wrong farm to delete", farm)
        await context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CONFIRM_DELETE
    if farm == "↩️ بازگشت":
        db.log_activity(user.id, "back")
        await context.bot.send_message(
            chat_id=user.id, text="عملیات کنسل شد!", reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    db.log_activity(user.id, "chose farm to delete", farm)
    location = user_farms.get(farm)["location"]
    text = f"""
آیا از حذف <b>{farm}</b> با مشخصات زیر اطمینان دارید؟
محصول باغ: {user_farms[farm].get("product")}
مساحت: {user_farms[farm].get("area")}
آدرس انتخاب شده ⬇️
"""
    await context.bot.send_message(chat_id=user.id, text=text, parse_mode=ParseMode.HTML)

    if location and location != {"latitude": None, "longitude": None}:
        await context.bot.send_location(
            chat_id=user.id,
            latitude=location.get("latitude"),
            longitude=location.get("longitude"),
            reply_markup=conf_del_keyboard(),
        )
        return DELETE_FARM
    else:
        await context.bot.send_message(
            chat_id=user.id,
            text=f"موقعیت <{farm}> ثبت نشده است. ",
            reply_markup=conf_del_keyboard(),
        )
        return DELETE_FARM

async def delete_farm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    user = update.effective_user
    farm = user_data["farm_to_delete"]
    answer = update.message.text
    acceptable = ["بله", "خیر", "بازگشت"]
    if answer not in acceptable:
        db.log_activity(user.id, "error - wrong delete confirmation", answer)
        await context.bot.send_message(
            chat_id=user.id, text="عملیات موفق نبود", reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    elif answer == "بازگشت":
        db.log_activity(user.id, "back")
        await context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CONFIRM_DELETE
    elif answer == "خیر":
        db.log_activity(user.id, "stopped delete")
        await context.bot.send_message(
            chat_id=user.id, text="عملیات لغو شد", reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    elif answer == "بله":
        db.log_activity(user.id, "confirmed delete")
        try:
            db.user_collection.update_one(
                {"_id": user.id}, {"$unset": {f"farms.{farm}": ""}}
            )
            text = f"{farm} با موفقیت حذف شد."
            await context.bot.send_message(
                chat_id=user.id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=start_keyboard(),
            )
            return ConversationHandler.END
        except KeyError:
            logger.info(f"DELETE: key {farm} doesn't exist for user {user.id}.")
            return ConversationHandler.END


async def error_handler_(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error('Update "%s" caused error "%s"', update, context.error)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error('Update "%s" caused error "%s"', update, context.error)

    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we have to join them together.
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f"An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )

    # Finally, send the message
    await context.bot.send_message(
        chat_id=103465015, text=message, parse_mode=ParseMode.HTML
    )


# START OF REGISTER CONVERSATION
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "start register", f"{user.id} - username: {user.username}")
    if db.check_if_user_is_registered(user_id=user.id):
        await update.message.reply_text(
            "شما قبلا ثبت نام کرده‌اید. می‌توانید با استفاده از /start به ثبت باغ‌های خود اقدام کنید"
        )
        return ConversationHandler.END
    await update.message.reply_text(
        "لطفا نام و نام خانوادگی خود را وارد کنید", reply_markup=ReplyKeyboardRemove()
    )
    return ASK_PHONE

async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "entered name", f"{update.message.text}")
    user_data = context.user_data
    # Get the answer to the area question
    if update.message.text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", update.message.text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    if not update.message.text:
        await update.message.reply_text("لطفا نام و نام خانوادگی خود را وارد کنید")
        db.log_activity(user.id, "error - enter name", f"{update.message.text}")
        return ASK_PHONE
    name = update.message.text.strip()
    user_data["name"] = name
    db.set_user_attribute(user_id=user.id, key="name", value=name)
    # db.set_user_attribute(user.id, 'products', user_data['product'], array=True)
    # db.set_user_attribute(user.id, 'provinces', user_data['province'], array=True)
    # db.set_user_attribute(user.id, 'cities', user_data['city'], array=True)
    # db.set_user_attribute(user.id, 'villages', user_data['village'], array=True)
    # db.set_user_attribute(user.id, 'areas', user_data['area'], array=True)
    await update.message.reply_text("لطفا شماره تلفن خود را وارد کنید:")
    return HANDLE_PHONE

async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    # Get the answer to the area question
    phone = update.message.text
    if phone in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", phone)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    if not phone or len(phone) != 11:
        db.log_activity(user.id, "error - entered phone", phone)
        await update.message.reply_text("لطفا شماره تلفن خود را وارد کنید:")
        return HANDLE_PHONE
    db.log_activity(user.id, "entered phone", phone)
    user_data["phone"] = phone
    db.set_user_attribute(user_id=user.id, key="phone-number", value=phone)
    reply_text = """
از ثبت نام شما در بات هواشناسی کشاورزی متشکریم.
لطفا با استفاده از /start نسبت به ثبت باغ‌های خود اقدام کنید.
راه‌های ارتباطی با ما:
ادمین: @agriiadmin
شماره ثابت: 02164063399
    """
    await update.message.reply_text(reply_text)
    return ConversationHandler.END


# START OF ADD_FARM CONVERSATION
async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "start add farm")
    if not db.check_if_user_is_registered(user_id=user.id):
        db.log_activity(user.id, "error - add farm", "not registered yet")
        await update.message.reply_text(
            "لطفا پیش از افزودن باغ از طریق /start ثبت نام کنید",
            reply_markup=start_keyboard(),
        )
        return ConversationHandler.END
    reply_text = """
لطفا برای تشخیص این باغ یک نام انتخاب کنید:
مثلا باغ شماره 1
"""
    await update.message.reply_text(reply_text, reply_markup=back_button())
    #
    return ASK_PRODUCT

async def ask_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        db.log_activity(user.id, "back")
        await update.message.reply_text("عمیلات لغو شد", reply_markup=start_keyboard())
        return ConversationHandler.END
    if update.message.text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", update.message.text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    if not update.message.text:
        db.log_activity(user.id, "error - no name received")
        reply_text = """
لطفا برای دسترسی ساده‌تر به این باغ یک نام انتخاب کنید:
مثلا باغ شماره 1
"""
        await update.message.reply_text(reply_text, reply_markup=back_button())
        return ASK_PRODUCT
    elif db.user_collection.find_one({"_id": user.id}).get("farms"):
        used_farm_names = db.user_collection.find_one({"_id": user.id})["farms"].keys()
        if update.message.text in used_farm_names:
            db.log_activity(user.id, "error - chose same name", f"{update.message.text}")
            reply_text = (
                "شما قبلا از این نام استفاده کرده‌اید. لطفا یک نام جدید انتخاب کنید."
            )
            await update.message.reply_text(reply_text, reply_markup=back_button())
            return ASK_PRODUCT
    name = update.message.text.strip()
    db.log_activity(user.id, "chose name", f"{update.message.text}")
    user_data["farm_name"] = name
    # db.set_user_attribute(user.id, "name", name)
    # db.set_user_attribute(user.id, "finished-sign-up", datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    # logger.info(f"{update.effective_user.username} (id: {update.effective_user.id}) Finished sign up.")
    await update.message.reply_text(
        "لطفا محصول باغ را انتخاب کنید", reply_markup=get_product_keyboard()
    )
    return ASK_PROVINCE

async def ask_province(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        db.log_activity(user.id, "back")
        reply_text = """
لطفا برای تشخیص این باغ یک نام انتخاب کنید:
مثلا باغ شماره 1
"""
        await update.message.reply_text(reply_text, reply_markup=back_button())
        return ASK_PRODUCT
    # Get the answer to the province question
    if not update.message.text or update.message.text not in PRODUCTS:
        db.log_activity(user.id, "error - chose wrong product", f"{update.message.text}")
        await update.message.reply_text(
            "لطفا محصول باغ را انتخاب کنید", reply_markup=get_product_keyboard()
        )
        return ASK_PROVINCE
    product = update.message.text.strip()
    user_data["product"] = product
    db.log_activity(user.id, "chose product", f"{update.message.text}")
    await update.message.reply_text(
        "لطفا استان محل باغ خود را انتخاب کنید:", reply_markup=get_province_keyboard()
    )
    return ASK_CITY

async def ask_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        db.log_activity(user.id, "back")
        await update.message.reply_text(
            "لطفا محصول باغ را انتخاب کنید", reply_markup=get_product_keyboard()
        )
        return ASK_PROVINCE
    # Get the answer to the province question
    if not update.message.text or update.message.text not in PROVINCES:
        db.log_activity(user.id, "error - chose wrong province", f"{update.message.text}")
        await update.message.reply_text(
            "لطفا استان محل باغ خود را انتخاب کنید:",
            reply_markup=get_province_keyboard(),
        )
        return ASK_CITY
    province = update.message.text.strip()
    user_data["province"] = province
    db.log_activity(user.id, "chose province", f"{update.message.text}")
    await update.message.reply_text(
        "لطفا شهرستان محل باغ را وارد کنید:", reply_markup=back_button()
    )
    return ASK_VILLAGE

async def ask_village(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        db.log_activity(user.id, "back")
        await update.message.reply_text(
            "لطفا استان محل باغ خود را انتخاب کنید:",
            reply_markup=get_province_keyboard(),
        )
        return ASK_CITY
    # Get the answer to the province question
    if update.message.text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", update.message.text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    if not update.message.text:
        db.log_activity(user.id, "error - city")
        await update.message.reply_text(
            "لطفا شهرستان محل باغ را وارد کنید:", reply_markup=back_button()
        )
        return ASK_VILLAGE
    city = update.message.text.strip()
    user_data["city"] = city
    db.log_activity(user.id, "entered city", f"{update.message.text}")
    await update.message.reply_text(
        "لطفا روستای محل باغ را وارد کنید:", reply_markup=back_button()
    )
    return ASK_AREA

async def ask_area(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        db.log_activity(user.id, "back")
        await update.message.reply_text(
            "لطفا شهرستان محل باغ را وارد کنید:", reply_markup=back_button()
        )
        return ASK_VILLAGE
    # Get the answer to the village question
    if update.message.text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", update.message.text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    if not update.message.text:
        db.log_activity(user.id, "error - village")
        await update.message.reply_text(
            "لطفا روستای محل باغ را وارد کنید:", reply_markup=back_button()
        )
        return ASK_AREA
    village = update.message.text.strip()
    user_data["village"] = village
    db.log_activity(user.id, "entered village", f"{update.message.text}")
    await update.message.reply_text("لطفا سطح زیر کشت خود را به هکتار وارد کنید:", reply_markup=back_button())
    return ASK_LOCATION

async def ask_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        db.log_activity(user.id, "back")
        await update.message.reply_text("لطفا روستای محل باغ را وارد کنید:", reply_markup=back_button())
        return ASK_AREA
    # Get the answer to the phone number question
    if update.message.text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", update.message.text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    if not update.message.text:
        db.log_activity(user.id, "error - area")
        await update.message.reply_text("لطفا سطح زیر کشت خود را به هکتار وارد کنید:", reply_markup=back_button())
        return ASK_LOCATION
    area = update.message.text.strip()
    user_data["area"] = area
    db.log_activity(user.id, "entered area", f"{update.message.text}")
    reply_text = "لطفا موقعیت باغ (لوکیشن باغ) خود را بفرستید."
    keyboard = [
        [KeyboardButton("ارسال لینک آدرس (گوگل مپ یا نشان)")],
        [
            KeyboardButton(
                "ارسال لوکیشن آنلاین (الان در باغ هستم)", request_location=True
            )
        ],
        [KeyboardButton("از نقشه داخل تلگرام انتخاب میکنم")],
        [KeyboardButton("بازگشت")]
    ]
    await update.message.reply_text(
        reply_text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return HANDLE_LOCATION

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        db.log_activity(user.id, "back")
        await update.message.reply_text("لطفا سطح زیر کشت خود را به هکتار وارد کنید:", reply_markup=back_button())
        return ASK_LOCATION
    if update.message.text == "ارسال لینک آدرس (گوگل مپ یا نشان)":
        db.log_activity(user.id, "chose location link")
        await update.message.reply_text("لطفا لینک آدرس باغ خود را ارسال کنید.", reply_markup=back_button())
        return HANDLE_LINK
            

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
        db.log_activity(user.id, "sent location", f"long:{location['longitude']}, lat: {location['latitude']}")
        logger.info(f"{update.effective_user.id} chose: ersal location online")
        user_data["location"] = {
            "latitude": location.latitude,
            "longitude": location.longitude,
        }
        farm_location = user_data["location"]
        new_farm_dict = {
            "product": farm_product,
            "province": farm_province,
            "city": farm_city,
            "village": farm_village,
            "area": farm_area,
            "location": farm_location,
            "location-method": "User sent location"
        }
        db.add_new_farm(user_id=user.id, farm_name=farm_name, new_farm=new_farm_dict)
        db.log_activity(user.id, "finished add farm - gave location", farm_name)
        reply_text = f"""
باغ شما با نام <{farm_name}> با موفقیت ثبت شد.
توصیه‌های مرتبط با شرایط آب‌و‌هوایی از روزهای آینده برای شما ارسال خواهد  شد.
برای ویرایش یا مشاهده اطلاعات باغ از گزینه‌های مرتبط در /start استفاده کنید.
"""
        await update.message.reply_text(reply_text, reply_markup=start_keyboard())
        return ConversationHandler.END
    if not location and text != "از نقشه داخل تلگرام انتخاب میکنم":
        db.log_activity(user.id, "error - location", text)
        logger.info(f"{update.effective_user.id} didn't send location successfully")
        reply_text = "ارسال موقعیت باغ با موفقیت انجام نشد. می توانید از طریق ویرایش باغ موقعیت آن را ثبت کنید"
        user_data["location"] = {
            "latitude": None,
            "longitude": None,
        }
        farm_location = user_data["location"]
        new_farm_dict = {
            "product": farm_product,
            "province": farm_province,
            "city": farm_city,
            "village": farm_village,
            "area": farm_area,
            "location": farm_location,
            "location-method": "Unsuccessful"
        }
        db.add_new_farm(user_id=user.id, farm_name=farm_name, new_farm=new_farm_dict)
        db.log_activity(user.id, "finish add farm - no location", farm_name)
        await update.message.reply_text(reply_text, reply_markup=start_keyboard())
        return ConversationHandler.END
    elif text == "از نقشه داخل تلگرام انتخاب میکنم":
        db.log_activity(user.id, "chose to send location from map")
        logger.info(f"{update.effective_user.id} chose: az google map entekhab mikonam")
        reply_text = """
        مطابق فیلم راهنما موقعیت لوکیشن باغ خود را انتخاب کنید
        
        👉  https://t.me/agriweath/2
        """
        await update.message.reply_text(reply_text, reply_markup=ReplyKeyboardRemove())
        return HANDLE_LOCATION

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    text = update.message.text
    farm_name = user_data["farm_name"]
    farm_product = user_data["product"]
    farm_province = user_data["province"]
    farm_city = user_data["city"]
    farm_village = user_data["village"]
    farm_area = user_data["area"]
    if text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", update.message.text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif not text:
        db.log_activity(user.id, "error - no location link")
        await update.message.reply_text("لطفا لینک آدرس باغ خود را ارسال کنید.", reply_markup=back_button())
        return HANDLE_LINK
    elif text == "بازگشت":
        db.log_activity(user.id, "back")
        reply_text = "لطفا موقعیت باغ (لوکیشن باغ) خود را بفرستید."
        keyboard = [
        [KeyboardButton("ارسال لینک آدرس (گوگل مپ یا نشان)")],
        [
            KeyboardButton(
                "ارسال لوکیشن آنلاین (الان در باغ هستم)", request_location=True
            )
        ],
        [KeyboardButton("از نقشه داخل تلگرام انتخاب میکنم")],
        [KeyboardButton("بازگشت")]
        ]
        await update.message.reply_text(
            reply_text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return HANDLE_LOCATION
    else:
        db.log_activity(user.id, "sent location link", text)
        reply_text = "ارسال لینک آدرس باغ با موفقیت انجام شد. لطفا تا بررسی ادمین منتظر بمانید. از شکیبایی شما سپاسگزاریم."
        user_data["location"] = {
            "latitude": None,
            "longitude": None,
        }
        farm_location = user_data["location"]
        new_farm_dict = {
            "product": farm_product,
            "province": farm_province,
            "city": farm_city,
            "village": farm_village,
            "area": farm_area,
            "location": farm_location,
            "location-method": "Link"
        }
        db.add_new_farm(user_id=user.id, farm_name=farm_name, new_farm=new_farm_dict)
        db.log_activity(user.id, "finish add farm with location link", farm_name)
        await update.message.reply_text(reply_text, reply_markup=start_keyboard())
        for admin in ADMIN_LIST:
            await context.bot.send_message(chat_id=admin, text=f"user {user.id} sent us a link for\nname:{farm_name}\n{text}")
        return ConversationHandler.END

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
            reply_markup=start_keyboard(),
        )
        return ConversationHandler.END

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
        await update.message.reply_text("عملیات لغو شد", reply_markup=start_keyboard())
        return ConversationHandler.END
    if farm not in list(user_farms.keys()):
        db.log_activity(user.id, "error - chose farm for weather report" , farm)
        await update.message.reply_text("لطفا دوباره تلاش کنید. نام باغ اشتباه بود", reply_markup=start_keyboard())
        return ConversationHandler.END
    db.log_activity(user.id, "chose farm for weather report", farm)
    longitude = user_farms[farm]["location"]["longitude"]
    latitude = user_farms[farm]["location"]["latitude"]
    
    if longitude is not None:
        try:
            if datetime.time(7, 0).strftime("%H%M") <= datetime.datetime.now().strftime("%H%M") < datetime.time(20, 30).strftime("%H%M"):    
                weather_data = gpd.read_file(f"data/pesteh{today}_1.geojson")
                point = Point(longitude, latitude)
                threshold = 0.1  # degrees
                idx_min_dist = weather_data.geometry.distance(point).idxmin()
                closest_coords = weather_data.geometry.iloc[idx_min_dist].coords[0]
                if point.distance(Point(closest_coords)) <= threshold:
                    row = weather_data.iloc[idx_min_dist]
                    tmin_values , tmax_values , rh_values , spd_values , rain_values = [], [], [], [], []
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
پیش‌بینی وضعیت آب و هوای باغ شما با نام <{farm}> در چهار روز آینده بدین صورت خواهد بود
"""
                    table([jtoday, jday2, jday3, jday4], tmin_values, tmax_values, rh_values, spd_values, rain_values)
                    with open('table.png', 'rb') as image_file:
                        await context.bot.send_photo(chat_id=user.id, photo=image_file, caption=caption, reply_markup=start_keyboard())
                    db.log_activity(user.id, "received 4-day weather reports")
                    return ConversationHandler.END
                else:
                    await context.bot.send_message(chat_id=user.id, text="متاسفانه اطلاعات هواشناسی باغ شما در حال حاضر موجود نیست", reply_markup=start_keyboard())
                    return ConversationHandler.END
            else:
                weather_data = gpd.read_file(f"data/pesteh{yesterday}_1.geojson")
                point = Point(longitude, latitude)
                threshold = 0.1  # degrees
                idx_min_dist = weather_data.geometry.distance(point).idxmin()
                closest_coords = weather_data.geometry.iloc[idx_min_dist].coords[0]
                if point.distance(Point(closest_coords)) <= threshold:
                    row = weather_data.iloc[idx_min_dist]
                    tmin_values , tmax_values , rh_values , spd_values , rain_values = [], [], [], [], []
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
پیش‌بینی وضعیت آب و هوای باغ شما با نام <{farm}> در سه روز آینده بدین صورت خواهد بود
"""
                    table([jday2, jday3, jday4], tmin_values[1:], tmax_values[1:], rh_values[1:], spd_values[1:], rain_values[1:])
                    with open('table.png', 'rb') as image_file:
                        await context.bot.send_photo(chat_id=user.id, photo=image_file, caption=caption, reply_markup=start_keyboard())
                    # await context.bot.send_message(chat_id=user.id, text=weather_today, reply_markup=start_keyboard())
                    db.log_activity(user.id, "received 3-day weather reports")
                    return ConversationHandler.END
                else:
                    await context.bot.send_message(chat_id=user.id, text="متاسفانه اطلاعات هواشناسی باغ شما در حال حاضر موجود نیست", reply_markup=start_keyboard())
                    return ConversationHandler.END
        except DriverError:
            logger.info(f"{user.id} requested today's weather. pesteh{today}_1.geojson was not found!")
            await context.bot.send_message(chat_id=user.id, text="متاسفانه اطلاعات هواشناسی باغ شما در حال حاضر موجود نیست", reply_markup=start_keyboard())
            return ConversationHandler.END
        finally:
            os.system("rm table.png")
    else:
        await context.bot.send_message(chat_id=user.id, text="موقعیت باغ شما ثبت نشده است. لظفا پیش از درخواست اطلاعات هواشناسی نسبت به ثبت موققعیت اقدام فرمایید.",
                                 reply_markup=start_keyboard())
        return ConversationHandler.END
 
def main():
    proxy_url = 'http://127.0.0.1:8889'
    application = ApplicationBuilder().token(TOKEN).build()
    # application = ApplicationBuilder().token(TOKEN).proxy_url(proxy_url).get_updates_proxy_url(proxy_url).build()
    register_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("✍️ ثبت نام"), register)],
        states={
            ASK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_phone)],
            HANDLE_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    
    weather_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("🌦 درخواست اطلاعات هواشناسی"), req_weather_data)],
        states={
            RECV_WEATHER: [MessageHandler(filters.TEXT , recv_weather)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    # invite_conv = ConversationHandler(
    #     entry_points=[MessageHandler(filters.Regex("دعوت از دیگران"), invite_link)],
    #     states={
    #         HANDLE_INV_LINK: [MessageHandler(filters.TEXT , handle_invite_link)]
    #     },
    #     fallbacks=[CommandHandler("cancel", cancel)],
    # )

    add_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("➕ اضافه کردن باغ"), add)],
        states={
            ASK_PRODUCT: [MessageHandler(filters.TEXT, ask_product)],
            ASK_PROVINCE: [MessageHandler(filters.TEXT, ask_province)],
            ASK_CITY: [MessageHandler(filters.TEXT, ask_city)],
            ASK_VILLAGE: [MessageHandler(filters.TEXT, ask_village)],
            ASK_AREA: [MessageHandler(filters.ALL, ask_area)],
            ASK_LOCATION: [MessageHandler(filters.ALL, ask_location)],
            HANDLE_LOCATION: [MessageHandler(filters.ALL, handle_location)],
            HANDLE_LINK: [MessageHandler(filters.ALL, handle_link)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    

    view_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("🖼 مشاهده باغ ها"), view_farm_keyboard)],
        states={
            VIEW_FARM: [MessageHandler(filters.ALL, view_farm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    off_conv = ConversationHandler(
        entry_points=[CommandHandler("off", ask_coupon)],
        states={
            HANDLE_COUPON: [MessageHandler(filters.ALL, handle_coupon)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    verify_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("✅ ارسال فیش پرداخت"), ask_code)],
        states={
            ASK_SS: [MessageHandler(filters.ALL, ask_ss)],
            HANDLE_SS: [MessageHandler(filters.ALL, handle_ss)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    edit_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("✏️ ویرایش باغ ها"), edit_farm_keyboard)],
        states={
            CHOOSE_ATTR: [MessageHandler(filters.ALL, choose_attr_to_edit)],
            EDIT_FARM: [MessageHandler(filters.ALL, edit_farm)],
            HANDLE_EDIT: [MessageHandler(filters.ALL, handle_edit)],
            HANDLE_EDIT_LINK: [MessageHandler(filters.ALL, handle_edit_link)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    

    delete_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("🗑 حذف باغ ها"), delete_farm_keyboard)
        ],
        states={
            CONFIRM_DELETE: [MessageHandler(filters.ALL, confirm_delete)],
            DELETE_FARM: [MessageHandler(filters.ALL, delete_farm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    

    broadcast_handler = ConversationHandler(
        entry_points=[CommandHandler("send", send)],
        states={
            CHOOSE_RECEIVERS: [MessageHandler(filters.ALL, choose_receivers)],
            HANDLE_IDS: [MessageHandler(filters.ALL, handle_ids)],
            BROADCAST: [MessageHandler(filters.ALL, broadcast)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    

    set_location_handler = ConversationHandler(
        entry_points=[CommandHandler("set", set_loc)],
        states={
            ASK_FARM_NAME: [MessageHandler(filters.ALL, ask_farm_name)],
            ASK_LONGITUDE: [MessageHandler(filters.ALL, ask_longitude)],
            ASK_LATITUDE: [MessageHandler(filters.ALL, ask_latitude)],
            HANDLE_LAT_LONG: [MessageHandler(filters.ALL, handle_lat_long)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    

    # Add handlers to the application
    application.add_error_handler(error_handler)

    application.add_handler(register_conv)
    application.add_handler(add_conv)
    # application.add_handler(invite_conv)
    application.add_handler(MessageHandler(filters.Regex("دعوت از دیگران"), invite))
    application.add_handler(MessageHandler(filters.Regex("💰 پرداخت"), payment_link))
    application.add_handler(CommandHandler("verify", verify_payment))
    application.add_handler(off_conv)
    application.add_handler(verify_conv)
    application.add_handler(weather_conv)
    application.add_handler(view_conv)
    application.add_handler(edit_conv)
    application.add_handler(delete_conv)

    application.add_handler(CommandHandler("coupon", create_coupon))
    application.add_handler(set_location_handler)
    application.add_handler(broadcast_handler)
    application.add_handler(CommandHandler("stats", bot_stats))
    application.add_handler(CallbackQueryHandler(button))

    application.add_handler(CommandHandler("start", start))


    # Schedule periodic messages
    job_queue = application.job_queue
    
    job_queue.run_repeating(get_member_count, interval=7200, first=60)
    job_queue.run_repeating(send_todays_data,
        interval=datetime.timedelta(days=1),
        # first=10
        first=datetime.time(7, 0),
    )

    job_queue.run_once(send_up_notice, when=5)
    
    # Start the bot
    application.run_polling()

if __name__ == "__main__":
    try:
        main()
    except NetworkError:
        logger.error("A network error was encountered!")
    except ConnectionRefusedError:
        logger.error("A ConnectionRefusedError was encountered!")
