import pymongo
from datetime import datetime, timedelta
import jdatetime
import pickle
import os
from typing import Callable, Type

REQUIRED_FIELDS = [
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
        self.app_collection = self.db["webappUserCollection"]

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

    def log_sms_message(self, user_id: int, msg: str, msg_code: int):
        msg_document = {
            "userID": user_id,
            "msg": msg,
            "msg-code": msg_code,
            "timestamp": datetime.now().strftime("%Y%m%d %H:%M")
        }
        self.sms_collection.insert_one(msg_document)
    