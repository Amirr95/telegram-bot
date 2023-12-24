from telegram import Update
from telegram.ext import ContextTypes, ApplicationHandlerStop
from telegram.error import Forbidden, BadRequest

import aiohttp
import os
import datetime
from asyncio.exceptions import TimeoutError

from database import Database
from utils.logger import logger

db = Database()


add_farm_before_location = """
کاربر عزیز، ثبت زمین شما در ربات هواشناسی آباد تکمیل نشده است. جهت دریافت خدمات لطفا مراحل ثبت زمین را تا انتها انجام دهید.
ربات آباد: t.me/agriweathbot
تماس با ما: 02164063410
نیاز به راهنمایی 22
لغو 11
"""

add_farm_after_location = """
کاربر عزیز، برای دریافت خدمات هواشناسی آباد نیاز به ثبت موقعیت زمین شما است. لطفا موقعیت زمین خود را در ربات ثبت کنید.
ربات آباد: t.me/agriweathbot
تماس با ما: 02164063410
نیاز به راهنمایی 22
لغو 11
"""

async def send_sms_method(text: str, receiver: str)->list[int]:
    asanak_username = os.environ["ASANAK_USERNAME"]
    asanak_password = os.environ["ASANAK_PASSWORD"]
    asanak_phone_num = os.environ["ASANAK_PHONE_NUM"]
    url = "https://panel.asanak.com/webservice/v1rest/sendsms"
    headers = {"Accept": "application/json"}
    payload = {
        'username': asanak_username,
        'password': asanak_password,
        'Source': asanak_phone_num,
        'Message': text,
        'destination': receiver
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=payload, headers=headers, timeout=5) as response:
            json = await response.json()
            # logger.info(f"response: {response}\ndata: {data}\njson: {json}")
            return json

async def msg_status_method(msg_id: str):
    asanak_username = os.environ["ASANAK_USERNAME"]
    asanak_password = os.environ["ASANAK_PASSWORD"]
    url = "https://panel.asanak.com/webservice/v1rest/msgstatus"
    headers = {"Accept": "application/json"}
    payload = {
        'username': asanak_username,
        'password': asanak_password,
        'msgid': msg_id,
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=payload, headers=headers, timeout=5) as response:
            json = await response.json()
            return json[0]
        
async def check_status(context: ContextTypes.DEFAULT_TYPE):
    user_id = context.job.chat_id
    data: dict = context.job.data
    msg: str = data.get("msg", "")
    receiver = data.get("receiver")
    msg_id = data.get("msg_id")
    msg_code = data.get("msg_code")
    origin: str = data.get("origin", "")
    job_counter: int = data.get("job_counter")
    if not job_counter:
        raise ValueError(f"job_counter is not defined:\n{data}")
    
    
    status = await msg_status_method(msg_id=msg_id)
    status_code = int(status.get("Status"))
    known_status = [-1, 1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
    if status_code != 6:
        if status_code in known_status:
            if origin == "no_farm_sms":
                if job_counter < 3:
                    data["job_counter"] += 1
                    context.job_queue.run_once(sms_no_farm, when=datetime.timedelta(seconds=60), chat_id=user_id)
            elif origin.startswith("farm_incomplete"):
                if job_counter < 3:
                    data["job_counter"] += 1
                    context.job_queue.run_once(sms_incomplete_farm, when=datetime.timedelta(seconds=60), chat_id=user_id,
                                           data= data)
        else:
            text = f"API call to sendsms returned a status code of {status}\njob data: {data}"
            await context.bot.send_message(chat_id=103465015, text=text)
            raise ValueError("Unknown sms status code")
    else:
        db.log_sms_message(user_id=user_id, msg=msg, msg_code=msg_code)
            
        
async def sms_no_farm(context: ContextTypes.DEFAULT_TYPE):
    user_id = context.job.chat_id
    data = context.job.data
    job_counter: int = data.get("job_counter", 1)
    user_doc = db.user_collection.find_one({"_id": user_id})
    name = user_doc.get("name", "کاربر")
    phone_num = user_doc.get("phone-number")
    msg = f"""
{name} عزیز، برای دریافت اطلاعات هواشناسی آباد، لطفا زمین خود را ثبت کنید.
ربات آباد: @agriweathbot
تماس با ما: 02164063410
نیاز به راهنمایی 22
لغو 11
"""
    if db.check_if_user_is_registered(user_id) and not db.get_farms(user_id):
        if phone_num:
            try:
                res = await send_sms_method(text=msg, receiver=phone_num)
            except TimeoutError:
                await context.bot.send_message(chat_id=103465015, text=f"TimeoutError while sending sms to {phone_num}")
            data = {
                "msg": msg,
                "msg_code": 1, # Just a code to represent the message in google sheet
                "receiver": phone_num,
                "msg_id": res[0], # The ID returned by the sendsms method
                "origin": "no_farm_sms",
                "job_counter": job_counter
            }
            logger.info(res)
            context.job_queue.run_once(check_status, when=datetime.timedelta(minutes=5), chat_id=user_id, data=data)
    
    
async def sms_incomplete_farm(context: ContextTypes.DEFAULT_TYPE):
    """
    Triggered as a user presses the `add_farm` button.
    Must provide the time when `add_farm` was pressed to query the database according to that. 
    """
    user_id = context.job.chat_id
    data = context.job.data
    timestamp_add_farm = data.get("timestamp")
    job_counter: int = data.get("job_counter", 1)
    user_doc = db.user_collection.find_one({"_id": user_id})
    name = user_doc.get("name", "کاربر")
    phone_num = user_doc.get("phone-number")
    msg_from_status_check = data.get("msg")
    msg_before_location = f"""
{name} عزیز، ثبت زمین شما در ربات هواشناسی آباد تکمیل نشده است. جهت دریافت خدمات لطفا مراحل ثبت زمین را تا انتها انجام دهید.
ربات آباد: @agriweathbot
تماس با ما: 02164063410
نیاز به راهنمایی 22
لغو 11
    """
    msg_location = f"""
{name} عزیز، برای دریافت خدمات هواشناسی آباد نیاز به ثبت موقعیت زمین شما است. لطفا موقعیت زمین خود را در ربات ثبت کنید.
ربات آباد: @agriweathbot
تماس با ما: 02164063410
نیاز به راهنمایی 22
لغو 11

    """
    if phone_num:
        if not db.check_if_user_has_farms_with_location(user_id=user_id, user_document=user_doc):
            if not db.check_if_user_activity_exsits(user_id=user_id, activity="entered area", gte=timestamp_add_farm):
                if not msg_from_status_check:
                    msg = msg_before_location
                    msg_code = 2
                else:
                    msg = msg_from_status_check
                    msg_code = 2
                try:
                    res = await send_sms_method(text=msg, receiver=phone_num)
                except TimeoutError:
                    await context.bot.send_message(chat_id=103465015, text=f"TimeoutError while sending sms to {phone_num}")
                try:
                    data = {
                        "msg": msg,
                        "msg_code": msg_code,
                        "receiver": phone_num,
                        "msg_id": res[0],
                        "origin": "farm_incomplete_before_location",
                        "timestamp": timestamp_add_farm,
                        "job_counter": job_counter
                    }
                    context.job_queue.run_once(check_status, when=datetime.timedelta(minutes=5), chat_id=user_id, data=data)
                except KeyError:
                    await context.bot.send_message(chat_id=103465015, text=f"res: {res}\ndata: {data}\nEncountered a KeyError.")
            else:
                if not msg_from_status_check:
                    msg = msg_location
                    msg_code = 3
                else:
                    msg = msg_from_status_check
                    msg_code = 3
                try:
                    res = await send_sms_method(text=msg, receiver=phone_num)
                except TimeoutError:
                    await context.bot.send_message(chat_id=103465015, text=f"TimeoutError while sending sms to {phone_num}")
                data = {
                    "msg": msg,
                    "msg_code": msg_code,
                    "receiver": phone_num,
                    "msg_id": res[0],
                    "origin": "farm_incomplete_after_location",
                    "timestamp": timestamp_add_farm,
                    "job_counter": job_counter
                }
                context.job_queue.run_once(check_status, when=datetime.timedelta(minutes=5), chat_id=user_id, data=data)

            
        