import logging
from logging.handlers import RotatingFileHandler
import datetime
from telegram import Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ContextTypes,
    ApplicationBuilder
)
from telegram.constants import ParseMode
from telegram.error import NetworkError
import os
import warnings
import html
import json
import traceback

import database

from utils.regular_jobs import send_todays_data, send_up_notice, get_member_count
from utils.keyboards import (
    manage_farms_keyboard,
    payment_keyboard,
    request_info_keyboard,
    start_keyboard_not_pesteh,
    start_keyboard_pesteh_kar,
    home_keyboard_pesteh_kar
)
from utils.add_conv import add_farm_conv_handler
from utils.edit_conv import edit_farm_conv_handler
from utils.weather_conv import weather_req_conv_handler
from utils.weather_api import load_weather_to_db
from utils.delete_conv import delete_conv_handler
from utils.register_conv import register_conv_handler
from utils.view_conv import view_conv_handler
from utils.set_location_conv import set_location_handler
from utils.admin import broadcast_handler, backup_send, stats_buttons, bot_stats
from utils.commands import invite, start, change_day, harvest_off_conv_handler, harvest_on_conv_handler, invite_conv
from utils.payment_funcs import payment_link, verify_payment, off_conv_handler, verify_conv_handler, create_coupon
from utils.harvest_conv import harvest_conv_handler
from utils.automn_conv import automn_conv_handler, show_remaining_hours

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
warnings.filterwarnings("ignore", category=UserWarning)

# Constants for ConversationHandler states
TOKEN = os.environ["AGRIWEATHBOT_TOKEN"]
MENU_CMDS = ['✍️ ثبت نام', '📤 دعوت از دیگران', '🖼 مشاهده باغ ها', '➕ اضافه کردن باغ', '🗑 حذف باغ ها', '✏️ ویرایش باغ ها', '🌦 درخواست اطلاعات هواشناسی', '/start', '/stats', '/send', '/set']
###################################################################
####################### Initialize Database #######################
db = database.Database()
ADMIN_LIST = db.get_admins()
###################################################################
####################### MENU NAVIGATION ###########################
async def home_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    reply_text = "بازگشت به منوی اصلی"
    db.log_activity(user.id, "navigated to home view")
    if db.check_if_user_has_pesteh(user.id):
        reply_markup = home_keyboard_pesteh_kar()
    else:
        reply_markup = start_keyboard_not_pesteh()
    
    await update.message.reply_text(reply_text, reply_markup=reply_markup)

async def farm_management_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    reply_text = "مدیریت کشت‌ها"
    db.log_activity(user.id, "navigated to farm management view")
    await update.message.reply_text(reply_text, reply_markup=manage_farms_keyboard())

async def weather_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    reply_text = "منوی هواشناسی"
    db.log_activity(user.id, "navigated to weather view")
    await update.message.reply_text(reply_text, reply_markup=start_keyboard_pesteh_kar())

async def info_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    reply_text = "می‌توانید اطلاعات اختصاصی باغ خود را با انتخاب موارد زیر دریافت کنید"
    db.log_activity(user.id, "navigated to farm info view")
    await update.message.reply_text(reply_text, reply_markup=request_info_keyboard())

async def payment_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    reply_text = """
<b>☘باغی آباد با "آباد"☘</b>

با عضویت در ربات " آباد " از خدمات زیر بهره‌مند می‌شوید: 

💢 <b>رایگان:</b>

✅ دریافت پیش بینی روزانه هواشناسی برای چهار روز آینده (دمای کمینه، دمای بیشینه، سرعت باد، رطوبت هوا و بارش)

✅ امکان ثبت یک باغ


💢 <b>سرویس vip:</b>

✅ دریافت هشدارهای لازم جهت پیشگیری از پدیده‌های خسارت‌زای هواشناسی (مانند سرمازدگی، گرمازدگی و آفتاب‌سوختگی، خسارت باد، تگرگ و … )

✅ دریافت توصیه‌های کاربردی هواشناسی کشاورزی مخصوص رقم پسته شما ( زمان مناسب کوددهی، سم‌پاشی و یادآوری اقدامات مهم باغ شما)

✅ دریافت پیامک در مواقع حساس علاوه بر بات تلگرامی

✅ امکان ثبت تا ۵ باغ
.
.
.
و بسیاری از توصیه‌های کاربردی دیگر


✅✅ در صورت عدم رضایت شما از سرویس در هر زمان، هزینه پرداختی باز می‌گردد.
"""
    db.log_activity(user.id, "navigated to payment view")
    await update.message.reply_text(reply_text, parse_mode=ParseMode.HTML, reply_markup=payment_keyboard())

async def contact_us(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "viewed contact us message")
    text = """
راه‌های ارتباط با ما:

ادمین: @agriiadmin
شماره تلفن: 02164063410
آدرس: تهران، ضلع غربی دانشگاه شریف، برج فناوری بنتک
"""
    await update.message.reply_text(text, reply_markup=db.find_start_keyboard(user.id))

###################################################################
###################################################################
# Fallback handlers
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

def main():
    proxy_url = 'http://127.0.0.1:8889'
    application = ApplicationBuilder().token(TOKEN).build()
    # application = ApplicationBuilder().token(TOKEN).proxy_url(proxy_url).get_updates_proxy_url(proxy_url).build()
    # Add handlers to the application
    application.add_error_handler(error_handler)

    # Menu navigation commands
    application.add_handler(MessageHandler(filters.Regex('^🏘 بازگشت به خانه$'), home_view))
    application.add_handler(MessageHandler(filters.Regex('^منوی هواشناسی$'), weather_view))
    application.add_handler(MessageHandler(filters.Regex('^👨‍🌾 مدیریت کشت‌ها$'), farm_management_view))
    application.add_handler(MessageHandler(filters.Regex('^🌟 سرویس VIP$'), payment_view))
    application.add_handler(MessageHandler(filters.Regex('^📲 دریافت اطلاعات اختصاصی باغ$'), info_view))

    # Bot handlers
    application.add_handler(register_conv_handler)
    application.add_handler(add_farm_conv_handler)
    application.add_handler(MessageHandler(filters.Regex("^📤 دعوت از دیگران$"), invite))
    # application.add_handler(invite_conv)
    application.add_handler(MessageHandler(filters.Regex("^📬 ارتباط با ما$"), contact_us))
    application.add_handler(MessageHandler(filters.Regex("^💶 خرید اشتراک$"), payment_link))
    application.add_handler(CommandHandler("verify", verify_payment))
    application.add_handler(off_conv_handler)
    application.add_handler(verify_conv_handler)
    application.add_handler(weather_req_conv_handler)
    application.add_handler(harvest_conv_handler)
    application.add_handler(automn_conv_handler)
    application.add_handler(view_conv_handler)
    application.add_handler(edit_farm_conv_handler)
    application.add_handler(delete_conv_handler)
    application.add_handler(harvest_off_conv_handler)
    application.add_handler(harvest_on_conv_handler)

    application.add_handler(CommandHandler("coupon", create_coupon))
    application.add_handler(set_location_handler)
    application.add_handler(broadcast_handler)
    application.add_handler(CommandHandler("stats", bot_stats))
    application.add_handler(CommandHandler("today", backup_send))
    application.add_handler(CallbackQueryHandler(stats_buttons, pattern="^(member_count|member_count_change|excel_download|block_count|no_location_count|no_phone_count)$"))
    application.add_handler(CallbackQueryHandler(show_remaining_hours, pattern="^gdd"))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(change_day))

    # Schedule periodic messages
    job_queue = application.job_queue
    
    job_queue.run_repeating(get_member_count, interval=7200, first=60)
    job_queue.run_repeating(send_todays_data,
        interval=datetime.timedelta(days=1),
        # first=10,
        first=datetime.time(5, 30),
        job_kwargs={"misfire_grace_time": 300}
    )
    job_queue.run_repeating(load_weather_to_db,
        interval=datetime.timedelta(hours=24),
        first=datetime.time(1, 30),
        # first=5
        job_kwargs={"misfire_grace_time": 300}
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
