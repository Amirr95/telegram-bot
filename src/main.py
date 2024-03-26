import asyncio
import aiohttp
from asyncio.exceptions import TimeoutError
import os
import database
from pg_sync import query_frost_temp, query_frost_wind
from utils.message_generator import generate_messages
from utils.logger import logger


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
        async with session.post(url, data=payload, headers=headers, timeout=30) as response:
            json = await response.json()
            # logger.info(f"response: {response}\ndata: {data}\njson: {json}")
            return json
        
        
async def main():
    db = database.Database()
    farmers = db.get_all_pesteh_farmers()
    for farmer in farmers:
        user_document = db.user_collection.find_one({"_id": farmer})
        phone_number = user_document.get("phone-number")
        if not phone_number:
            logger.info(f"Phone number was not found for {farmer}")
            continue
        farms = user_document.get("farms")
        for farm in farms:
            longitude = farms[farm].get("location", {}).get("longitude")
            latitude = farms[farm].get("location", {}).get("latitude")
            if longitude and latitude:
                frost_temp = query_frost_temp(latitude, longitude).get("frost-temp")
                frost_wind = query_frost_wind(latitude, longitude).get("frost-wind")
                if frost_temp and frost_wind:
                    messages = generate_messages(frost_temp, frost_wind)
                    if messages:
                        sms_msg = f"احتمال سرمازدگی در باغ شما با نام {farm}\n" + "اطلاعات بیشتر با مراجعه به آباد:\nt.me/agriweathbot\n\n\n" + "\n".join(messages) + "\nراهنمایی 22\nلغو 11"
                        logger.info(f"Sending SMS to {phone_number}")
                        try:
                            res = await send_sms_method(text=sms_msg, receiver=phone_number)
                            logger.info(f"Code: {res[0]}")
                            logger.info(f"SMS sent to {farmer} - {phone_number}")
                        except TimeoutError:
                            logger.error(f"TimeoutError while sending sms to {phone_number} (for {farmer})")
                else:
                    logger.warning(f"Query returned an empty dictionary, user: {farmer} farm: {farm}")
                    
if __name__=="__main__":
    asyncio.run(main())
    
    # Sample data:
    # data = {
    #             "msg": msg,
    #             "msg_code": 1, # Just a code to represent the message in google sheet
    #             "receiver": phone_num,
    #             "msg_id": res[0], # The ID returned by the sendsms method
    #             "origin": "no_farm_sms",
    #             "job_counter": job_counter
    #         }