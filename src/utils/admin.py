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
from telegram.error import BadRequest, Forbidden
import os
import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import warnings
import database
from .sms_funcs import sms_block
from .keyboards import (
    stats_keyboard,
    back_button,
    choose_role
)
from .regular_jobs import send_todays_data


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
CHOOSE_RECEIVERS, HANDLE_IDS, BROADCAST = range(3)
ASK_FARM_NAME, ASK_LONGITUDE, ASK_LATITUDE, HANDLE_LAT_LONG = range(4)
MENU_CMDS = ['✍️ ثبت نام', '📤 دعوت از دیگران', '🖼 مشاهده کشت‌ها', '➕ اضافه کردن کشت', '🗑 حذف کشت', '✏️ ویرایش کشت‌ها', '🌦 درخواست اطلاعات هواشناسی', '/start', '/stats', '/send', '/set']
###################################################################
####################### Initialize Database #######################
db = database.Database()
ADMIN_LIST = db.get_admins()
###################################################################

# Start of /send conversation
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
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif not message_text:
        await update.message.reply_text(
            "گیرنده پیام کیست؟",
            reply_markup=choose_role()
        )
        return CHOOSE_RECEIVERS
    elif message_text == "/cancel":
        db.log_activity(user.id, "/cancel")
        await update.message.reply_text("عملیات کنسل شد!", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif message_text == "بازگشت":
        db.log_activity(user.id, "back")
        await update.message.reply_text("عملیات کنسل شد!", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif message_text == "تمام کاربران":
        db.log_activity(user.id, "chose /send to all users")
        user_data["receiver_list"] = db.user_collection.distinct("_id")
        user_data["receiver_type"] = "to All Users"
        await update.message.reply_text("لطفا پیام مورد نظرتان را بنویسید یا برای لغو /cancel را بزنید:", 
                                  reply_markup=back_button())
        return BROADCAST
    elif message_text == "پسته‌کاران":
        db.log_activity(user.id, "chose /send to pesteh farmers")
        user_data["receiver_list"] = db.get_all_pesteh_farmers()
        user_data["receiver_type"] = "to pesteh farmers"
        await update.message.reply_text("لطفا پیام مورد نظرتان را بنویسید یا برای لغو /cancel را بزنید:", 
                                  reply_markup=back_button())
        return BROADCAST
    elif message_text == "دکمه ثبت نام را نزدند":
        db.log_activity(user.id, "chose /send to users who never pressed register")
        user_data["receiver_list"] = db.register_not_pressed()
        user_data["receiver_type"] = "to users who started the bot but didn't press register btn"
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
        await update.message.reply_text("عملیات کنسل شد!", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END

async def handle_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ids = update.message.text
    user = update.effective_user
    user_data = context.user_data
    if ids in MENU_CMDS or not ids:
        db.log_activity(user.id, "error - answer in menu_cmd list", ids)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
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
        await update.message.reply_text("عملیات کنسل شد!", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif message_text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", message_text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
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
                if datetime.time(5).strftime("%H%M") <= datetime.datetime.now().strftime("%H%M") < datetime.time(19).strftime("%H%M"): 
                    context.job_queue.run_once(sms_block, when=datetime.timedelta(minutes=30), chat_id=user_id, data={})
                else:
                    context.job_queue.run_once(sms_block, when=datetime.time(4, 30), chat_id=user_id, data={}) 
            except BadRequest:
                logger.error(f"chat with {user_id} not found.")
                await context.bot.send_message(chat_id=user.id, text=f"{user_id} was not found")
        db.log_sent_messages(receivers, f"broadcast {user_data['receiver_type']}")
        for id in ADMIN_LIST:
            try:
                await context.bot.send_message(id, f"پیام برای {i} نفر از {len(receiver_list)} نفر ارسال شد."
                                    , reply_markup=db.find_start_keyboard(id))
            except BadRequest or Forbidden:
                logger.warning(f"admin {id} has deleted the bot")
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات کنسل شد!")
    return ConversationHandler.END


async def backup_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_LIST:
        return
    context.job_queue.run_once(send_todays_data, when=10)
    for admin in ADMIN_LIST:
        try:
            context.bot
        except BadRequest or Forbidden:
            logger.error(f"Problem sending a message to admin: {admin}")

# Stats functions
async def bot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in ADMIN_LIST:
        await update.message.reply_text(
            "آمار مورد نظر را انتخاب کنید", reply_markup=stats_keyboard()
        )

async def stats_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stat = update.callback_query
    try:
        await stat.answer()
    except BadRequest:
        logger.error(f"query.answer() caused BadRequest error. user: {stat.message.chat.id}")
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


broadcast_handler = ConversationHandler(
        entry_points=[CommandHandler("send", send)],
        states={
            CHOOSE_RECEIVERS: [MessageHandler(filters.ALL, choose_receivers)],
            HANDLE_IDS: [MessageHandler(filters.ALL, handle_ids)],
            BROADCAST: [MessageHandler(filters.ALL, broadcast)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )