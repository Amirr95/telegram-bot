import os
import pymongo
import gspread
import time
import logging
from logging.handlers import RotatingFileHandler
import warnings
from datetime import datetime

warnings.filterwarnings("ignore", category=UserWarning)
# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    encoding="utf-8",
    level=logging.INFO,
    handlers=[
        RotatingFileHandler(
            "sheet_logs.log", maxBytes=10000000, backupCount=5
        ),  # File handler to write logs to a file
        logging.StreamHandler(),  # Stream handler to display logs in the console
    ],
)
logger = logging.getLogger("sheet-export")

class Sheet():
    """
Class that represents the sheet connected to our database.
Need to figure out the order -- add new rows or update existing rows first?
Also self.sheet_values should get updated. would that cause any inconsistencies?
    """
    def __init__(self):
        self.auth = ".gspread/sheet.json"
        self.sheet_name = "database"
        self.worksheet = gspread.service_account(self.auth).open(self.sheet_name)
        self.sheet = self.worksheet.sheet1
        self.stats_sheet = self.worksheet.worksheet("stats")
        self.invite_sheet = self.worksheet.worksheet("invites")
        self.sheet_values = self.sheet.get_all_values()
        self.stat_values = self.stats_sheet.get_all_values()
        self.num_rows = len(self.sheet_values)
        self.num_stat_rows = len(self.stat_values)

        self.client = pymongo.MongoClient(os.environ["MONGODB_URI"])
        self.required_fields = ["name", "phone-number"]
        self.db = self.client["agriweathBot"]
        self.user_collection = self.db["newUserCollection"]
        self.token_collection = self.db["tokenCollection"]
        self.bot_collection = self.db["botCollection"]

        self.num_users_w_farms_pipeline = [
    {
        '$match': {
            'farms': {
                '$exists': True
            }
        }
    }, {
        '$count': 'string'
    }
]
        self.users_w_location_pipeline = [
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
        self.num_farms_pipeline = [
    {
        '$project': {
            'farms': {
                '$objectToArray': '$farms'
            }
        }
    }, {
        '$unwind': '$farms'
    }, {
        '$group': {
            '_id': None, 
            'total_farms': {
                '$sum': 1
            }
        }
    }
]
        self.pre_harvest_farms_pipeline = [
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
            'farms.v.harvest-off': False
        }
    }, {
        '$count': 'string'
    }
]
        self.post_harvest_farms_pipeline = [
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
            'farms.v.harvest-off': True
        }
    }, {
        '$count': 'string'
    }
]
        self.invites_pipeline = [
    {
        "$group": {
            "_id": "$owner",
            "used_by": {"$push": "$used-by"}
        }
    },
    {
        "$unwind": "$used_by"
    },
    {
        "$group": {
            "_id": "$_id",
            "used_by_combined": {"$addToSet": "$used_by"}
        }
    },
    {
        "$project": {
            "_id": 0,
            "owner": "$_id",
            "used_by_combined": 1
        }
    }
    ]   
    
    def user_exists_in_sheet(self, user_id):
        rows = [row for row in self.sheet_values[1:] if int(row[0])==user_id]
        if rows==[]:
            logger.info(f"user {user_id} doesn't exist in the sheet")
            return False
        else:
            return True
    
    def check_if_user_is_registered(self, user_id: int):
        document = self.user_collection.find_one( {"_id": user_id} )
        if all(key in document for key in self.required_fields):
            return True
        else:
            return False
    
    def num_users(self) -> int:
        return len(self.user_collection.distinct("_id"))
    
    def num_registered(self) -> int:
        users = self.user_collection.distinct("_id")
        num = 0
        for user in users:
            if self.check_if_user_is_registered(user):
                num += 1
        return num
    
    def num_blocks(self) -> int:
        blocked_users = self.user_collection.count_documents({"blocked": True})
        return blocked_users
    
    def num_users_with_farms(self) -> int:
        return self.user_collection.aggregate(self.num_users_w_farms_pipeline).next()["string"]
    
    def num_farms(self) -> int:
        return self.user_collection.aggregate(self.num_farms_pipeline).next()["total_farms"]
    
    def num_pre_harvest_farms(self) -> int:
        return self.user_collection.aggregate(self.pre_harvest_farms_pipeline).next()["string"]
    
    def num_post_harvest_farms(self) -> int:
        return self.user_collection.aggregate(self.post_harvest_farms_pipeline).next()["string"]
    
    def get_farms(self, user_id: int) -> dict:
        """Use after verifynig user has at least one farm (so it doesn't return None)"""
        user_doc = self.user_collection.find_one( {"_id": user_id} )
        return user_doc.get("farms")

    def get_users_with_location(self) -> dict:
        """Return a dictionary of users who have atleast one farm with known location and the 
        number of such farms belonging to the user"""
        cursor = self.user_collection.aggregate(self.users_w_location_pipeline) # users who have atleast one farm with no location
        users = [user["_id"] for user in cursor]
        out = dict()
        for user in users:
            farms = self.get_farms(user)
            for farm in farms:
                if farms[farm]["location"]["longitude"]:
                    out[user] = out.get(user, 0) + 1
        return out

    def num_invites(self) -> list:
        """returns a list of dicts with keys: 'owner' and 'used_by_combined'"""
        res = list(self.token_collection.aggregate(self.invites_pipeline))
        for item in res:
            item['used_by_combined'] = [user for array in item["used_by_combined"] for user in array]
        output = []
        for item in res:
            if item["used_by_combined"] != []:
                username = self.user_collection.find_one({"_id": item["owner"]})["username"]
                output.append({'owner': item["owner"],"username": username, "invites": len(item["used_by_combined"])})
        return output


    def farm_stats(self):
        users = self.user_collection.distinct("_id")
        users_w_farm, num_farms, farms_w_loc, harvest_off, harvest_on = 0, 0, 0, 0, 0 # users with farms, total number of farms, farms with location
        for user in users:

            user_doc = self.user_collection.find_one({"_id": user})
            farms = user_doc.get("farms", None)
            if farms:
                users_w_farm += 1
                for farm in farms:
                    num_farms += 1
                    if farms[farm]["location"].get("longitude"):
                        farms_w_loc += 1
                    if farms[farm].get("harvest-off"):
                        harvest_off += 1
                    if farms[farm].get("harvest-off")==False:
                        harvest_on += 1
        return {'users_w_farm': users_w_farm, "num_farms": num_farms, "farms_w_loc": farms_w_loc,
                'harvest_off':harvest_off, 'harvest_on': harvest_on}


    def add_missing_row(self, user_id: int, mongo_doc: dict = None, farm_name: str = None, ):
        """
        Given a user_id and no farm name, this function will look for all farms belonging to the user
        and add them to the sheet.
        If farm name is provided, only that farm gets inserted.
        The new row is inserted at the bottom of the sheet.
        """
        # mongo_doc = self.user_collection.find_one( {"_id": user_id} )
        if not mongo_doc:
            return
        
        if farm_name:
            row = [ user_id, 
                    mongo_doc.get("username"),
                    mongo_doc.get("name"),
                    mongo_doc.get("first-seen"),
                    mongo_doc.get("phone-number"),
                    farm_name,
                    mongo_doc['farms'][farm_name].get("product"),
                    mongo_doc['farms'][farm_name].get("province"),
                    mongo_doc['farms'][farm_name].get("city"),
                    mongo_doc['farms'][farm_name].get("village"),
                    mongo_doc['farms'][farm_name].get("area"),
                    mongo_doc['farms'][farm_name]["location"].get("longitude"),
                    mongo_doc['farms'][farm_name]["location"].get("latitude"),
                    mongo_doc['farms'][farm_name].get("location-method"),
                    mongo_doc.get("blocked"),
                    mongo_doc.get("invited-by")]
            self.sheet.insert_row(row, self.num_rows + 1)
            self.num_rows += 1
            logger.info(f"added farm: {farm_name} for user {user_id}")
            time.sleep(0.5)
        else:
            farms = mongo_doc.get("farms")
            if farms:
                farm_names = list(farms.keys())
                i = 0
                for farm in farm_names:
                    row = [ user_id, 
                            mongo_doc.get("username"),
                            mongo_doc.get("name"),
                            mongo_doc.get("first-seen"),
                            mongo_doc.get("phone-number"),
                            farm,
                            mongo_doc['farms'][farm].get("product"),
                            mongo_doc['farms'][farm].get("province"),
                            mongo_doc['farms'][farm].get("city"),
                            mongo_doc['farms'][farm].get("village"),
                            mongo_doc['farms'][farm].get("area"),
                            mongo_doc['farms'][farm]["location"].get("longitude"),
                            mongo_doc['farms'][farm]["location"].get("latitude"),
                            mongo_doc['farms'][farm].get("location-method"),
                            mongo_doc.get("blocked"),
                            mongo_doc.get("invited-by")]
                    self.sheet.insert_row(row, self.num_rows + 1)
                    self.num_rows += 1
                    logger.info(f"added farm: {farm} for user {user_id}")
                    time.sleep(0.5)

            else:
                row = [ user_id, 
                        mongo_doc.get("username"),
                        mongo_doc.get("name"),
                        mongo_doc.get("first-seen"),
                        mongo_doc.get("phone-number"),
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        mongo_doc.get("blocked"),
                        mongo_doc.get("invited-by")
                        ]
                self.sheet.insert_row(row, self.num_rows + 1)
                self.num_rows += 1
                logger.info(f"user {user_id} was added to sheet with no farms")
                time.sleep(0.5)

    def update_existing_rows(self):
        for i, row in enumerate(self.sheet_values[1:]):
            user_id = int(row[0])
            farm_name = row[5]
            mongo_doc = self.user_collection.find_one( {"_id": user_id} )
            if not mongo_doc:
                continue
            if farm_name == "":
                row = [ user_id, 
                        mongo_doc.get("username"),
                        mongo_doc.get("name"),
                        mongo_doc.get("first-seen"),
                        mongo_doc.get("phone-number"),
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        mongo_doc.get("blocked"),
                        mongo_doc.get("invited-by")
                        ]
                self.sheet.update(f"A{i+2}:P{i+2}", [row])
                time.sleep(0.5)
            else:
                try:
                    row = [ user_id, 
                            mongo_doc.get("username"),
                            mongo_doc.get("name"),
                            mongo_doc.get("first-seen"),
                            mongo_doc.get("phone-number"),
                            farm_name,
                            mongo_doc['farms'][farm_name].get("product"),
                            mongo_doc['farms'][farm_name].get("province"),
                            mongo_doc['farms'][farm_name].get("city"),
                            mongo_doc['farms'][farm_name].get("village"),
                            mongo_doc['farms'][farm_name].get("area"),
                            mongo_doc['farms'][farm_name]["location"].get("longitude"),
                            mongo_doc['farms'][farm_name]["location"].get("latitude"),
                            mongo_doc['farms'][farm_name].get("location-method"),
                            mongo_doc.get("blocked"),
                            mongo_doc.get("invited-by")]
                    self.sheet.update(f"A{i+2}:P{i+2}", [row])
                    time.sleep(0.5)
                except KeyError:
                    row = [ user_id, 
                            mongo_doc.get("username"),
                            mongo_doc.get("name"),
                            mongo_doc.get("first-seen"),
                            mongo_doc.get("phone-number"),
                            "",
                            "USER HAS DELETED THIS FARM!"]
                    self.sheet.update(f"A{i+2}:P{i+2}", [row])
                    time.sleep(0.5)

    def find_missing_farms(self, user_id, mongo_doc):
        mongo_farms = mongo_doc.get("farms", None)
        if not mongo_farms:
            return None
        mongo_farm_names = list(mongo_farms.keys())
        sheet_farms = [row[5] for row in self.sheet_values if row[0]==str(user_id)]
        missing = [farm for farm in mongo_farm_names if farm not in sheet_farms]
        if missing == []:
            return None
        else:
            return missing
        
    def find_row_without_farms(self, user_id: int, mongo_doc: dict):
        if not mongo_doc.get('farms'):
            return None
        rows = self.sheet.findall(str(user_id), in_column=1)
        if rows == []:
            return None
        row_idx = [cell.row - 1 for cell in rows]
        no_farms = [idx for idx in row_idx if self.sheet_values[idx][5]==""]
        if no_farms == []:
            return None
        else:
            return no_farms

    def add_missing_farms(self, user_id: int, mongo_doc: dict, missing_farms: list):
        for missing_farm in missing_farms:
            row = [ user_id, 
                    mongo_doc.get("username"),
                    mongo_doc.get("name"),
                    mongo_doc.get("first-seen"),
                    mongo_doc.get("phone-number"),
                    missing_farm,
                    mongo_doc['farms'][missing_farm].get("product"),
                    mongo_doc['farms'][missing_farm].get("province"),
                    mongo_doc['farms'][missing_farm].get("city"),
                    mongo_doc['farms'][missing_farm].get("village"),
                    mongo_doc['farms'][missing_farm].get("area"),
                    mongo_doc['farms'][missing_farm]["location"].get("longitude"),
                    mongo_doc['farms'][missing_farm]["location"].get("latitude"),
                    mongo_doc['farms'][missing_farm].get("location-method"),
                    mongo_doc.get("blocked"),
                    mongo_doc.get("invited-by")]
            no_farm_rows = self.find_row_without_farms(user_id, mongo_doc)
            if no_farm_rows:
                self.sheet.update(f"A{no_farm_rows[0]+1}:P{no_farm_rows[0]+1}", [row])
                time.sleep(0.5)
            else:
                self.sheet.insert_row(row, self.num_rows + 1)
                self.num_rows += 1
                time.sleep(0.5)
    
    def update_stats_sheet(self, date: str = datetime.now().strftime("%Y%m%d %H:%M")): # "%Y-%m-%d %H:%M"
        last_date = self.stat_values[-1][0]

        last_date_dt = datetime.strptime(last_date, "%Y%m%d %H:%M")
        date_dt = datetime.strptime(date, "%Y%m%d %H:%M")

        last_date_first_seen = last_date_dt.strftime("%Y-%m-%d %H:%M")
        date_first_seen = date_dt.strftime("%Y-%m-%d %H:%M")

        ### date + KPIs -> 19
        weather_requests = self.bot_collection.find(
            {'type': 'activity logs', 'user_activity': 'request weather', 'timestamp': {'$lte': date, '$gte': last_date}}
        )
        num_weather_requests = len(list(weather_requests))
        num_weather_requests_unique = len(weather_requests.distinct("userID"))
        sp_requests = self.bot_collection.find(
            {'type': 'activity logs', 'user_activity': 'request sp', 'timestamp': {'$lte': date, '$gte': last_date}}
        )
        num_sp_requests = len(list(sp_requests))
        num_sp_requests_unique = len(sp_requests.distinct("userID"))
        chose_day = self.bot_collection.find(
            {'type': 'activity logs', 'user_activity': 'chose advice date', 'timestamp': {'$lte': date, '$gte': last_date}}
        )
        num_chose_day = len(list(chose_day))
        num_chose_day_unique = len(chose_day.distinct("userID"))
        chose_sp_day = self.bot_collection.find(
            {'type': 'activity logs', 'user_activity': 'chose sp-advice date', 'timestamp': {'$lte': date, '$gte': last_date}}
        )
        num_chose_sp_day = len(list(chose_sp_day))
        num_chose_sp_day_unique = len(chose_sp_day.distinct("userID"))
        ####
        start_register = self.bot_collection.find(
            {'type': 'activity logs', 'user_activity': 'start register', 'timestamp': {'$lte': date, '$gte': last_date}}
        )
        num_start_register = len(list(start_register))
        num_start_register_unique = len(start_register.distinct("userID"))
        num_enter_phone = len(list(self.bot_collection.find(
            {'type': 'activity logs', 'user_activity': 'entered phone', 'timestamp': {'$lte': date, '$gte': last_date}}
        )))
        num_enter_name = len(list(self.bot_collection.find(
            {'type': 'activity logs', 'user_activity': 'entered name', 'timestamp': {'$lte': date, '$gte': last_date}}
        )))
        ####
        start_add = self.bot_collection.find(
            {'type': 'activity logs', 'user_activity': 'start add farm', 'timestamp': {'$lte': date, '$gte': last_date}}
        )
        num_start_add = len(list(start_add))
        num_start_add_unique = len(start_add.distinct("userID"))
        num_chose_name = len(list(self.bot_collection.find(
            {'type': 'activity logs', 'user_activity': 'chose name', 'timestamp': {'$lte': date, '$gte': last_date}}
        )))
        num_chose_product = len(list(self.bot_collection.find(
            {'type': 'activity logs', 'user_activity': 'chose product', 'timestamp': {'$lte': date, '$gte': last_date}}
        )))
        num_chose_province = len(list(self.bot_collection.find(
            {'type': 'activity logs', 'user_activity': 'chose province', 'timestamp': {'$lte': date, '$gte': last_date}}
        )))
        num_chose_city = len(list(self.bot_collection.find(
            {'type': 'activity logs', 'user_activity': 'entered city', 'timestamp': {'$lte': date, '$gte': last_date}}
        )))        
        num_chose_village = len(list(self.bot_collection.find(
            {'type': 'activity logs', 'user_activity': 'entered villagee', 'timestamp': {'$lte': date, '$gte': last_date}}
        )))
        num_chose_area = len(list(self.bot_collection.find(
            {'type': 'activity logs', 'user_activity': 'entered area', 'timestamp': {'$lte': date, '$gte': last_date}}
        )))
        location_success = self.bot_collection.find(
            {'type': 'activity logs', 'user_activity': 'sent location', 'timestamp': {'$lte': date, '$gte': last_date}}
        )
        num_location_success = len(list(location_success))
        num_location_success_unique = len(location_success.distinct("userID"))

        num_location_map = len(list(self.bot_collection.find(
            {'type': 'activity logs', 'user_activity': 'chose to send location from map', 'timestamp': {'$lte': date, '$gte': last_date}}
        )))
        num_location_fail = len(list(self.bot_collection.find(
            {'type': 'activity logs', 'user_activity': 'finish add farm - no location', 'timestamp': {'$lte': date, '$gte': last_date}}
        )))
        num_location_link = len(list(self.bot_collection.find(
            {'type': 'activity logs', 'user_activity': 'sent location link', 'timestamp': {'$lte': date, '$gte': last_date}}
        )))
        invites = self.user_collection.find(
            {'first-seen': {'$lte': date_first_seen, '$gte': last_date_first_seen}, 'invited-by': {'$exists': True}}
        )
        join_with_invite = len(list(invites))
        inviters = invites.distinct("invited-by")
        inviters = [str(person) for person in inviters]
        inviters = ', '.join(inviters)

        invite_btn = self.bot_collection.find(
            {'type': 'activity logs', 'user_activity': 'chose invite-link menu option', 'timestamp': {'$lte': date, '$gte': last_date}}
        )
        num_invite_btn = len(list(invite_btn))
        num_invite_btn_unique = len(invite_btn.distinct("userID"))

        vip_btn = self.bot_collection.find(
            {'type': 'activity logs', 'user_activity': 'navigated to payment view', 'timestamp': {'$lte': date, '$gte': last_date}}
        )
        num_vip_btn = len(list(vip_btn))
        num_vip_btn_unique = len(vip_btn.distinct("userID"))

        payment_link = self.bot_collection.find(
            {'type': 'activity logs', 'user_activity': 'chose payment from menu', 'timestamp': {'$lte': date, '$gte': last_date}}
        )
        num_payment_link = len(list(payment_link))
        num_payment_link_unique = len(payment_link.distinct("userID"))

        verify_payment = self.bot_collection.find(
            {'type': 'activity logs', 'user_activity': 'chose ersal-e fish', 'timestamp': {'$lte': date, '$gte': last_date}}
        )
        num_verify_payment = len(list(verify_payment))
        num_verify_payment_unique = len(verify_payment.distinct("userID"))

        contact_btn = self.bot_collection.find(
            {'type': 'activity logs', 'user_activity': 'viewed contact us message', 'timestamp': {'$lte': date, '$gte': last_date}}
        )
        num_contact_btn = len(list(contact_btn))
        num_contact_btn_unique = len(contact_btn.distinct("userID"))

        # farm_stats = self.farm_stats()
        logger.info("Querying location information...")
        location_info = self.get_users_with_location()
        farms_w_location = 0
        for user in location_info: farms_w_location += location_info[user]
        users_w_location = len(location_info)
        users_w_multi_location = len([user for user in location_info if location_info[user] > 1])
        row = [
            date,
            self.num_users(),
            self.num_registered(),
            self.num_blocks(),
            self.num_users_with_farms(), # farm_stats["users_w_farm"],
            self.num_farms(), # farm_stats["num_farms"],
            farms_w_location,# farm_stats["farms_w_loc"],
            users_w_location, users_w_multi_location,
            num_weather_requests, num_weather_requests_unique,
            num_sp_requests, num_sp_requests_unique,
            num_chose_day, num_chose_day_unique,
            num_chose_sp_day, num_chose_sp_day_unique,
            num_start_register, num_start_register_unique, num_enter_phone, num_chose_name,
            num_start_add, num_start_add_unique, num_enter_name, num_chose_product, num_chose_province, num_chose_city, num_chose_village, num_chose_area,
            num_location_fail, num_location_link, num_location_map, num_location_success, num_location_success_unique,
            join_with_invite,
            inviters,
            num_invite_btn, num_invite_btn_unique,
            num_vip_btn, num_vip_btn_unique,
            num_payment_link, num_payment_link_unique,
            num_verify_payment, num_verify_payment_unique, 
            num_contact_btn, num_contact_btn_unique,
            self.num_post_harvest_farms(), # farm_stats["harvest_off"],
            self.num_pre_harvest_farms() #farm_stats["harvest_on"],
        ]
        self.stats_sheet.update(f"A{self.num_stat_rows+1}:AV{self.num_stat_rows+1}", [row])
        time.sleep(0.5)

    def update_invites_sheet(self):
        invites = self.num_invites()
        self.invite_sheet.delete_rows(2, self.invite_sheet.row_count - 1)
        empty_row = ["", "", ""]
        for i in range(len(invites) + 10):
            self.invite_sheet.insert_row(empty_row, 2)
            time.sleep(1)
        for i, item in enumerate(invites):
            row = [item["owner"], item["username"], item["invites"]]
            self.invite_sheet.update(f"A{i+2}:AS{i+2}", [row])
            time.sleep(1)


def main():
    date = datetime.now().strftime("%Y%m%d %H:%M")
    sheet = Sheet()
    logger.info("Finished initializing")
    mongo_users = sheet.user_collection.distinct("_id")
    logger.info(f"mongo users: {len(mongo_users)}")
    logger.info(f"sheet users: {len(set([int(row[0]) for row in sheet.sheet_values[1:]]))}")
    logger.info("start updating stats sheet")
    logger.info(f"date: {date}")
    sheet.update_stats_sheet(date=date)
    logger.info("Finished updating stats sheet")
    sheet.update_invites_sheet()
    logger.info("Finished updating invites sheet")
    for user in mongo_users:
        mongo_doc = sheet.user_collection.find_one( {"_id": user} )
        if not sheet.user_exists_in_sheet(user):
            logger.info(f"{user} not in sheet")
            sheet.add_missing_row(user, mongo_doc)
        else:
            missing_farms = sheet.find_missing_farms(user, mongo_doc)
            if missing_farms:
                sheet.add_missing_farms(user, mongo_doc, missing_farms)
                logger.info(f"user had missing farms: {missing_farms}")
    logger.info("Finished adding new rows")            
    sheet.update_existing_rows()
    logger.info("Finished updating existing rows")
    
if __name__=="__main__":
    main()
    
