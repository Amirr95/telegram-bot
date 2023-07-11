import pymongo
from datetime import datetime


USER_FIELDS = [
    "_id",
    "username",
    "product",
    "province",
    "city",
    "village",
    "phone",
    "name",
    "location",
    "user_journey",
]


class Database:
    def __init__(self) -> None:
        self.client = pymongo.MongoClient("mongodb://127.0.0.1:27017")
        self.db = self.client["bot"]  # database name
        self.user_collection = self.db["users"]
        self.bot_collection = self.db["bot"]
        self.dialog_collection = self.db["dialog"]

    def check_if_user_exists(self, user_id: int, raise_exception: bool = False):
        if self.user_collection.count_documents({"_id": user_id}) > 0:
            return True
        else:
            if raise_exception:
                raise ValueError(f"User {user_id} does not exist")
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
        product: str = "",
        province: str = "",
        city: str = "",
        village: str = "",
        phone_number: str = "",
        name: str = "",
        location: dict = {},
    ):
        user_dict = {
            "_id": user_id,
            "username": username,
            "product": product,
            "province": province,
            "city": city,
            "village": village,
            "phone_number": phone_number,
            "name": name,
            "location": location,
            "first-seen": datetime.now().strftime("%Y-%m-%d H:m:s")
        }

        if not self.check_if_user_exists(user_id=user_id):
            self.user_collection.insert_one( user_dict )
    
    def get_user_attribute(self, user_id: int, key: str):
        self.check_if_user_exists(user_id=user_id, raise_exception=True)
        user_dict = self.user_collection.find_one( {"_id": user_id} )

        if key not in user_dict:
            return None
        return user_dict[key]
    
    def set_user_attribute(self, user_id: int, key: str, value: any):
        self.check_if_user_exists(user_id=user_id, raise_exception=True)
        self.user_collection.update_one({"_id": user_id}, {"$set": {key: value}})

    # def log_message_to_user(self, user_id: int, message: str):
    #     self.check_if_user_exists(user_id=user_id, raise_exception=True)

    def log_new_message(
        self,
        user_id,
        username: str = "",
        message: str = "",
    ):
        current_time = datetime.now().strftime("%Y%m%d H:m:s")
        dialog_dict = {
            "_id": user_id,
            "username": username,
            "message": [f"{current_time} - {message}"]
        }

        if not self.check_if_dialog_exists(user_id=user_id):
            self.dialog_collection.insert_one( dialog_dict )
        else:
            self.dialog_collection.update_one({"id": user_id}, {"$push": {"message": f"{current_time} - {message}"}})
    

    

