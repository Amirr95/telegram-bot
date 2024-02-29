import logging
from logging.handlers import RotatingFileHandler
from telegram import (
    Update,
)
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from telegram.constants import ParseMode
import warnings
import database
from pg_sync import check_user_in_postgres, delete_farm_from_pg
from .keyboards import (
    manage_farms_keyboard,
    farms_list_reply,
    conf_del_keyboard,
)

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
CONFIRM_DELETE, DELETE_FARM = range(2)
MENU_CMDS = ['✍️ ثبت نام', '📤 دعوت از دیگران', '🖼 مشاهده کشت‌ها', '➕ اضافه کردن کشت', '🗑 حذف کشت', '✏️ ویرایش کشت‌ها', '🌦 درخواست اطلاعات هواشناسی', '/start', '/stats', '/send', '/set']
###################################################################
####################### Initialize Database #######################
db = database.Database()
ADMIN_LIST = db.get_admins()

# START OF DELETE CONVERSATION
async def delete_farm_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "start delete process")
    user_farms = db.get_farms(user.id)
    if user_farms:
        await update.message.reply_text(
            "یکی از کشت‌های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CONFIRM_DELETE
    else:
        await update.message.reply_text(
            "شما هنوز باغی ثبت نکرده اید", reply_markup=db.find_start_keyboard(user.id)
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
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    if farm not in user_farms_names and farm != "↩️ بازگشت":
        db.log_activity(user.id, "error - wrong farm to delete", farm)
        await context.bot.send_message(
            chat_id=user.id,
            text="یکی از کشت‌های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CONFIRM_DELETE
    if farm == "↩️ بازگشت":
        db.log_activity(user.id, "back")
        await context.bot.send_message(
            chat_id=user.id, text="عملیات کنسل شد!", reply_markup=db.find_start_keyboard(user.id)
        )
        return ConversationHandler.END
    db.log_activity(user.id, "chose farm to delete", farm)
    location = user_farms.get(farm)["location"]
    text = f"""
آیا از حذف <b>{farm}</b> با مشخصات زیر اطمینان دارید؟
محصول: {user_farms[farm].get("product")}
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
    phone_number = db.get_user_attribute(user.id, "phone-number")
    farm = user_data["farm_to_delete"]
    answer = update.message.text
    acceptable = ["بله", "خیر", "بازگشت"]
    if answer not in acceptable:
        db.log_activity(user.id, "error - wrong delete confirmation", answer)
        await context.bot.send_message(
            chat_id=user.id, text="عملیات موفق نبود", reply_markup=db.find_start_keyboard(user.id)
        )
        return ConversationHandler.END
    elif answer == "بازگشت":
        db.log_activity(user.id, "back")
        await context.bot.send_message(
            chat_id=user.id,
            text="یکی از کشت‌های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CONFIRM_DELETE
    elif answer == "خیر":
        db.log_activity(user.id, "stopped delete")
        await context.bot.send_message(
            chat_id=user.id, text="عملیات لغو شد", reply_markup=db.find_start_keyboard(user.id)
        )
        return ConversationHandler.END
    elif answer == "بله":
        db.log_activity(user.id, "confirmed delete")
        delete_farm_from_pg(phone_number, farm)
        try:
            db.user_collection.update_one(
                {"_id": user.id}, {"$unset": {f"farms.{farm}": ""}}
            )
            text = f"{farm} با موفقیت حذف شد."
            await context.bot.send_message(
                chat_id=user.id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=db.find_start_keyboard(user.id),
            )
            return ConversationHandler.END
        except KeyError:
            logger.info(f"DELETE: key {farm} doesn't exist for user {user.id}.")
            return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات کنسل شد!")
    return ConversationHandler.END


delete_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("🗑 حذف کشت"), delete_farm_keyboard)
        ],
        states={
            CONFIRM_DELETE: [MessageHandler(filters.ALL, confirm_delete)],
            DELETE_FARM: [MessageHandler(filters.ALL, delete_farm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )