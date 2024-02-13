import logging
from logging.handlers import RotatingFileHandler
import datetime
from telegram import (
    KeyboardButton,
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CommandHandler,
    filters
)
from telegram.error import BadRequest, Forbidden
import warnings

import database
from .regular_jobs import no_location_reminder
from .keyboards import (
    manage_farms_keyboard,
    get_product_keyboard,
    get_province_keyboard,
    farms_list_reply,
    edit_keyboard_reply,
    back_button,
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
CHOOSE_ATTR, EDIT_FARM, HANDLE_EDIT, HANDLE_EDIT_LINK = range(4)

MENU_CMDS = ['✍️ ثبت نام', '📤 دعوت از دیگران', '🖼 مشاهده کشت‌ها', '➕ اضافه کردن کشت', '🗑 حذف کشت', '✏️ ویرایش کشت‌ها', '🌦 درخواست اطلاعات هواشناسی', '/start', '/stats', '/send', '/set']
###################################################################
####################### Initialize Database #######################
db = database.Database()
ADMIN_LIST = db.get_admins()
###################################################################
# START OF EDIT CONVERSATION
async def edit_farm_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "start edit")
    user_farms = db.get_farms(user.id)
    if user_farms:
        # await context.bot.send_message(chat_id=user.id, text="یکی از باغ های خود را ویرایش کنید", reply_markup=farms_list(db, user.id, view=False, edit=True))
        await context.bot.send_message(
            chat_id=user.id,
            text="کشت مورد نظر را انتخاب کنید:",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CHOOSE_ATTR
    else:
        await context.bot.send_message(
            chat_id=user.id,
            text="شما هنوز باغی ثبت نکرده اید",
            reply_markup=db.find_start_keyboard(user.id),
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
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    if farm not in user_farms and farm != "↩️ بازگشت":
        db.log_activity(user.id, "error - chose wrong farm", farm)
        await context.bot.send_message(
            chat_id=user.id,
            text="یکی از کشت‌های خود را ویرایش کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CHOOSE_ATTR
    if farm == "↩️ بازگشت":
        db.log_activity(user.id, "back")
        await context.bot.send_message(
            chat_id=user.id, text="عملیات کنسل شد!", reply_markup=db.find_start_keyboard(user.id)
        )
        return ConversationHandler.END
    db.log_activity(user.id, "chose farm to edit", farm)
    message_id = update.effective_message.message_id
    try:
        # await context.bot.edit_message_text(chat_id=user.id, message_id=message_id, text=f"انتخاب مولفه برای ویرایش در {farm}", reply_markup=edit_keyboard())
        await context.bot.send_message(
            chat_id=user.id,
            text=f"یکی از موارد زیر را جهت ویرایش انتخاب کنید:",
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
    farm = user_data["selected_farm"]
    # attr = update.callback_query.data
    attr = update.message.text
    if attr == "بازگشت به لیست کشت‌ها":
        db.log_activity(user.id, "back")
        # await context.bot.edit_message_text(chat_id=user.id, message_id=message_id, text="یکی از باغ های خود را انتخاب کنید",
        #                                reply_markup=farms_list_reply(db, user.id))
        await context.bot.send_message(
            chat_id=user.id,
            text="یکی از کشت‌های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CHOOSE_ATTR
    if attr == "تغییر محصول":
        db.log_activity(user.id, "chose edit product")
        user_data["attr"] = attr
        farm_doc = db.user_collection.find_one({"_id": user.id})["farms"][farm]
        if farm_doc["product"].startswith("پسته"):
            await context.bot.send_message(chat_id=user.id, text="لطفا محصول جدید باغ را انتخاب کنید", reply_markup=get_product_keyboard())
        else:
            await context.bot.send_message(chat_id=user.id, text="لطفا محصول جدید را بنویسید")
        return HANDLE_EDIT
    elif attr == "تغییر استان":
        db.log_activity(user.id, "chose edit province")
        user_data["attr"] = attr
        await context.bot.send_message(
            chat_id=user.id,
            text="لطفا استان جدید را انتخاب کنید یا بنویسید:",
            reply_markup=get_province_keyboard(),
        )
        return HANDLE_EDIT
    elif attr == "تغییر شهرستان":
        db.log_activity(user.id, "chose edit city")
        user_data["attr"] = attr
        await context.bot.send_message(chat_id=user.id, text="لطفا شهر جدید را وارد کنید", reply_markup=back_button())
        return HANDLE_EDIT
    elif attr == "تغییر روستا":
        db.log_activity(user.id, "chose edit village")
        user_data["attr"] = attr
        await context.bot.send_message(
            chat_id=user.id, text="لطفا روستای جدید را وارد کنید", reply_markup=back_button()
        )
        return HANDLE_EDIT
    elif attr == "تغییر مساحت":
        db.log_activity(user.id, "chose edit area")
        user_data["attr"] = attr
        await context.bot.send_message(
            chat_id=user.id, text="لطفا مساحت جدید را وارد کنید", reply_markup=back_button()
        )
        return HANDLE_EDIT
    elif attr == "تغییر موقعیت":
        db.log_activity(user.id, "chose edit location")
        user_data["attr"] = attr
        reply_text = """
لطفا موقعیت (لوکیشن) جدید خود را با انتخاب یکی از روش‌های زیر بفرستید.

🟢 ربات آباد از لوکیشن شما فقط در راستای ارسال توصیه ها استفاده می‌کند.
🟢 متاسفانه آباد امکان ارسال توصیه بدون داشتن لوکیشن باغ شما را ندارد.
🟢 در ارسال لوکیشن مشکل دارید ؟ جهت راهنمایی همین حالا به @agriiadmin پیام دهید.
    """
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
            text=reply_text,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
        return HANDLE_EDIT
    else:
        db.log_activity(user.id, "error - chose wrong value to edit", attr)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
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
        if new_product in MENU_CMDS:
            db.log_activity(user.id, "error - answer in menu_cmd list", new_city)
            await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
            return ConversationHandler.END
        if new_product == "بازگشت":
            db.log_activity(user.id, "back")
            await context.bot.send_message(chat_id=user.id, text = "یکی از موارد زیر را جهت ویرایش انتخاب کنید:", reply_markup=edit_keyboard_reply())
            return EDIT_FARM
        if not new_product:
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
            chat_id=user.id, text=reply_text, reply_markup=db.find_start_keyboard(user.id)
        )
        return ConversationHandler.END
    elif attr == "تغییر استان":
        new_province = update.message.text
        if new_province in MENU_CMDS:
            db.log_activity(user.id, "error - answer in menu_cmd list", new_city)
            await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
            return ConversationHandler.END
        if new_province == "بازگشت":
            await context.bot.send_message(chat_id=user.id, text = "یکی از موارد زیر را جهت ویرایش انتخاب کنید:", reply_markup=edit_keyboard_reply())
            return EDIT_FARM
        if not new_province:
            db.log_activity(user.id, "error - edit province", new_province)
            await update.message.reply_text(
                "لطفا استان جدید را انتخاب کنید",
                reply_markup=get_province_keyboard(),
            )
            return HANDLE_EDIT
        db.set_user_attribute(user.id, f"farms.{farm}.province", new_province)
        reply_text = f"استان جدید {farm} با موفقیت ثبت شد."
        db.log_activity(user.id, "finish edit province")
        await context.bot.send_message(
            chat_id=user.id, text=reply_text, reply_markup=db.find_start_keyboard(user.id)
        )
        return ConversationHandler.END
    elif attr == "تغییر شهرستان":
        new_city = update.message.text
        if new_city == "بازگشت":
            await context.bot.send_message(chat_id=user.id, text = "یکی از موارد زیر را جهت ویرایش انتخاب کنید:", reply_markup=edit_keyboard_reply())
            return EDIT_FARM
        if new_city in MENU_CMDS:
            db.log_activity(user.id, "error - answer in menu_cmd list", new_city)
            await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
            return ConversationHandler.END
        if not new_city:
            db.log_activity(user.id, "error - edit city")
            await update.message.reply_text("لطفا شهرستان جدید را وارد کنید")
            return HANDLE_EDIT
        db.set_user_attribute(user.id, f"farms.{farm}.city", new_city)
        reply_text = f"شهرستان جدید {farm} با موفقیت ثبت شد."
        db.log_activity(user.id, "finish edit city")
        await context.bot.send_message(
            chat_id=user.id, text=reply_text, reply_markup=db.find_start_keyboard(user.id)
        )
        return ConversationHandler.END
    elif attr == "تغییر روستا":
        new_village = update.message.text
        if new_village == "بازگشت":
            await context.bot.send_message(chat_id=user.id, text = "یکی از موارد زیر را جهت ویرایش انتخاب کنید:", reply_markup=edit_keyboard_reply())
            return EDIT_FARM
        if new_village in MENU_CMDS:
            db.log_activity(user.id, "error - answer in menu_cmd list", new_village)
            await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
            return ConversationHandler.END
        if not new_village:
            db.log_activity(user.id, "error - edit village")
            await update.message.reply_text("لطفا روستای جدید را وارد کنید")
            return HANDLE_EDIT
        db.set_user_attribute(user.id, f"farms.{farm}.village", new_village)
        reply_text = f"روستای جدید {farm} با موفقیت ثبت شد."
        db.log_activity(user.id, "finish edit village")
        await context.bot.send_message(
            chat_id=user.id, text=reply_text, reply_markup=db.find_start_keyboard(user.id)
        )
        return ConversationHandler.END
    elif attr == "تغییر مساحت":
        new_area = update.message.text
        if new_area == "بازگشت":
            await context.bot.send_message(chat_id=user.id, text = "یکی از موارد زیر را جهت ویرایش انتخاب کنید:", reply_markup=edit_keyboard_reply())
            return EDIT_FARM
        if new_area in MENU_CMDS:
            db.log_activity(user.id, "error - answer in menu_cmd list", new_area)
            await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
            return ConversationHandler.END
        if not new_area:
            db.log_activity(user.id, "error - edit area")
            await update.message.reply_text("لطفا مساحت جدید را وارد کنید")
            return HANDLE_EDIT
        db.set_user_attribute(user.id, f"farms.{farm}.area", new_area)
        reply_text = f"مساحت جدید {farm} با موفقیت ثبت شد."
        db.log_activity(user.id, "finish edit area")
        await context.bot.send_message(
            chat_id=user.id, text=reply_text, reply_markup=db.find_start_keyboard(user.id)
        )
        return ConversationHandler.END
    elif attr == "تغییر موقعیت":
        new_location = update.message.location
        text = update.message.text
        if text == "بازگشت":
            db.log_activity(user.id, "back")
            await context.bot.send_message(chat_id=user.id, text = "یکی از موارد زیر را جهت ویرایش انتخاب کنید:", reply_markup=edit_keyboard_reply())
            return EDIT_FARM
        if text == "ارسال لینک آدرس (گوگل مپ یا نشان)":
            db.log_activity(user.id, "chose to edit location with link")
            db.set_user_attribute(
                user.id, f"farms.{farm}.location-method", "Link via edit"
            )
            await update.message.reply_text("لطفا لینک آدرس باغ خود را ارسال کنید.", reply_markup=back_button())
            return HANDLE_EDIT_LINK
        if new_location:
            logger.info(f"{update.effective_user.id} chose: new_location sent successfully")
            db.set_user_attribute(
                user.id, f"farms.{farm}.location.longitude", new_location.longitude
            )
            db.set_user_attribute(
                user.id, f"farms.{farm}.location.latitude", new_location.latitude
            )
            db.set_user_attribute(
                user.id, f"farms.{farm}.location-method", "User sent location via edit"
            )
            reply_text = f"موقعیت جدید {farm} با موفقیت ثبت شد."
            db.log_activity(user.id, "finish edit location", f"long: {new_location.longitude}, lat: {new_location.latitude}")
            await context.bot.send_message(
                chat_id=user.id, text=reply_text, reply_markup=db.find_start_keyboard(user.id)
            )
            return ConversationHandler.END
        if not new_location and text != "از نقشه داخل تلگرام انتخاب میکنم":
            logger.info(
                f"{update.effective_user.id} didn't send new_location successfully"
            )
            reply_text = """
ارسال موقعیت جدید باغ با موفقیت انجام نشد.
در ارسال لوکیشن مشکل دارید ؟ جهت راهنمایی همین حالا به @agriiadmin پیام دهید.
            """
            db.log_activity(user.id, "error - edit location", text)
            await context.bot.send_message(
                chat_id=user.id, text=reply_text, reply_markup=edit_keyboard_reply()
            )
            db.set_user_attribute(
                user.id, f"farms.{farm}.location-method", "Unsuccessful via edit"
            )
            context.job_queue.run_once(no_location_reminder, when=datetime.timedelta(hours=1),chat_id=user.id, data=user.username)    
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
    farm = user_data["selected_farm"]
    if text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    if not text:
        db.log_activity(user.id, "error - no location link")
        await update.message.reply_text("لطفا لینک آدرس باغ خود را ارسال کنید.", reply_markup=back_button())
        return HANDLE_EDIT_LINK
    elif text == "بازگشت":
        db.log_activity(user.id, "back")
        reply_text = "لطفا موقعیت باغ (لوکیشن باغ) خود را با انتخاب یکی از روش‌های زیر بفرستید."
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
    db.set_user_attribute(user.id, f"farms.{farm}.link-status", "To be verified")
    db.log_activity(user.id, "finish edit location with link")
    await update.message.reply_text(reply_text, reply_markup=db.find_start_keyboard(user.id))
    context.job_queue.run_once(no_location_reminder, when=datetime.timedelta(hours=1),chat_id=user.id, data=user.username)    
    for admin in ADMIN_LIST:
        data = f"set-location\n{user.id}\n{user_data['selected_farm']}"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("ثبت لوکیشن", callback_data=data)]
        ])
        try:
            await context.bot.send_message(chat_id=admin, text=f"user {user.id} sent us a link for\nname:{user_data['selected_farm']}\n{text}", reply_markup=keyboard)
        except BadRequest or Forbidden:
            logger.warning(f"admin {admin} has deleted the bot")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات کنسل شد!")
    return ConversationHandler.END


edit_farm_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("✏️ ویرایش کشت‌ها"), edit_farm_keyboard)],
        states={
            CHOOSE_ATTR: [MessageHandler(filters.ALL, choose_attr_to_edit)],
            EDIT_FARM: [MessageHandler(filters.ALL, edit_farm)],
            HANDLE_EDIT: [MessageHandler(filters.ALL, handle_edit)],
            HANDLE_EDIT_LINK: [MessageHandler(filters.ALL, handle_edit_link)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )