import logging
from logging.handlers import RotatingFileHandler
import datetime
from telegram import (
    KeyboardButton,
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from telegram.error import BadRequest, Forbidden
from telegram.constants import ParseMode 
import warnings

import database
from .regular_jobs import no_location_reminder
from .keyboards import (
    manage_farms_keyboard,
    get_product_keyboard,
    get_province_keyboard,
    back_button,
    land_type_keyboard
)
from .logger import logger
from .sms_funcs import sms_incomplete_farm
from .number_transformer import extract_number
# Constants for ConversationHandler states
(
    ASK_TYPE,
    ASK_PRODUCT,
    HANDLE_PRODUCT,
    ASK_PROVINCE,
    ASK_CITY,
    ASK_VILLAGE,
    ASK_AREA,
    ASK_LOCATION,
    HANDLE_LOCATION,
    HANDLE_LINK
) = range(10)

MENU_CMDS = ['✍️ ثبت نام', '📤 دعوت از دیگران', '🖼 مشاهده کشت‌ها', '➕ اضافه کردن کشت', '🗑 حذف کشت', '✏️ ویرایش کشت‌ها', '🌦 درخواست اطلاعات هواشناسی', '/start', '/stats', '/send', '/set']

MESSAGES = {
    ""
}
###################################################################
####################### Initialize Database #######################
db = database.Database()
ADMIN_LIST = db.get_admins()

# START OF ADD_FARM CONVERSATION
async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "start add farm")
    if not db.check_if_user_is_registered(user_id=user.id):
        db.log_activity(user.id, "error - add farm", "not registered yet")
        await update.message.reply_text(
            "لطفا پیش از افزودن باغ از طریق /start ثبت نام کنید",
            reply_markup=db.find_start_keyboard(user.id),
        )
        return ConversationHandler.END
    reply_text = """
لطفا برای تشخیص این کشت یک نام وارد کنید:
مثلا: باغ پسته
"""
    await update.message.reply_text(reply_text, reply_markup=back_button())
    job_data = {"timestamp": datetime.datetime.now().strftime("%Y%m%d %H%M")}
    if datetime.time(2, 30).strftime("%H%M") <= datetime.datetime.now().strftime("%H%M") < datetime.time(17, 30).strftime("%H%M"): 
        context.job_queue.run_once(sms_incomplete_farm, when=datetime.timedelta(hours=1), chat_id=user.id, data=job_data)
    else:
        context.job_queue.run_once(sms_incomplete_farm, when=datetime.time(4, 30), chat_id=user.id, data=job_data) 
    return ASK_TYPE


async def ask_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives and handles <<name>>"""
    user = update.effective_user
    user_data = context.user_data
    message_text = update.message.text
    if message_text == "بازگشت":
        db.log_activity(user.id, "back")
        await update.message.reply_text("عمیلات لغو شد", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif update.message.text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", update.message.text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif "." in message_text:
        db.log_activity(user.id, "error - chose name with .", f"{message_text}")
        reply_text = (
                "نام باغ نباید شامل <b>.</b> باشد. لطفا یک نام دیگر انتخاب کنید"
            )
        await update.message.reply_text(reply_text, reply_markup=back_button(), parse_mode=ParseMode.HTML)
        return ASK_TYPE
    elif not message_text:
        db.log_activity(user.id, "error - no name received")
        reply_text = """
لطفا برای تشخیص این کشت یک نام وارد کنید:
مثلا: باغ پسته
"""
        await update.message.reply_text(reply_text, reply_markup=back_button())
        return ASK_TYPE
    elif db.user_collection.find_one({"_id": user.id}).get("farms"):
        used_farm_names = db.user_collection.find_one({"_id": user.id})["farms"].keys()
        if message_text in used_farm_names:
            db.log_activity(user.id, "error - chose same name", f"{message_text}")
            reply_text = (
                "شما قبلا از این نام استفاده کرده‌اید. لطفا یک نام جدید انتخاب کنید."
            )
            await update.message.reply_text(reply_text, reply_markup=back_button())
            return ASK_TYPE
    farm_name = message_text.strip()
    user_data["farm_name"] = farm_name
    db.log_activity(user.id, "chose name", farm_name)
    new_farm_dict = {
        "type": None,
        "product": None,
        "province": None,
        "city": None,
        "village": None,
        "area": None,
        "location": {"latitude": None, "longitude": None},
        "location-method": None
    }
    db.add_new_farm(user_id=user.id, farm_name=farm_name, new_farm=new_farm_dict)
    reply_text = """
لطفا نوع کشت خود را انتخاب کنید. 
اگر نوع کشت شما در گزینه‌‌ها نیست آن را بنویسید.
"""
    # await update.message.reply_text(reply_text, reply_markup=back_button())
    await update.message.reply_text(reply_text, reply_markup=land_type_keyboard())
    return ASK_PRODUCT
    

async def ask_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives and handles <<land_type>>"""
    user = update.effective_user
    user_data = context.user_data
    message_text = update.message.text
    # logger.info(update.message.text)
    if message_text == "بازگشت":
        db.log_activity(user.id, "back")
        reply_text = """
لطفا برای تشخیص این کشت یک نام وارد کنید:
مثلا: باغ پسته
"""
        await update.message.reply_text(reply_text, reply_markup=back_button())
        return ASK_TYPE
    elif message_text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", message_text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif "." in message_text:
        db.log_activity(user.id, "error - chose land type with .", f"{update.message.text}")
        reply_text = (
                "نوع کشت نمی‌تواند شامل <b>.</b> باشد. لطفا دوباره آن را وارد کنید."
            )
        await update.message.reply_text(reply_text, reply_markup=land_type_keyboard(), parse_mode=ParseMode.HTML)
        return ASK_PRODUCT
    elif not message_text:
        db.log_activity(user.id, "error - no name received")
        reply_text = """
لطفا نوع کشت خود را انتخاب کنید. 
اگر نوع کشت شما در گزینه‌‌ها نیست آن را بنویسید.
"""
        await update.message.reply_text(reply_text, reply_markup=land_type_keyboard())
        return ASK_PRODUCT
    

    farm_name = user_data["farm_name"]
    land_type = message_text.strip()
    user_data["land_type"] = land_type
    db.log_activity(user.id, "chose land type", land_type)
    db.set_user_attribute(user.id, f"farms.{farm_name}.type", land_type)
    if land_type == "باغ":
        await update.message.reply_text(
            "لطفا محصول باغ را انتخاب کنید. \nدر صورتی‌‌‌که باغ پسته ندارید محصول باغ خود را بنویسید.", 
            reply_markup=ReplyKeyboardMarkup([["پسته", "بازگشت"]], resize_keyboard=True, one_time_keyboard=True))
        return HANDLE_PRODUCT
    else:
        await update.message.reply_text("چه محصولی پرورش می‌دهید؟", reply_markup=back_button()
        )
        return ASK_PROVINCE


async def handle_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the products"""
    user = update.effective_user
    user_data = context.user_data
    land_type = user_data["land_type"]
    message_text = update.message.text
    # logger.info(update.message.text)
    if message_text == "بازگشت":
        db.log_activity(user.id, "back")
        reply_text = """
لطفا نوع کشت خود را انتخاب کنید. 
اگر نوع کشت شما در گزینه‌‌ها نیست آن را بنویسید.
"""
        await update.message.reply_text(reply_text, reply_markup=land_type_keyboard())
        return ASK_PRODUCT
    elif message_text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", message_text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif "." in message_text:
        db.log_activity(user.id, "error - chose product with .", f"{message_text}")
        reply_text = (
                "نام محصول نباید شامل <b>.</b> باشد. لطفا یک بار دیگر نام محصول را بدون <b>.</b> وارد کنید."
            )
        await update.message.reply_text(reply_text, reply_markup=back_button(), parse_mode=ParseMode.HTML)
        return HANDLE_PRODUCT
    elif not message_text:
        db.log_activity(user.id, "error - no product received")
        if land_type == "باغ":
            keyboard = ReplyKeyboardMarkup([["پسته", "بازگشت"]], resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text(
                "لطفا محصول باغ را انتخاب کنید. \nدر صورتی‌‌‌که باغ پسته ندارید محصول باغ خود را بنویسید.", reply_markup=keyboard
            )
            return HANDLE_PRODUCT
        else:
            await update.message.reply_text("چه محصولی پرورش می‌دهید؟", reply_markup=back_button()
            )
            return HANDLE_PRODUCT
    user_data["farm_product"] = message_text
    if land_type == "باغ" and message_text == "پسته":
        db.log_activity(user.id, "chose product", "پسته")
        await update.message.reply_text(
            "لطفا نوع پسته باغ خود را انتخاب کنید", reply_markup=get_product_keyboard()
        )
        return ASK_PROVINCE
    else:
        await update.message.reply_text(
            "لطفا یک بار دیگر محصول خود را وارد کنید.")
        return ASK_PROVINCE

async def ask_province(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ 
    If land_type==باغ this function receives output of handle_product
    Otherwise will receive output of ask_product
    """
    user = update.effective_user
    user_data = context.user_data
    message_text = update.message.text
    land_type = user_data["land_type"]

    if message_text == "بازگشت":
        db.log_activity(user.id, "back")
        if land_type != "باغ":
            reply_text = """
لطفا نوع کشت خود را انتخاب کنید. 
اگر نوع کشت شما در گزینه‌‌ها نیست آن را بنویسید.
"""
            await update.message.reply_text(reply_text, reply_markup=land_type_keyboard())
            return ASK_PRODUCT
        else:
            await update.message.reply_text(
            "لطفا محصول باغ را انتخاب کنید. \nدر صورتی‌‌‌که باغ پسته ندارید محصول باغ خود را بنویسید.", 
            reply_markup=ReplyKeyboardMarkup([["پسته", "بازگشت"]], resize_keyboard=True, one_time_keyboard=True))
            return HANDLE_PRODUCT
    # Get the answer to the province question
    elif message_text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", message_text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif not message_text or "." in message_text:
        db.log_activity(user.id, "error - chose wrong product", f"{update.message.text}")
        await update.message.reply_text(
            "لطفا فرایند را از ابتدا شروع کنید.", reply_markup=get_product_keyboard()
        )
        return ConversationHandler.END
    product = message_text.strip()
    if product.startswith("پسته"):
        product = "پسته"
    farm_name = user_data["farm_name"]
    db.set_user_attribute(user.id, f"farms.{farm_name}.product", product)
    db.log_activity(user.id, "chose product", f"{product}")
    await update.message.reply_text(
        "لطفا استان خود را انتخاب کنید. \nاگر استان شما در گزینه‌ها نبود آن را بنویسید", reply_markup=get_province_keyboard()
    )
    return ASK_CITY

async def ask_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    message_text = update.message.text
    land_type = user_data["land_type"]

    if message_text == "بازگشت":
        db.log_activity(user.id, "back")
        if land_type != "باغ":
            await update.message.reply_text("چه محصولی پرورش می‌دهید؟", reply_markup=back_button()
        )
            return ASK_PROVINCE
        else:
            await update.message.reply_text(
            "لطفا محصول باغ را انتخاب کنید. \nدر صورتی‌‌‌که باغ پسته ندارید محصول باغ خود را بنویسید.", 
            reply_markup=ReplyKeyboardMarkup([["پسته", "بازگشت"]], resize_keyboard=True, one_time_keyboard=True))
            return HANDLE_PRODUCT

        # await update.message.reply_text(
        #     "لطفا محصول باغ را انتخاب کنید", reply_markup=get_product_keyboard()
        # )
        # return ASK_PROVINCE
    # Get the answer to the province question
    elif message_text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", message_text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif not message_text:
        db.log_activity(user.id, "error - chose wrong province", f"{update.message.text}")
        await update.message.reply_text(
            "لطفا استان محل کشت خود را انتخاب کنید یا آن را بنویسید",
            reply_markup=get_province_keyboard(),
        )
        return ASK_CITY
    province = message_text.strip()
    farm_name = user_data["farm_name"]
    db.set_user_attribute(user.id, f"farms.{farm_name}.province", province)
    db.log_activity(user.id, "chose province", f"{province}")
    await update.message.reply_text(
        "لطفا شهرستان محل کشت را وارد کنید:", reply_markup=back_button()
    )
    return ASK_VILLAGE

async def ask_village(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        db.log_activity(user.id, "back")
        await update.message.reply_text(
            "لطفا استان محل کشت خود را انتخاب کنید:",
            reply_markup=get_province_keyboard(),
        )
        return ASK_CITY
    # Get the answer to the province question
    if update.message.text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", update.message.text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    if not update.message.text:
        db.log_activity(user.id, "error - city")
        await update.message.reply_text(
            "لطفا شهرستان محل کشت را وارد کنید:", reply_markup=back_button()
        )
        return ASK_VILLAGE
    city = update.message.text.strip()
    farm_name = user_data["farm_name"]
    db.set_user_attribute(user.id, f"farms.{farm_name}.city", city)
    db.log_activity(user.id, "entered city", f"{city}")
    await update.message.reply_text(
        "لطفا روستای محل کشت و آدرس حدودی آن را وارد کنید:", reply_markup=back_button()
    )
    return ASK_AREA

async def ask_area(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        db.log_activity(user.id, "back")
        await update.message.reply_text("لطفا شهرستان محل کشت را وارد کنید:", reply_markup=back_button())
        return ASK_VILLAGE
    # Get the answer to the village question
    if update.message.text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", update.message.text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    if not update.message.text:
        db.log_activity(user.id, "error - village")
        await update.message.reply_text(
            "لطفا روستای محل کشت و آدرس حدودی آن را وارد کنید:", reply_markup=back_button()
        )
        return ASK_AREA
    village = update.message.text.strip()
    farm_name = user_data["farm_name"]
    db.set_user_attribute(user.id, f"farms.{farm_name}.village", village)
    db.log_activity(user.id, "entered village", f"{village}")
    await update.message.reply_text("لطفا متراژ کشت خود را به هکتار وارد کنید:", reply_markup=back_button())
    return ASK_LOCATION

async def ask_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        db.log_activity(user.id, "back")
        await update.message.reply_text("لطفا روستای محل کشت و آدرس حدودی آن را وارد کنید:", reply_markup=back_button())
        return ASK_AREA
    # Get the answer to the phone number question
    if update.message.text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", update.message.text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    if not update.message.text:
        db.log_activity(user.id, "error - area")
        await update.message.reply_text("لطفا متراژ کشت خود را به هکتار وارد کنید:", reply_markup=back_button())
        return ASK_LOCATION
    area = update.message.text.strip()
    area = extract_number(area)
    if not area:
        db.log_activity(user.id, "error - area", update.message.text)
        await update.message.reply_text("لطفا متراژ کشت خود را به صورت عددی با واحد هکتار وارد کنید مثلا:\n<b>1.5</b>", parse_mode=ParseMode.HTML, reply_markup=back_button())
        return ASK_LOCATION
    user_data["area"] = area
    farm_name = user_data["farm_name"]
    db.set_user_attribute(user.id, f"farms.{farm_name}.area", area)
    db.log_activity(user.id, "entered area", f"{area}")
    reply_text = """
لطفا موقعیت باغ (لوکیشن باغ) خود را با انتخاب یکی از روش‌های زیر بفرستید.

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
    await update.message.reply_text(
        reply_text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return HANDLE_LOCATION

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        db.log_activity(user.id, "back")
        await update.message.reply_text("لطفا متراژ کشت خود را به هکتار وارد کنید:", reply_markup=back_button())
        return ASK_LOCATION
    if update.message.text == "ارسال لینک آدرس (گوگل مپ یا نشان)":
        db.log_activity(user.id, "chose location link")
        reply_text = """
 لطفا مطابق فیلم راهنما لینک موقعیت باغ خود را از گوگل مپ یا نشان ارسال کنید.
 
👉 https://t.me/agriweath/59 

در صورت نیاز به راهنمایی بیشتر همین حالا به @agriiadmin پیام دهید.
"""
        await update.message.reply_text(reply_text, reply_markup=back_button())
        return HANDLE_LINK
            
    farm_name = user_data["farm_name"]

    # Get the user's location
    location = update.message.location
    text = update.message.text
    if location:
        db.log_activity(user.id, "sent location", f"long:{location['longitude']}, lat: {location['latitude']}")
        logger.info(f"{update.effective_user.id} chose: ersal location online")

        db.set_user_attribute(user.id, f"farms.{farm_name}.location.latitude", location.latitude)
        db.set_user_attribute(user.id, f"farms.{farm_name}.location.longitude", location.longitude)
        db.set_user_attribute(user.id, f"farms.{farm_name}.location-method", "User sent location")

        db.log_activity(user.id, "finished add farm - gave location", farm_name)
        reply_text = f"""
باغ شما با نام <{farm_name}> با موفقیت ثبت شد.
توصیه‌های مرتبط با شرایط آب‌و‌هوایی از روزهای آینده برای شما ارسال خواهد  شد.
برای ویرایش یا مشاهده اطلاعات باغ از گزینه‌های مرتبط در /start استفاده کنید.
"""
        await update.message.reply_text(reply_text, reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    if not location and text != "از نقشه داخل تلگرام انتخاب میکنم":
        db.log_activity(user.id, "error - location", text)
        logger.info(f"{update.effective_user.id} didn't send location successfully")
        reply_text = "ارسال موقعیت باغ با موفقیت انجام نشد. می توانید از طریق ویرایش باغ، موقعیت آن را ثبت کنید."
        
        db.set_user_attribute(user.id, f"farms.{farm_name}.location-method", "Unsuccessful")
        db.log_activity(user.id, "finish add farm - no location", farm_name)
        
        context.job_queue.run_once(no_location_reminder, when=datetime.timedelta(hours=1),chat_id=user.id, data=user.username)    
        await update.message.reply_text(reply_text, reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif text == "از نقشه داخل تلگرام انتخاب میکنم":
        db.log_activity(user.id, "chose to send location from map")
        logger.info(f"{update.effective_user.id} chose: az google map entekhab mikonam")
        reply_text = """
        مطابق فیلم راهنما موقعیت (لوکیشن) باغ خود را انتخاب کنید
        
        👉  https://t.me/agriweath/2
        """
        await update.message.reply_text(reply_text, reply_markup=back_button())
        return HANDLE_LOCATION

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    text = update.message.text
    farm_name = user_data["farm_name"]
    if text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", update.message.text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif not text:
        db.log_activity(user.id, "error - no location link")
        await update.message.reply_text("لطفا لینک آدرس باغ خود را ارسال کنید.", reply_markup=back_button())
        return HANDLE_LINK
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
        return HANDLE_LOCATION
    else:
        db.log_activity(user.id, "sent location link", text)
        reply_text = "ارسال لینک آدرس باغ با موفقیت انجام شد. لطفا تا بررسی ادمین منتظر بمانید.\n از شکیبایی شما سپاسگزاریم."
        db.set_user_attribute(user.id, f"farms.{farm_name}.location-method", "Link")
        db.set_user_attribute(user.id, f"farms.{farm_name}.link-status", "To be verified")
        db.log_activity(user.id, "finish add farm with location link", farm_name)
        context.job_queue.run_once(no_location_reminder, when=datetime.timedelta(hours=1), chat_id=user.id, data=user.username)    
        await update.message.reply_text(reply_text, reply_markup=db.find_start_keyboard(user.id))
        for admin in ADMIN_LIST:
            data = f"set-location\n{user.id}\n{farm_name}"
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("ثبت لوکیشن", callback_data=data)]
            ])
            try:
                await context.bot.send_message(chat_id=admin, text=f"user {user.id} sent us a link for\nname:{farm_name}\n{text}",reply_markup=keyboard)
            except BadRequest or Forbidden:
                logger.warning(f"admin {admin} has deleted the bot")
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات کنسل شد!")
    return ConversationHandler.END


add_farm_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("➕ اضافه کردن کشت"), add)],
        states={
            ASK_TYPE: [MessageHandler(filters.TEXT, ask_type)],
            ASK_PRODUCT: [MessageHandler(filters.TEXT, ask_product)],
            HANDLE_PRODUCT: [MessageHandler(filters.TEXT, handle_product)],
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