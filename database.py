import pymongo
from datetime import datetime
import pickle
import pandas as pd
import os

REQUIRED_FIELDS = [
    "_id",
    "username",
    "name",
    "phone-number",
]


class Database:
    def __init__(self) -> None:
        self.client = pymongo.MongoClient(os.environ["MONGODB_URI"])
        self.db = self.client[os.environ["MONGODB_NAME"]]  # database name
        self.user_collection = self.db[os.environ["USER_COLLECTION"]]
        self.bot_collection = self.db[os.environ["BOT_COLLECTION"]]
        self.dialog_collection = self.db[os.environ["DIALOG_COLLECTION"]]

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

    def check_if_dialog_exists(self, user_id: int, raise_exception: bool = False):
        if self.dialog_collection.count_documents({"_id": user_id}) > 0:
            return True
        else:
            if raise_exception:
                raise ValueError(f"User {user_id} does not exist")
            else:
                return False
    
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


    def add_new_farm(self, user_id, farm_name: str, new_farm: dict):
        self.user_collection.update_one(
            {"_id": user_id},
            {"$set": {f"farms.{farm_name}": new_farm}}
        )

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

    def log_activity(self, user_id: int, user_activity: str):
        activity = {
            "user_activity": user_activity,
            "type": "activity logs",
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


    def populate_user_collection(
            self,
            user_id,
            username: str = "",
            product: str = "",
            province: str = "",
            city: str = "",
            village: str = "",
            area = 0,
            phone_number: str = "",
            name: str = "",
            location: dict = {},
            first_seen: str = datetime.now().strftime("%Y-%m-%d %H:%M")
        ):
            user_dict = {
                "_id": user_id,
                "username": username,
                "products": [product],
                "provinces": [province],
                "cities": [city],
                "villages": [village],
                "areas": [area],
                "phone-number": phone_number,
                "name": name,
                "locations": [location],
                "first-seen": first_seen
                # "first-seen": datetime.now().strftime("%Y-%m-%d %H:%m:%s"),
            }

            if not self.check_if_user_exists(user_id=user_id):
                self.user_collection.insert_one(user_dict)
                print(f"added {user_id} to userCollection")
    def populate_mongodb_from_pickle(self):
        with open("bot_data.pickle", "rb") as f:
            user_data = pickle.load(f)["user_data"]
        for key in user_data:
            username = user_data[key].get("username", None)
            product = user_data[key].get("produce", "")
            province = user_data[key].get("province", "")
            city = user_data[key].get("city", "")
            village = user_data[key].get("village", "")
            area = user_data[key].get("area", 0)
            phone_number = user_data[key].get("phone", "")
            name = user_data[key].get("name", "")
            location = user_data[key].get("location", {})
            first_seen = user_data[key].get("join-date")
            self.populate_user_collection(key, username, product, province, city, village, area, phone_number, name, location, first_seen)


    def to_excel(self, output_file: str) -> None:
        user_df = pd.DataFrame(columns=['id', 'username', 'product', 'province', 'city', 'village','area', 'phone', 'latitude', 'longitude', 'name', 'blocked'])
        users = self.user_collection.distinct("_id")
        for i, user_id in enumerate(users):
            document = self.user_collection.find_one({"_id": user_id})
            location = document.get('locations')
            if location[0].get("longitude"):
                latitude = [loc['latitude'] for loc in location]
                longitude = [loc['longitude'] for loc in location]
            else:
                latitude = None
                longitude = None
            user_df.loc[i] = pd.Series({
                'id': user_id,
                'username': document.get('username'),
                'product': document.get('products'),
                'province': document.get('provinces'),
                'city': document.get('cities'),
                'village': document.get('villages'),
                'area': document.get('areas'),
                'phone': document.get('phone-number'),
                'latitude': latitude,
                'longitude': longitude,
                'name': document.get('name'),
                'blocked': document.get('blocked'),
            })
        
        user_df.to_excel(output_file)
