import logging
from logging.handlers import RotatingFileHandler
from telegram import (
    Update,
)
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from telegram.error import BadRequest, Forbidden
from telegram.constants import ParseMode
import requests
import re
import warnings
import database

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
ASK_FARM_NAME, ASK_LONGITUDE, ASK_LATITUDE, HANDLE_LAT_LONG = range(4)
HANDLE_LOCATION = 0
MENU_CMDS = ['✍️ ثبت نام', '📤 دعوت از دیگران', '🖼 مشاهده کشت‌ها', '➕ اضافه کردن کشت', '🗑 حذف کشت', '✏️ ویرایش کشت‌ها', '🌦 درخواست اطلاعات هواشناسی', '/start', '/stats', '/send', '/set']
###################################################################
####################### Initialize Database #######################
db = database.Database()
ADMIN_LIST = db.get_admins()
###################################################################
async def cq_set_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    admin = query.from_user
    try:
        await query.answer()
    except BadRequest:
        logger.error(f"query.answer() caused BadRequest error. user: {query.message.chat.id}")
    target_user = int(query.data.split("\n")[1])
    farm_name = query.data.split("\n")[2]
    context.user_data['target_user'] = target_user
    context.user_data['farm_name'] = farm_name
    await context.bot.send_message(admin.id, text="آدرس کاربر را به این صورت وارد کن:\nlatitude,longitude ->\n37.4,59.35")
    return HANDLE_LOCATION

async def cq_handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin = update.effective_user
    user_data = context.user_data
    
    target_user = user_data.get("target_user")
    farm_name = user_data.get("farm_name")
    
    if not target_user or not farm_name:
        await context.bot.send_message(admin.id, "اطلاعات یافت نشد. لطفا از /set استفاده کن.")
        return ConversationHandler.END
    
    message = update.message.text
    try:
        lat = float(message.split(',')[0])
        long = float(message.split(',')[1])
    except (IndexError, ValueError):
        await context.bot.send_message(admin.id, "لوکیشن ارسالی باید به صورت زیر باشد:\n`latitude,longitude`\nدوباره دکمه را بزن وامتحان کن.", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    
    db.set_user_attribute(target_user, f"farms.{farm_name}.location.longitude", long)
    db.set_user_attribute(target_user, f"farms.{farm_name}.location.latitude", lat)
    db.set_user_attribute(target_user, f"farms.{farm_name}.link-status", "Verified")
    db.log_activity(admin.id, "set a user's location", target_user)
    for admin in ADMIN_LIST:
        await context.bot.send_message(chat_id=admin, text=f"Location of farm {farm_name} belonging to {target_user} was set")
        await context.bot.send_location(chat_id=admin, latitude=lat, longitude=long)
    try:
        await context.bot.send_message(chat_id=target_user, text=f"لوکیشن باغ شما با نام {farm_name} ثبت شد.")
        await context.bot.send_location(chat_id=target_user, latitude=lat, longitude=long)
    except (BadRequest, Forbidden):
        db.set_user_attribute(target_user, "blocked", True)
        await context.bot.send_message(chat_id=admin.id, text=f"Location wasn't set. User may have blocked the bot.")
    return ConversationHandler.END    

# Start of /set conversation
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
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
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
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif not farm_name:
        await update.message.reply_text(f"نام باغ چیست؟ \n/cancel")
        return ASK_LONGITUDE
    elif len(user_data['target']) != len(farm_name.split('\n')):
        db.log_activity(user.id, "error - farm_name list not equal to IDs", farm_name)
        await update.message.reply_text("تعداد آی‌دی‌ها و نام باغ ها یکسان نیست. لطفا دوباره شروع کنید.", reply_markup=db.find_start_keyboard(user.id))
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
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif not longitude:
        await update.message.reply_text("""
اگر یک آیدی وارد کردید حالا مقدار longitude را وارد کنید. اگر بیش از یک آیدی داشتید لینک‌های گوگل مپ مرتبط را وارد کنید.
هر لینک در یک خط باشد. تنها لینکهایی که مانند زیر باشند قابل قبول هستند
https://goo.gl/maps/3Nx2zh3pevaz9vf16
""")
        return ASK_LATITUDE
    elif len(target) == 1 and longitude.replace(".", "").isdecimal() == False:
        await update.message.reply_text("\n\n <b>مقدار Longitude وارد شده قابل قبول نیست. طول و عرض جغرافیایی باید اعداد صحیح یا اعشار باشند.\nدوباره تلاش کنید.</b> \n\n", parse_mode=ParseMode.HTML)
        return ASK_LATITUDE
    elif len(target) == 1:
        user_data["long"] = longitude
        await update.message.reply_text(f"what's the latitude of {user_data['target']}?\ndo you want to /cancel ?")
        return HANDLE_LAT_LONG
    else:
        links = longitude.split("\n")
        if len(user_data['target']) != len(links):
            db.log_activity(user.id, "error - links list not equal to IDs", farm_name)
            await update.message.reply_text("تعداد لینک ها و آیدی ها یکسان نیست. لطفا دوباره شروع کنید.", reply_markup=db.find_start_keyboard(user.id))
            return ConversationHandler.END
        elif not all(link.startswith("https://goo.gl") for link in links):
            db.log_activity(user.id, "error - links not valid", farm_name)
            await update.message.reply_text("لینک ها مورد قبول نیستند. لطفا دوباره شروع کنید.", reply_markup=db.find_start_keyboard(user.id))
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
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif not latitude:
        await update.message.reply_text(f"what's the latitude of {latitude}? \ndo you want to /cancel ?")
        return HANDLE_LAT_LONG
    elif latitude.replace(".", "").isdecimal() == False:
        await update.message.reply_text("\n\n <b>مقدار Latitude وارد شده قابل قبول نیست. طول و عرض جغرافیایی باید اعداد صحیح یا اعشار باشند.\nدوباره تلاش کنید.</b> \n\n", parse_mode=ParseMode.HTML)
        return HANDLE_LAT_LONG
    user_data["lat"] = latitude
    db.set_user_attribute(int(user_data["target"][0]), f"farms.{user_data['farm_name']}.location.longitude", float(user_data["long"]))
    db.set_user_attribute(int(user_data["target"][0]), f"farms.{user_data['farm_name']}.location.latitude", float(user_data["lat"]))
    db.set_user_attribute(int(user_data["target"][0]), f"farms.{user_data['farm_name']}.link-status", "Verified")
    db.log_activity(user.id, "set a user's location", user_data["target"][0])
    for admin in ADMIN_LIST:
        await context.bot.send_message(chat_id=admin, text=f"Location of farm {user_data['farm_name']} belonging to {user_data['target'][0]} was set")
        await context.bot.send_location(chat_id=admin, latitude=float(user_data["lat"]), longitude=float(user_data["long"]))
    try:
        await context.bot.send_message(chat_id=int(user_data["target"][0]), text=f"لوکیشن باغ شما با نام {user_data['farm_name']} ثبت شد.")
        await context.bot.send_location(chat_id=int(user_data["target"][0]), latitude=float(user_data["lat"]), longitude=float(user_data["long"]))
    except (BadRequest, Forbidden):
        db.set_user_attribute(int(user_data["target"][0]), "blocked", True)
        await context.bot.send_message(chat_id=user.id, text=f"Location wasn't set. User may have blocked the bot.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات کنسل شد!")
    return ConversationHandler.END


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

cq_set_location_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(cq_set_location, pattern="^set-location")],
    states={
        HANDLE_LOCATION: [MessageHandler(filters.ALL, cq_handle_location)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)