import pymongo
from datetime import datetime, timedelta
import jdatetime
import pickle
import pandas as pd
import os
from telegram import ReplyKeyboardMarkup
from typing import Callable, Type

REQUIRED_FIELDS = [
    "_id",
    "username",
    "name",
    "phone-number",
]


class Database:
    def __init__(self) -> None:
        self.client = pymongo.MongoClient(os.environ["MONGODB_URI"])
        self.db = self.client["agriweathBot"]  # database name
        self.user_collection = self.db["newUserCollection"]
        self.bot_collection = self.db["botCollection"]
        self.token_collection = self.db["tokenCollection"]
        self.dialog_collection = self.db["dialogCollection"]
        self.sms_collection = self.db["smsCollection"]
        self.weather_collection = self.db["weatherCollection"]

    def check_if_user_exists(self, user_id: int, raise_exception: bool = False):
        if self.user_collection.count_documents({"_id": user_id}) > 0:
            return True
        else:
            if raise_exception:
                raise ValueError(f"User {user_id} does not exist")
            else:
                return False

    def check_if_user_is_registered(self, user_id: int, required_keys: list = REQUIRED_FIELDS):
        if not self.check_if_user_exists(user_id=user_id):
            return False
        else:
            document = self.user_collection.find_one( {"_id": user_id} )
            if all(key in document for key in required_keys):
                return True
            else:
                return False
    
    def check_if_user_has_farms(self, user_id: int, user_document: dict = None) -> bool:
        if not user_document:
            user_document = self.user_collection.find_one( {"_id": user_id} )
        if user_document.get("farms"):
            return True
        else: 
            return False
        
    def check_if_user_has_farms_with_location(self, user_id: int, user_document: dict = None) -> bool:
        if not user_document:
            user_document = self.user_collection.find_one( {"_id": user_id} )
        # Lets assume that the user has atleast one farm i.e. we've filtered the users who don't have a farm
        longitudes = { farm: user_document.get("farms", {}).get(farm, {}).get("location", {}).get("longitude") for farm in list(user_document.get("farms", {}).keys()) }
        if any([longitudes[farm] for farm in list(longitudes.keys())]):
            return True
        else:
            return False
        
    def check_if_user_has_pesteh(self, user_id: int, user_document: dict = None) -> bool:
        if not user_document:
            user_document = self.user_collection.find_one( {"_id": user_id} )
        products = [user_document["farms"][farm].get("product", "") for farm in list(user_document["farms"].keys())]
        products = [product for product in products if product]
        if any([product.startswith("پسته") for product in products]):
            return True
        else:
            return False

    def find_start_keyboard(self, user_id: int, user_document: dict = None) -> Callable[[], Type[ReplyKeyboardMarkup]]:
        from utils import keyboards
        if not user_document:
            user_document = self.user_collection.find_one( {"_id": user_id} )
        if not self.check_if_user_is_registered(user_id):
            return keyboards.start_keyboard_not_registered()
        else:
            if not self.check_if_user_has_farms(user_id, user_document):
                return keyboards.start_keyboard_no_farms()
            else:
                if not self.check_if_user_has_farms_with_location(user_id, user_document):
                    return keyboards.start_keyboard_no_location()
                else:
                    if not self.check_if_user_has_pesteh(user_id, user_document):
                        return keyboards.start_keyboard_not_pesteh()
                    else:
                        return keyboards.start_keyboard_pesteh_kar()

    def get_all_pesteh_farmers(self) -> list:
        pipeline = [
            {
                '$project': {
                    'farms': {
                        '$objectToArray': '$farms'
                    }
                }
            }, {
                '$unwind': '$farms'
            }, {
                '$match': {
                    'farms.v.product': {
                        '$regex': '^پسته'
                    }
                }
            }, {
                '$group': {
                    '_id': '$_id'
                }
            }
        ]
        cursor = self.user_collection.aggregate(pipeline) # users who have atleast one pesteh farm 
        users = [user["_id"] for user in cursor]
        return users

    def register_not_pressed(self) -> list[int]:
        """_summary_
        Helper function that returns all users that started the bot but never pressed the register button
        Returns:
            list[int]: List of Telegram IDs
        """
        pipeline = [
            {
                '$match': {
                    'user_activity': {
                        '$exists': True
                    }
                }
            }, {
                '$group': {
                    '_id': '$userID',
                    'activity': {
                        '$push': '$user_activity'
                    }
                }
            }, {
                '$match': {
                    'activity': {
                        '$elemMatch': {
                            '$eq': 'start register'
                        }
                    }
                }
            },
        ]
        cursor = self.bot_collection.aggregate(pipeline)
        pressed_register = [user["_id"] for user in cursor]
        all_users = self.user_collection.distinct("_id")
        not_pressed_register = [user for user in all_users if user not in pressed_register]
        return not_pressed_register
        
    def check_if_dialog_exists(self, user_id: int, raise_exception: bool = False):
        if self.dialog_collection.count_documents({"_id": user_id}) > 0:
            return True
        else:
            if raise_exception:
                raise ValueError(f"User {user_id} does not exist")
            else:
                return False

    def check_if_user_activity_exsits(self, 
                                      user_id: int, 
                                      activity: str, 
                                      gte: str, 
                                      lte: str = datetime.now().strftime("%Y%m%d %H:%M"))->bool:
        """checks user activities in the botCollection and returns True if a particular activity exists.

        Args:
            user_id (int): UserID of a Telegram.User
            activity (str): Name of the activity
            gt (str): Time to start the search (in `%Y%m%d %H:%M` format)
            lt (str): Time to stop the search (in `%Y%m%d %H:%M` format)
        """
        document = self.bot_collection.find_one( {
            "userID": user_id,
            "user_activity": activity,
            "timestamp": {"$gte": gte, "$lte": lte} 
        } )
        from utils.logger import logger
        logger.info(f"document: {document}\nuser: {user_id}, gte: {gte}, lt: {lte}, activity: {activity}")
        if document:
            return True
        else:
            return False

    def log_sms_message(self, user_id: int, msg: str, msg_code: int):
        msg_document = {
            "userID": user_id,
            "msg": msg,
            "msg-code": msg_code,
            "timestamp": datetime.now().strftime("%Y%m%d %H:%M")
        }
        self.sms_collection.insert_one(msg_document)
    
    def add_new_user(
        self,
        user_id,
        username: str = "",
        first_seen: str = datetime.now().strftime("%Y-%m-%d %H:%M")
    ):
        user_dict = {
            "_id": user_id,
            "username": username,
            "first-seen": first_seen,
            # "phone-number": "",
            # "name": "",
            "blocked": False
        }

        if not self.check_if_user_exists(user_id=user_id):
            self.user_collection.insert_one(user_dict)

    def get_admins(self) -> list:
        """Return a list of admin IDs"""
        admins = self.bot_collection.find_one({"name":"admin-list"})["admins"]
        admins = [int(admin) for admin in admins]
        return admins

    def add_new_farm(self, user_id, farm_name: str, new_farm: dict):
        self.user_collection.update_one(
            {"_id": user_id},
            {"$set": {f"farms.{farm_name}": new_farm}}
        )

    def load_weather_data(self, 
                          user_id: int, 
                          farm_name: str, 
                          timestamp: datetime,
                          max_temp: list[float], 
                          min_temp: list[float], 
                          rain_sum: list[float], 
                          snow_sum: list[float],
                          precipitation_probability: list[float], 
                          wind_speed: list[float], 
                          wind_direction: list[float],
                          relative_humidity: list[float]) -> None:
        
        jdate = jdatetime.datetime.fromgregorian(datetime=timestamp)
        labels = [(jdate + jdatetime.timedelta(days=i)).strftime("%Y/%m/%d") for i in range(7)]
        document = {
            "userID": user_id,
            "farm_name": farm_name,
            "timestamp": timestamp,
            "labels": labels,
            "weather": {
                "max_temp": max_temp,
                "min_temp": min_temp,
                "rain_sum": rain_sum,
                "snow_sum": snow_sum,
                "precipitation_probability": precipitation_probability,
                "wind_speed": wind_speed,
                "wind_direction": wind_direction,
                "relative_humidity": relative_humidity
            }    
        }
        
        self.weather_collection.insert_one(document)
        
    def query_weather_prediction(self, user_id: int, farm_name: str) -> tuple | None:
        def degrees_to_direction(degrees):
            directions = ['↑', '↗', '→', '↘', '↓', '↙', '←', '↖']
            index = round(degrees / 45) % 8
            return directions[index]
        document = self.weather_collection.find({"userID": user_id, "farm_name": farm_name}).sort("timestamp", -1).limit(1)
        document = next(document, None)
        
        if document is None:
            return None
        
        labels: list = document.get("labels")
        tmax_values: list = document.get("weather", {}).get("max_temp")
        tmin_values: list = document.get("weather", {}).get("min_temp")
        rain_sum: list = document.get("weather", {}).get("rain_sum")
        snow_sum: list = document.get("weather", {}).get("snow_sum")
        precipitation_probability: list = document.get("weather", {}).get("precipitation_probability")
        wind_speed: list = document.get("weather", {}).get("wind_speed")
        wind_direction: list = document.get("weather", {}).get("wind_direction")
        relative_humidity: list = document.get("weather", {}).get("relative_humidity")
        
        # change wind direction from degrees to arrows
        if wind_direction is not None:
            wind_direction = [degrees_to_direction(degrees) for degrees in wind_direction]
        
        # if any of the parameters are missing we need to make a new api call
        if any(x is None for x in (labels, tmax_values, tmin_values, rain_sum, snow_sum, precipitation_probability, wind_speed, wind_direction, relative_humidity)):
            return None
        
        # Make sure that the weather document was added today.
        now = datetime.utcnow()
        if document.get("timestamp").date() == now.date():
            return labels, tmax_values, tmin_values, rain_sum, snow_sum, precipitation_probability, wind_speed, wind_direction, relative_humidity
        else:
            return None
    
    def add_token(self, user_id: int, value: str):
        token_dict = {
            "owner": user_id,
            "token-value": value,
            "time-created": datetime.now().strftime("%Y%m%d %H:%M"),
            "used-by": [],
        }
        self.token_collection.insert_one(token_dict)

    def log_token_use(self, user_id: int, value: str) -> int:
        token_document = self.token_collection.find_one({ "token-value": value })
        if token_document:
            owner = token_document.get("owner")
            self.token_collection.update_one({"token-value": value}, {"$push": {"used-by": user_id}})
            self.user_collection.update_one({"_id": user_id}, {"$set": {"invited-by": owner}})

    def calc_token_number(self, value: str):
        token_document = self.token_collection.find_one({ "token-value": value })
        return len(token_document['used-by'])

    def calc_user_tokens(self, user_id: int) -> int:
        user_tokens = self.token_collection.find( {"owner": user_id} )
        num = 0
        if user_tokens:            
            for token in user_tokens:
                num += len(token["used-by"])
        return num


    def get_user_attribute(self, user_id: int, key: str):
        self.check_if_user_exists(user_id=user_id, raise_exception=True)
        user_dict = self.user_collection.find_one({"_id": user_id})

        if key not in user_dict:
            return None
        return user_dict[key]
    
    def set_user_attribute(self, user_id: int, key: str, value: any, array: bool = False):
        self.check_if_user_exists(user_id=user_id, raise_exception=True)
        if not array:
            self.user_collection.update_one({"_id": user_id}, {"$set": {key: value}})
        else:
            self.user_collection.update_one({"_id": user_id}, {"$push": {key: value}})
    # def log_message_to_user(self, user_id: int, message: str):
    #     self.check_if_user_exists(user_id=user_id, raise_exception=True)
    def save_coupon(self, text, value):
        if not self.bot_collection.find_one( {"_id": "coupons"} ):
            self.bot_collection.insert_one({"_id": "coupons", 'values': [{text: float(value)}]})
            return True
        else:
            coupons_doc = self.bot_collection.find_one( {"_id": "coupons"} )
            coupons = [list(coupon.keys())[0] for coupon in coupons_doc["values"]]
            if text in coupons:
                return False
            else:
                self.bot_collection.update_one({"_id": "coupons"}, {"$push": {'values': {text: float(value)} }})
                return True

    def verify_coupon(self, coupon: str):
        coupons_doc = self.bot_collection.find_one( {"_id": "coupons"} )
        if not coupons_doc:
            return False
        coupons = [list(coupon.keys())[0] for coupon in coupons_doc["values"]]
        if coupon in coupons:
            return True
        else: return False
    
    def apply_coupon(self, coupon: str, original: float) -> float:
        coupons_doc = self.bot_collection.find_one( {"_id": "coupons"} )
        coupons = coupons_doc["values"]
        for item in coupons:
            coupon_value = item.get(coupon)
            if coupon_value:
                new_value = original - coupon_value
                return new_value
        return original

    def log_payment( self,
                     user_id: int,
                     used_coupon: str = None,
                     reason: str = 'subscription',
                     amount: float = 500000.0,
                     verified: bool = False,
                     code: str = ""):
        current_time = datetime.now().strftime("%Y%m%d %H:%M")
        payment_dict = {
            'code': code,
            'time-approved': current_time,
            'reason': reason,
            'amount': amount,
            'coupon': used_coupon,
            'verified': verified
        }
        self.set_user_attribute(user_id, 'payments', payment_dict, True)

    def add_coupon_to_payment_dict(self, user_id: int, code: str, coupon: str) -> None:
        filter_query = {'_id': user_id,
                        'payments': {'$elemMatch': {'code': code} } }
        update_query = {'$set': { 'payments.$.coupon': coupon } }
        self.user_collection.update_one(filter_query, update_query)

    def modify_final_price_in_payment_dict(self, user_id: int, code: str, final_price: float) -> None:
        filter_query = {'_id': user_id,
                        'payments': {'$elemMatch': {'code': code} } }
        update_query = {'$set': { 'payments.$.amount': final_price } }
        self.user_collection.update_one(filter_query, update_query)

    def get_final_price(self, user_id: int, code: str):
        document = self.user_collection.find_one( {'_id': user_id,
                                        'payments': {'$elemMatch': {'code': code} }} )
        payment = next((payment for payment in document['payments'] if payment['code'] == code), None)
        return payment['amount']

    def verify_payment(self, user_id: int, code: str):
        filter_query = {'_id': user_id,
                        'payments': {'$elemMatch': {'code': code} } }
        update_query = {'$set': { 'payments.$.verified': True } }
        self.user_collection.update_one(filter_query, update_query)
        self.set_user_attribute(user_id, 'has-verified-payments', True)
        
    def process_coupon_use(self):
        pass

    def log_new_message(
        self,
        user_id,
        username: str = "",
        message: str = "",
        function: str = "",
    ):
        current_time = datetime.now().strftime("%Y%m%d %H:%M")
        dialog_dict = {
            "_id": user_id,
            "username": username,
            "message": [f"{current_time} - {function} - {message}"],
            "function": [function]
        }

        if not self.check_if_dialog_exists(user_id=user_id):
            self.dialog_collection.insert_one(dialog_dict)
        else:
            self.dialog_collection.update_one(
                {"_id": user_id}, {
                    "$push": {"message": f"{current_time} - {function} - {message}", "function": function}})
    

    def log_sent_messages(self, users: list, function: str = "") -> None:
        current_time = datetime.now().strftime("%Y%m%d %H:%M")
        usernames = [self.user_collection.find_one({"_id": user})["username"] for user in users]
        users = [str(user) for user in users]
        log_dict = {
            "time-sent": current_time,
            "type": "sent messages",
            "function-used": function,
            "number-of-receivers": len(users),
            "receivers": dict(zip(users, usernames))
        }
        self.bot_collection.insert_one(log_dict)

    def log_member_changes(
        self,
        members: int = 0,
        time: str = "",
    ):
        bot_members_dict = {
            "num-members": [members],
            "time-stamp": [time]
        }

        if self.bot_collection.count_documents({}) == 0:
            self.bot_collection.insert_one(bot_members_dict)
        else:
            self.bot_collection.update_one({}, {"$push": {"num-members": members, "time-stamp": time}})

    def log_activity(self, user_id: int, user_activity: str, provided_value: str = ""):
        activity = {
            "user_activity": user_activity,
            "type": "activity logs",
            "value": provided_value,
            "userID": user_id,
            "username": self.user_collection.find_one({"_id": user_id})["username"],
            "timestamp": datetime.now().strftime("%Y%m%d %H:%M")
        }
        self.bot_collection.insert_one(activity)

    def get_farms(self, user_id):
        if not self.check_if_user_is_registered(user_id=user_id):
            return []
        user = self.user_collection.find_one( {"_id": user_id} )
        # provinces = user.get("provinces")
        # cities = user.get("cities")
        # villages = user.get("villages")
        # areas = user.get("areas")
        # locations = user.get("locations")
        # equality = len(provinces) == len(cities) == len(villages) == len(areas) == len(locations)
        farms = user.get("farms")
        return farms
    
    def get_users_with_location(self):
        pipeline = [
                {"$match": {"$and": [
                        { "farms": { "$exists": True } },
                        { "farms": { "$ne": None } },
                        { "farms": { "$ne": {} } }
                        ]
                    }
                },
                {"$addFields": {
                    "farmsArray": { "$objectToArray": "$farms" }
                    }
                },
                {"$redact": {
                    "$cond": {
                        "if": {
                        "$anyElementTrue": {
                            "$map": {
                            "input": "$farmsArray",
                            "as": "farm",
                            "in": {
                                "$and": [
                                { "$ne": ["$$farm.v.location.latitude", None] },
                                { "$ne": ["$$farm.v.location.longitude", None] }
                                ]
                            }
                            }
                        }
                        },
                        "then": "$$KEEP",
                        "else": "$$PRUNE"
                    }
                    }
                },
                {"$project": {
                    "_id": 1
                    }
                }
                ]

        cursor = self.user_collection.aggregate(pipeline) # users who have atleast one farm with no location
        users = [user["_id"] for user in cursor]
        return users

    def get_users_without_location(self):
        pipeline = [
            { "$addFields": { "farmsArray": { "$objectToArray": "$farms" } } },
            { "$match": { "farmsArray.v.location.latitude": None, "farmsArray.v.location.longitude": None } },
            { "$project": { "_id": 1 } }
        ]
        cursor = self.user_collection.aggregate(pipeline) # users who have atleast one farm with no location
        users = [user["_id"] for user in cursor]
        return users

    def get_farms_with_location(self) -> list[dict[str, any]]:
        """
        Returns list[dict[str, any]]: a list of dictionaries with 3 keys:\n
                _id -> telegram user id,\n
                farm -> farm name,\n
                location -> {latitude: `lat`, longitude: `long`}.
        """
        pipeline = [ 
                    { '$match': 
                        { '$and': [{ 'farms': { '$exists': True } }, 
                                   { 'farms': { '$ne': None } },
                                   { 'farms': { '$ne': {} } } 
                                ] 
                        }
                    }, 
                    { '$addFields': 
                        {'farmsArray': 
                           { '$objectToArray': '$farms' } 
                        }
                    }, 
                    { '$unwind': '$farmsArray' }, 
                    { '$match': 
                        {'farmsArray.v.location.latitude': { '$ne': None },
                         'farmsArray.v.location.longitude': { '$ne': None } 
                        }
                    }, 
                    { '$project': 
                        { 
                         '_id': 1,
                         'farm': '$farmsArray.k',
                         'location': '$farmsArray.v.location' 
                        } 
                    } 
        ]
        cursor = self.user_collection.aggregate(pipeline) # 
        return list(cursor)
        
    def get_users_without_phone(self):
        pipeline = [
            { "$match": {"$or": [ {"phone-number": None}, {"phone-number": ""} ] } },
            { "$project": { "_id": 1 } }
        ]
        cursor = self.user_collection.aggregate(pipeline) # users with no phone number
        users = [user["_id"] for user in cursor]
        return users

    def number_of_members(self) -> int:
        members = self.user_collection.distinct("_id")
        return len(members)
    
    def number_of_blocks(self) -> int:
        blocked_users = self.user_collection.count_documents({"blocked": True})
        return blocked_users
    