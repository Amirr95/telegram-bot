import logging
import json
import datetime
import pickle
import geopandas as gpd
from telegram import Bot, KeyboardButton, Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, CallbackContext, \
    BasePersistence, ConversationHandler, PicklePersistence
from telegram.error import BadRequest, Unauthorized
import os


# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Constants for ConversationHandler states
START, ASK_PHONE, ASK_QUESTION_1, ASK_QUESTION_2, ASK_LOCATION, HANDLE_LOCATION = range(6)
START, ASK_PROVINCE, ASK_CITY, ASK_AREA, ASK_PHONE, ASK_LOCATION, ASK_NAME, HANDLE_NAME = range(8)

# TOKEN = os.environ["AGRIWEATHBOT_TOKEN"]
TOKEN = "6004713690:AAHz8olZ6Z4qaODXt5fue3CvaF2VQzCQbms"
PROXY_URL = "http://127.0.0.1:8889"

persistence = PicklePersistence(filename='bot_data.pickle')
REQUIRED_KEYS = ['produce', 'province', 'city', 'area', 'location', 'name', 'phone']
PROVINCES = ['کرمان', 'خراسان رضوی', 'خراسان جنوبی', 'یزد', 'فارس', 'سمنان', 'سایر']
PRODUCTS = ['پسته اکبری', 'پسته اوحدی', 'پسته احمدآقایی', 'پسته بادامی', 'پسته فندقی', 'پسته کله قوچی', 'پسته ممتاز', 'سایر']

def start(update: Update, context: CallbackContext):
    user = update.effective_user
    name = user.username
    # update.message.reply_text(f"id: {user.id}, username: {user.username}")
    persistence_data = persistence.user_data # {103465015: {'produce': 'محصول 3', 'province': 'استان 4', 'city': 'اردستان', 'area': '۵۴۳۳۴۵۶', 'location': {'latitude': 35.762059, 'longitude': 51.476923}, 'name': 'امیررضا', 'phone': '۰۹۱۳۳۶۴۷۹۹۱'}})
    user_data = context.user_data # {'produce': 'محصول 3', 'province': 'استان 4', 'city': 'اردستان', 'area': '۵۴۳۳۴۵۶', 'location': {'latitude': 35.762059, 'longitude': 51.476923}, 'name': 'امیررضا', 'phone': '۰۹۱۳۳۶۴۷۹۹۱'}
    user_data['username'] = update.effective_user.username
    user_data['blocked'] = False
    user_data['join-date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Check if the user has already signed up
    if user.id in persistence.user_data:
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
    logger.info(f"user_data: {context.user_data}")
    # Get the answer to the province question
    if not update.message.text or update.message.text not in PRODUCTS:
        update.message.reply_text("لطفا نوع محصول خود را انتخاب کنید:", reply_markup=get_produce_keyboard())
        return ASK_PROVINCE
    produce = update.message.text.strip()
    user_data['produce'] = produce
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
    return ASK_AREA


def ask_area(update: Update, context: CallbackContext):
    user_data = context.user_data

    # Get the answer to the city question
    if not update.message.text or update.message.text=="/start":
        update.message.reply_text("لطفا شهرستان محل باغ را وارد کنید:", reply_markup=ReplyKeyboardRemove())
        return ASK_AREA
    
    city = update.message.text.strip()
    user_data['city'] = city

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
    phone = update.message.text.strip()
    user_data['phone'] = phone

    # persistence.update_user_data(user_id=update.effective_user.id, data = user_data)
    reply_text = """
    لطفا موقعیت (لوکیشن) باغ خود را مطابق فیلم راهنما (https://t.me/agriweath/2) ارسال کنید.

👉  https://t.me/agriweath/2
    """
    update.message.reply_text(reply_text)
    return ASK_NAME


def ask_name(update: Update, context: CallbackContext):
    user_data = context.user_data
    # update.message.reply_text("Please share your location!")

    # Get the user's location
    location = update.message.location
    # logger.info(f"location: {update.message.location}")
    if not location:
        text = """
    لطفا موقعیت (لوکیشن) باغ خود را مطابق فیلم راهنما (https://t.me/agriweath/2) ارسال کنید.

👉  https://t.me/agriweath/2
    """
        update.message.reply_text(text) 
        # update.message.reply_text("لطفا محل زمین خود را در نقشه با ما به اشتراک بگذارید:")
        # with open("./help.mp4", "rb") as gif:
        #     update.message.reply_animation(animation=gif, caption="لطفا موقعیت (لوکیشن) باغ خود را مطابق فیلم راهنما ارسال کنید")

        return ASK_NAME
    user_data['location'] = {
        'latitude': location.latitude,
        'longitude': location.longitude
    }

    update.message.reply_text("نام و نام خانودگی خود را وارد کنید:")
    return HANDLE_NAME


def handle_name(update: Update, context: CallbackContext):
    user_data = context.user_data

    if not update.message.text or update.message.text=="/start":
        update.message.reply_text("نام و نام خانودگی خود را وارد کنید:")
        return HANDLE_NAME
    
    name = update.message.text.strip()
    user_data['name'] = name

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
    return ConversationHandler.END


# Function to get the multi-choice keyboard for provinces
def get_province_keyboard():
    keyboard = [['کرمان', 'خراسان رضوی', 'خراسان جنوبی'], ['یزد', 'فارس', 'سمنان'], ['سایر']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)


# Function to get the multi-choice keyboard for produce
def get_produce_keyboard():
    keyboard = [['پسته اکبری', 'پسته اوحدی', 'پسته احمدآقایی'], ['پسته بادامی', 'پسته فندقی', 'پسته کله قوچی'], ['پسته ممتاز', 'سایر']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)


# Function to send personalized scheduled messages
def send_location_guide(update: Update, context: CallbackContext, bot: Bot):
    # Retrieve all user data
    user_data = persistence.get_user_data()
    for user_id in user_data:
            chat = context.bot.getChat(user_id)
            username = chat.username
            user_data[user_id]['username'] = username
            logger.info(f"username: {username}")
            # if not "location" in user_data[user_id]:
            message = """
باغدار عزیز برای ارسال توصیه‌های هواشناسی، به لوکیشن (موقعیت جغافیایی) باغ شما نیاز داریم.
لطفا با ارسال لوکیشن باغ، ثبت نام خود را از طریق /start تکمیل کنید.

برای راهنمایی به @agriiadmin پیام دهید.
                """
            try:
                bot.send_message(user_id, message) ##, parse_mode=telegram.ParseMode.MARKDOWN_V2)
                user_data[user_id]["blocked"] = False
                user_data[user_id]['job-date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
            except Unauthorized:
                logger.info(f"user {user_id} blocked the bot")
                user_data[user_id]["blocked"] = True
                user_data[user_id]['block-date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("job_data.pickle", "wb") as job_data:
        pickle.dump(user_data, job_data)
            

def location_command_handler(update: Update, context: CallbackContext):
    location_keyboard = KeyboardButton(text="send_location", request_location=True)
    contact_keyboard = KeyboardButton(text="send_contact", request_contact=True)
    custom_keyboard = [[ location_keyboard, contact_keyboard ]]
    reply_markup = ReplyKeyboardMarkup(custom_keyboard)
    update.message.reply_text(text="Would you mind sharing your location and contact with me?", reply_markup=reply_markup)

def location(update: Update, context: CallbackContext):
    location = update.message.location
    contact = update.message.contact
    update.message.reply_text(
        f"location: {location}"
        f"contact: {contact}"
    )
    
def main():
    updater = Updater(TOKEN, persistence=persistence, use_context=True)# , request_kwargs={'proxy_url': PROXY_URL})

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Add handlers to the dispatcher
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            ASK_PROVINCE: [MessageHandler(Filters.text, ask_province)],
            ASK_CITY: [MessageHandler(Filters.text, ask_city)],
            ASK_AREA: [MessageHandler(Filters.all, ask_area)],
            ASK_PHONE: [MessageHandler(Filters.all, ask_phone)],
            ASK_LOCATION: [MessageHandler(Filters.all, ask_location)],
            ASK_NAME: [MessageHandler(Filters.all, ask_name)],
            HANDLE_NAME: [MessageHandler(Filters.all, handle_name)]
        },
        fallbacks=[CommandHandler('cancel', start)]
    )

    dp.add_handler(conv_handler)

    # dp.add_handler(CommandHandler('location', location_command_handler))
    # Add the location handler for the received location
    # dp.add_handler(MessageHandler(Filters.location, location_command_handler))

    # Start the bot
    updater.start_polling()

    # Schedule periodic messages
    job_queue = updater.job_queue
    # job_queue.run_repeating(lambda context: send_scheduled_messages(updater, context, context.bot), 
    #                         interval=datetime.timedelta(seconds=5).total_seconds())
    job_queue.run_once(lambda context: send_location_guide(updater, context, context.bot), when=60)
    # Run the bot until you press Ctrl-C or the process receives SIGINT, SIGTERM, or SIGABRT
    updater.idle()

    updater.co
if __name__ == '__main__':
    main()
