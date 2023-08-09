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
        InlineKeyboardButton("دانلود فایل اکسل", callback_data='excel_download'),
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
    
def farms_list_reply(database: db, user_id):
    farms = database.get_farms(user_id=user_id)
    if not farms:
        return None
    keys_list = list(farms.keys())
    keyboard = [ [key] for key in keys_list ]
    keyboard.append(["↩️ بازگشت"])
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        
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
        "بازگشت به لیست باغ ها",
    ]
    ]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)



def return_keyboard():
    keyboard = ["back"]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
# Function to get the multi-choice keyboard for provinces
def get_province_keyboard():
    keyboard = [['کرمان', 'خراسان رضوی', 'خراسان جنوبی'], ['یزد', 'فارس', 'سمنان'], ['مرکزی', 'تهران', 'اصفهان'], ['قم', 'سیستان و بلوچستان', 'قزوین'], ['سایر', 'بازگشت']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)


# Function to get the multi-choice keyboard for produce
def start_keyboard():
    keyboard = [['✍️ ثبت نام'], ['دعوت از دیگران'], ['🖼 مشاهده باغ ها', '➕ اضافه کردن باغ'],  ['🗑 حذف باغ ها', '✏️ ویرایش باغ ها'], ['🌦 درخواست اطلاعات هواشناسی']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

def get_product_keyboard():
    keyboard = [['پسته اکبری', 'پسته اوحدی', 'پسته احمدآقایی'], ['پسته بادامی', 'پسته فندقی', 'پسته کله قوچی'], ['پسته ممتاز', 'سایر', 'بازگشت']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

def conf_del_keyboard():
    keyboard = [['بله'], ['خیر'], ['بازگشت']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

def choose_role():
    keyboard = [['تمام کاربران'], ['تعیین id'], ['لوکیشن دار'], ['بدون لوکیشن'], ['بدون شماره تلفن'], ['بازگشت']]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True ,one_time_keyboard=True)

def back_button():
    keyboard = [['بازگشت']]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True ,one_time_keyboard=True)