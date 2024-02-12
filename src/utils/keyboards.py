from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
import database

db = database.Database

def stats_keyboard():
    keyboard = [
    [
        InlineKeyboardButton("تعداد اعضا", callback_data='member_count'),
        InlineKeyboardButton("تغییرات تعداد اعضا", callback_data='member_count_change')
    ],
    [
        InlineKeyboardButton("تعداد بلاک‌ها", callback_data='block_count'),
        InlineKeyboardButton("تعداد اعضای بدون لوکیشن", callback_data='no_location_count'),
        
    ],
    [
        # InlineKeyboardButton("دانلود فایل اکسل", callback_data='excel_download'),
        InlineKeyboardButton("تعداد اعضای بدون تلفن", callback_data='no_phone_count'),
    ],
    # [
    #     InlineKeyboardButton("پراکندگی لوکیشن اعضا", callback_data='html_map'),
    # ],
]
    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup

def farms_list_inline(database: db, user_id, view: bool = True, edit: bool = False):
    farms = database.get_farms(user_id=user_id)
    if not farms:
        return None
    keys_list = list(farms.keys())
    if view & edit:
        raise ValueError("edit and error can't be True at the same time")
    elif view:
        keyboard = [ [InlineKeyboardButton(key, callback_data=f"{key}")] for key in keys_list ]
        return InlineKeyboardMarkup(keyboard)
    elif edit:
        keyboard = [ [InlineKeyboardButton(key, callback_data=f"{key}")] for key in keys_list ]
        return InlineKeyboardMarkup(keyboard)
    
def farms_list_reply(database: db, user_id, pesteh_kar: bool = None):
    farms = database.get_farms(user_id=user_id)
    if not farms:
        return None
    keys_list = list(farms.keys())
    if pesteh_kar:
        keyboard = [ [key] for key in keys_list if farms[key].get("product", "").startswith("پسته")]
    else:
        keyboard = [ [key] for key in keys_list ]
    keyboard.append(["↩️ بازگشت"])
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
def edit_keyboard_inline():
    keyboard = [
    [
        InlineKeyboardButton("تغییر محصول", callback_data='product'),
        InlineKeyboardButton("تغییر استان", callback_data='province')
    ],
    [
        InlineKeyboardButton("تغییر شهرستان", callback_data='city'),
        InlineKeyboardButton("تغییر روستا", callback_data='village')
    ],
    [
        InlineKeyboardButton("تغییر سطح", callback_data='area'),
        InlineKeyboardButton("تغییر موقعیت", callback_data='location'),
    ],
    [
        InlineKeyboardButton("بازگشت به لیست باغ ها", callback_data='back'),
    ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup

def edit_keyboard_reply():
    keyboard = [
    [
        "تغییر محصول",
        "تغییر استان",
    ],
    [
        "تغییر شهرستان",
        "تغییر روستا",
    ],
    [
        "تغییر مساحت",
        "تغییر موقعیت",
    ],
    [
        "بازگشت به لیست کشت‌ها",
    ]
    ]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

def land_type_keyboard():
    keyboard = [["باغ", "مزرعه"], ["صیفی", "گلخانه"], ['بازگشت']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)


def return_keyboard():
    keyboard = ["back"]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
# Function to get the multi-choice keyboard for provinces
def get_province_keyboard():
    keyboard = [['کرمان', 'خراسان رضوی', 'خراسان جنوبی'], ['یزد', 'فارس', 'سمنان'], ['مرکزی', 'تهران', 'اصفهان'], ['قم', 'سیستان و بلوچستان', 'قزوین'], ['بازگشت']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

# 🌳🧾💶💰✅

# Function to get the multi-choice keyboard for produce
# def start_keyboard():
#     keyboard = [['📤 دعوت از دیگران'], ,  ['🗑 حذف باغ ها', '✏️ ویرایش باغ ها'], ['🌦 درخواست اطلاعات هواشناسی']]
#     return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)


def start_keyboard_not_registered():
    keyboard = [ ["✍️ ثبت نام"] ]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)


def start_keyboard_no_farms():
    keyboard = [ ["➕ اضافه کردن کشت"] ]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

def start_keyboard_no_location():
    keyboard = [ ["✏️ ویرایش کشت‌ها"] ]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

def start_keyboard_not_pesteh():
    keyboard = [ ['👨‍🌾 مدیریت کشت‌ها'],  ['🌟 سرویس VIP'], ['⚠️ هشدار سرمازدگی زمستانه'], ['🌦 پیش‌بینی هواشناسی', '🧪 شرایط محلول‌پاشی'],  ['📤 دعوت از دیگران', '📬 ارتباط با ما']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

def start_keyboard_pesteh_kar():
    keyboard = [ ['🌦 پیش‌بینی هواشناسی'], ['⚠️ هشدار سرمازدگی زمستانه', '🌡 نیاز حرارتی پروانه چوبخوار'], ['🧪 شرایط محلول‌پاشی', '❄️ نیاز سرمایی'], ['🏘 بازگشت به خانه'] ]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

def home_keyboard_pesteh_kar():
    keyboard = [ ['👨‍🌾 مدیریت کشت‌ها'],  ['🌟 سرویس VIP'] , ['📤 دعوت از دیگران', '📬 ارتباط با ما'], ['منوی هواشناسی']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)


def manage_farms_keyboard():
    keyboard = [['🖼 مشاهده کشت‌ها', '➕ اضافه کردن کشت'], ['🗑 حذف کشت', '✏️ ویرایش کشت‌ها'], ['🏘 بازگشت به خانه']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)

def payment_keyboard():
    keyboard = [['💶 خرید اشتراک'], ['🧾 ارسال فیش پرداخت'], ['🏘 بازگشت به خانه']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)

def request_info_keyboard():
    keyboard = [ ['🌦 درخواست اطلاعات هواشناسی'],  ['🧪 دریافت توصیه محلول‌پاشی'], ['🏘 بازگشت به خانه']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

def view_advise_keyboard(farm_name: str):
    keyboard = [
        [
        InlineKeyboardButton("توصیه پس‌فردا", callback_data=f'{farm_name}\nday3_advise'),
        InlineKeyboardButton("توصیه فردا", callback_data=f'{farm_name}\nday2_advise'),
        InlineKeyboardButton("توصیه امروز", callback_data=f'{farm_name}\ntoday_advise'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup

def view_sp_advise_keyboard(farm_name: str):
    keyboard = [
        [
        InlineKeyboardButton("توصیه پس‌فردا", callback_data=f'{farm_name}\nday3_sp_advise'),
        InlineKeyboardButton("توصیه فردا", callback_data=f'{farm_name}\nday2_sp_advise'),
        InlineKeyboardButton("توصیه امروز", callback_data=f'{farm_name}\ntoday_sp_advise'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup

def view_ch_advise_keyboard(farm_name: str):
    keyboard = [
        [
        InlineKeyboardButton("توصیه پسان‌فردا", callback_data=f'{farm_name}\nday3_ch_advise'),
        InlineKeyboardButton("توصیه پس‌فردا", callback_data=f'{farm_name}\nday2_ch_advise'),
        InlineKeyboardButton("توصیه فردا", callback_data=f'{farm_name}\nday1_ch_advise'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup

def weather_keyboard(farm_name: str):
    keyboard = [
        [
        InlineKeyboardButton("openMeteo", callback_data=f'open_meteo_prediction\n{farm_name}'),
        InlineKeyboardButton("مرکز هواشناسی", callback_data=f'oskooei_prediction\n{farm_name}'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup
    
def register_keyboard():
    keyboard = [['✍️ ثبت نام']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

def get_product_keyboard():
    keyboard = [['پسته اکبری', 'پسته اوحدی', 'پسته احمدآقایی'], ['پسته بادامی', 'پسته فندقی', 'پسته کله قوچی'], ['پسته ممتاز', 'بازگشت']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

def conf_del_keyboard():
    keyboard = [['بله'], ['خیر'], ['بازگشت']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

def automn_month():
    keyboard = [['آبان'], ['آذر'], ['↩️ بازگشت']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

def automn_week():
    keyboard = [['هفته دوم', 'هفته اول'], ['هفته چهارم', 'هفته سوم'], ['↩️ بازگشت']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)


def choose_role():
    keyboard = [['تعیین id'], ['تمام کاربران'], ['دکمه ثبت نام را نزدند'], ['پسته‌کاران'], ['لوکیشن دار'], ['بدون لوکیشن'], ['بدون شماره تلفن'], ['بازگشت']]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True ,one_time_keyboard=True)

def back_button():
    keyboard = [['بازگشت']]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True ,one_time_keyboard=True)