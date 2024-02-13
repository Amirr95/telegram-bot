from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from telegram.error import Forbidden, BadRequest
from telegram.constants import ParseMode

import datetime
import jdatetime
import rasterio
from rasterio.errors import RasterioIOError
from rasterio.transform import rowcol
import warnings

import database

from .logger import logger
from .keyboards import (
    farms_list_reply,
    automn_month,
    automn_week,
    get_product_keyboard
)
from .table_generator import chilling_hours_table, remaining_chilling_hours_table

warnings.filterwarnings("ignore", category=UserWarning)

AUTOMN_MONTH, AUTOMN_WEEK, SET_AUTOMN_TIME, CONFIRM_PRODUCT = range(4)
MENU_CMDS = ['✍️ ثبت نام', '📤 دعوت از دیگران', '🖼 مشاهده کشت‌ها', '➕ اضافه کردن کشت', '🗑 حذف کشت', '✏️ ویرایش کشت‌ها', '🌦 درخواست اطلاعات هواشناسی', '/start', '/stats', '/send', '/set']
###################################################################
####################### Initialize Database #######################
db = database.Database()


# Calculate chilling hours
def calculate_chilling_hours(automn_time: str, longitude: float, latitude: float) -> dict[str, float]:
    methods = ['Chilling_Hours', 'Chilling_Hours_7', 'Dynamic', 'Utah']
    hours = {}
    for method in methods:
        with rasterio.open(f"data/Daily_{method}.tif") as src:
            row, col = rowcol(src.transform, longitude, latitude)
            
            pixel_values = []
            for band in range(1, src.count + 1):
                pixel_values.append(src.read(band)[row, col])
        automn_time_to_start_band_index = {
            "هفته اول - آبان": 0,
            "هفته دوم - آبان": 0,
            "هفته سوم - آبان": 3,
            "هفته چهارم - آبان": 10,
            "هفته اول - آذر": 24,
            "هفته دوم - آذر": 31,
            "هفته سوم - آذر": 38,
            "هفته چهارم - آذر": 45,
        }

        start_band_index = automn_time_to_start_band_index.get(automn_time)    
        hours[method] = round(sum(pixel_values[start_band_index:]))
    return hours


async def show_remaining_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback Query that generates a table showing the user how many hours remain
    for their farm
    """
    query = update.callback_query
    user = query.from_user
    try:
        await query.answer()
    except BadRequest:
        logger.error(f"query.answer() caused BadRequest error. user: {query.message.chat.id}")
    hours = int(query.data.split("\n")[1])
    pesteh_types = [
        "کرمان - رقم ماده غالب کالیفرنیا",
        "کله قوچی", 
        "اوحدی (فندقی)", 
        "احمدآقایی", 
        "اکبری", 
        "فندقی غفوری", 
        "چروک"
    ]
    complete_hours = [1000, 600, 800, 1000, 1200, 1200, 1400]
    hours_difference = [hours - el for el in complete_hours]
    remaining_chilling_hours_table(pesteh_types, complete_hours, hours_difference, hours)
    try:
        caption = f"ساعات باقیمانده نیاز سرمایی ارقام مختلف پسته در باغ شما بر اساس روش <b>0 تا 7</b>"
        with open('table.png', 'rb') as image_file:
            await context.bot.send_photo(chat_id=user.id, photo=image_file, caption=caption, reply_markup=db.find_start_keyboard(user.id), parse_mode=ParseMode.HTML, read_timeout=15, write_timeout=30)
        
        db.log_activity(user.id, "received remaining hours info")
    except Forbidden or BadRequest:
        logger.info("encountered error trying to respond to CallbackQueryHandler")
        db.log_activity(user.id, "error - couldn't receive remaining hours info")
    except:
        logger.info("Unexpected error") # Could be message not modified?
        db.log_activity(user.id, "error - couldn't receive remaining hours info")
    
# START OF AUTOMN TIME CONVERSATION
async def automn_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "start to set automn time")
    if db.check_if_user_has_pesteh(user.id):
        await context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id, True),
        )
        return AUTOMN_MONTH
    else:
        db.log_activity(user.id, "error - no pesteh farms to set automn time")
        await context.bot.send_message(
            chat_id=user.id,
            text="شما هنوز باغ پسته‌ای ثبت نکرده اید",
            reply_markup=db.find_start_keyboard(user.id),
        )
        return ConversationHandler.END

async def ask_automn_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    farm = update.message.text
    user_farms = db.get_farms(user.id)
    
    if farm == '↩️ بازگشت':
        db.log_activity(user.id, "back")
        await update.message.reply_text("عملیات لغو شد", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif farm not in list(user_farms.keys()):
        db.log_activity(user.id, "error - chose farm for automn time" , farm)
        await update.message.reply_text("لطفا دوباره تلاش کنید. نام باغ اشتباه بود", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif farm in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", farm)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    
    db.log_activity(user.id, f"chose farm for setting automn time", farm)
    if user_farms[farm].get("automn-time"):
        if user_farms[farm].get("location", {}).get("longitude") and user_farms[farm].get("location", {}).get("latitude"):
            reply_text = f"این ساعت‌ها با توجه به موقعیت و زمان خزان ثبت‌شده توسط شما <b>({user_farms[farm].get('automn-time')})</b> برای باغ شما: #<b>{farm.replace(' ', '_')}</b> محاسبه شده‌اند"
            try:
                hours = calculate_chilling_hours(user_farms[farm].get("automn-time"), user_farms[farm].get("location", {}).get("longitude"), user_farms[farm].get("location", {}).get("latitude"))
                chilling_hours_table(["صفر تا هفت", "زیر هفت", "دینامیک", "یوتا"],
                                    [(jdatetime.date.today() - jdatetime.timedelta(days=1 )).strftime("%Y/%m/%d")] * 4,
                                    [hours["Chilling_Hours"], hours["Chilling_Hours_7"], hours["Dynamic"], hours["Utah"]],
                                    "chill-table.png")
                data = f"gdd\n{hours['Chilling_Hours']}"
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("مشاهده نیازمندی رقم‌های مختلف", callback_data=data)]
                ])
                with open('chill-table.png', 'rb') as image_file:
                    await context.bot.send_photo(chat_id=user.id, photo=image_file, caption=reply_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
                # db.log_activity(user.id, "automn time of farm was already set", farm)
                db.log_activity(user.id, "received chilling hours report", hours)
                # await update.message.reply_text(reply_text, reply_markup=db.find_start_keyboard(user.id))
                return ConversationHandler.END
            except RasterioIOError:
                logger.info(f"{user.id} requested chilling hours. File was not found!")
                await context.bot.send_message(chat_id=user.id, text="متاسفانه اطلاعات باغ شما در حال حاضر موجود نیست", reply_markup=db.find_start_keyboard(user.id))
                return ConversationHandler.END
            except IndexError:
                logger.info(f"{user.id} requested chilling hours data for {farm} which is outside Iran\nLocation:{user_farms[farm].get('location')}!")
                msg = """
                متاسفانه مکان باغ شما خارج از مناطق تحت پوشش آباد است. شما می‌توانید از مسیر
                <b>بازگشت به خانه --> مدیریت کشت‌ها --> ویرایش کشت‌ها</b> لوکیشن باغ خود را ویرایش کنید.
                """
                await context.bot.send_message(chat_id=user.id, text=msg, reply_markup=db.find_start_keyboard(user.id), parse_mode=ParseMode.HTML)
                return ConversationHandler.END
                
        else:
            db.log_activity(user.id, "error - chose farm for automn time" , farm)
            await update.message.reply_text("پیش از دریافت نیاز سرمایی باید مختصات باغ خود را ثبت کنید.", reply_markup=db.find_start_keyboard(user.id))
            return ConversationHandler.END
    else:
        user_data["set-automn-time-of-farm"] = farm
        reply_text = "برای محاسبه نیاز سرمایی لطفا زمان خزان باغ خود را ثبت کنید."
        await update.message.reply_text(reply_text, reply_markup=automn_month())
        return AUTOMN_WEEK
    
async def ask_automn_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    month = update.message.text
    acceptable_months = ["آبان", "آذر"]
    if month == '↩️ بازگشت':
        db.log_activity(user.id, "back")
        await context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id, True),
        )
        return AUTOMN_MONTH
    elif month in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", month)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif month not in acceptable_months:
        db.log_activity(user.id, "error - chose wrong month for automn time" , month)
        await update.message.reply_text("لطفا دوباره تلاش کنید. ماه انتخاب شده اشتباه بود.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    db.log_activity(user.id, "chose month for automn time" , month)
    user_data["automn-month"] = month
    reply_text = "هفته خزان باغ خود را انتخاب کنید."
    await update.message.reply_text(reply_text, reply_markup=automn_week())
    return SET_AUTOMN_TIME

async def set_automn_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    week = update.message.text
    acceptable_weeks = ['هفته دوم', 'هفته اول', 'هفته چهارم', 'هفته سوم']
    if week == '↩️ بازگشت':
        db.log_activity(user.id, "back")
        reply_text = "برای محاسبه نیاز سرمایی لطفا زمان خزان باغ خود را ثبت کنید."
        await update.message.reply_text(reply_text, reply_markup=automn_month())
        return AUTOMN_WEEK
    elif week in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", week)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif week not in acceptable_weeks:
        db.log_activity(user.id, "error - chose wrong week for automn time" , week)
        await update.message.reply_text("لطفا دوباره تلاش کنید. هفته انتخاب شده اشتباه بود", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    db.log_activity(user.id, "chose week for automn time" , week)
    user_data["automn-week"] = week
    month = user_data["automn-month"]
    farm = user_data["set-automn-time-of-farm"]
    logger.info(f"farm: {farm}")
    db.set_user_attribute(user.id, f"farms.{farm}.automn-time", f"{week} - {month}")
    reply_text = "زمان خزان باغ شما ثبت شد. اکنون میتوانید از گزینه <b>نیاز سرمایی</b> موجود در منو اطلاعات باغ خود را مشاهده کنید."
    await update.message.reply_text(reply_text, reply_markup=db.find_start_keyboard(user.id), parse_mode=ParseMode.HTML,)
    return ConversationHandler.END
    farm_dict = db.get_farms(user.id)[farm]
    product = farm_dict.get("product")
    reply_text = f"""
رقم ثبت شده برای باغ پسته شما <b>{product}</b> است. 
در صورت صحیح بودن <b>/finish</b> را بزنید. در غیر این صورت رقم‌های پسته خود را انتخاب کنید.
همچنین می‌توانید رقم پسته را در صورتی که در لیست موجود نبود بنویسید.
    """
    await update.message.reply_text(reply_text, reply_markup=get_product_keyboard(), parse_mode=ParseMode.HTML)
    return CONFIRM_PRODUCT

async def confirm_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    farm = user_data["set-automn-time-of-farm"]
    farm_dict = db.get_farms(user.id)[farm]
    product = farm_dict.get("product")
    new_product = update.message.text
    if new_product == 'بازگشت':
        db.log_activity(user.id, "back")
        reply_text = "هفته خزان باغ خود را انتخاب کنید."
        await update.message.reply_text(reply_text, reply_markup=automn_week())
        return SET_AUTOMN_TIME
    elif new_product == '/finish':
        db.log_activity(user.id, "finished adding products for farm during set-automn-time")
        reply_text = "از ثبت زمان خزان باغ متشکریم، نیاز سرمایی مخصوص رقم باغ شما محاسبه شده و از همین جا قابل مشاهده خواهد بود."
        await update.message.reply_text(reply_text, reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    else:
        db.log_activity(user.id, "added product for farm during set-automn-time", new_product)
        db.set_user_attribute(user.id, f"farms.{farm}.product", f"{product} - {new_product}")
        farm_dict = db.get_farms(user.id)[farm]
        product = farm_dict.get("product")
        reply_text = f"""
    رقم ثبت شده برای باغ پسته شما <b>{product}</b> است. 
    در صورت صحیح بودن <b>/finish</b> را بزنید. در غیر این صورت رقم‌های پسته خود را انتخاب کنید.
    همچنین می‌توانید رقم پسته را در صورتی که در لیست موجود نبود بنویسید.
        """
        await update.message.reply_text(reply_text, reply_markup=get_product_keyboard(), parse_mode=ParseMode.HTML)
        return CONFIRM_PRODUCT
    
    
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات کنسل شد!")
    return ConversationHandler.END   


automn_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^❄️ نیاز سرمایی$'), automn_time)],
        states={
            AUTOMN_MONTH: [MessageHandler(filters.TEXT , ask_automn_month)],
            AUTOMN_WEEK: [MessageHandler(filters.TEXT , ask_automn_week)],
            SET_AUTOMN_TIME: [MessageHandler(filters.TEXT , set_automn_time)],
            # CONFIRM_PRODUCT: [MessageHandler(filters.TEXT | filters.COMMAND , confirm_product)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
