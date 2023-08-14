import os
import pymongo
import gspread
import time
import logging
from logging.handlers import RotatingFileHandler
import warnings

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
    def __init__(self):
        self.auth = ".gspread/sheet.json"
        self.sheet_name = "database"
        self.sheet = gspread.service_account(self.auth).open(self.sheet_name).sheet1
        self.sheet_values = self.sheet.get_all_values()
        self.num_rows = len(self.sheet_values)

        self.client = pymongo.MongoClient(os.environ["MONGODB_URI"])
        self.db = self.client["agriweathBot"]
        self.user_collection = self.db["newUserCollection"]

    def user_exists_in_sheet(self, user_id):
        rows = [row for row in self.sheet_values[1:] if int(row[0])==user_id]
        if rows==[]:
            logger.info(f"user {user_id} doesn't exist in the sheet")
            return False
        else:
            return True
    

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
                    mongo_doc['farms'][farm_name].get("blocked")]
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
                            mongo_doc['farms'][farm].get("blocked")]
                    self.sheet.insert_row(row, self.num_rows + 1)
                    self.num_rows += 1
                    logger.info(f"added farm: {farm} for user {user_id}")
                    time.sleep(0.5)

            else:
                row = [ user_id, 
                        mongo_doc.get("username"),
                        mongo_doc.get("name"),
                        mongo_doc.get("first-seen"),
                        mongo_doc.get("phone-number")]
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
                        mongo_doc.get("phone-number")]
                self.sheet.update(f"A{i+2}:O{i+2}", [row])
                time.sleep(0.5)
            else:
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
                        mongo_doc['farms'][farm_name].get("blocked")]
                self.sheet.update(f"A{i+2}:O{i+2}", [row])
                time.sleep(0.5)
            
    # def add_new_users(self, new_user: int = None):
    #     mongo_users = self.user_collection.distinct("_id")
    #     if not new_user:
    #         if self.num_rows == 0:
    #             new_users = mongo_users
    #             header_row = [  "UserID",
    #                             "Username",
    #                             "Name",
    #                             "First Seen",
    #                             "Phone",
    #                             "Farm Name",
    #                             "Product",
    #                             "Province",
    #                             "City",
    #                             "Village",
    #                             "Longitude",
    #                             "Latitude",
    #                             "Location Method",
    #                             "Blocked"]
    #             self.sheet.insert_row(header_row, index=0)
    #             self.num_rows += 1
    #             time.sleep(0.5)
    #         else:
    #             try:
    #                 sheet_users = set([int(row[0]) for row in self.sheet_values[1:]])
    #                 new_users = [user for user in mongo_users if user not in sheet_users]
    #             except ValueError:
    #                 pass
    #                 # logger.error("row[0] probably couldn't become an INT.")
    #         for user in new_users:
    #             self.add_row_to_sheet(user)
    #     else:
    #         self.add_row_to_sheet(new_user)

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
                    mongo_doc['farms'][missing_farm].get("blocked")]
            no_farm_rows = self.find_row_without_farms(user_id, mongo_doc)
            if no_farm_rows:
                self.sheet.update(f"A{no_farm_rows[0]+1}:O{no_farm_rows[0]+1}", [row])
                time.sleep(0.5)
            else:
                self.sheet.insert_row(row, self.num_rows + 1)
                self.num_rows += 1
                time.sleep(0.5)

def main():
    sheet = Sheet()
    logger.info("Finished initializing")
    mongo_users = sheet.user_collection.distinct("_id")
    logger.info(f"mongo users: {len(mongo_users)}")
    logger.info(f"sheet users: {len(set([int(row[0]) for row in sheet.sheet_values[1:]]))}")
    for user in mongo_users:
        mongo_doc = sheet.user_collection.find_one( {"_id": user} )
        if not sheet.user_exists_in_sheet(user):
            sheet.add_missing_row(user, mongo_doc)
        else:
            missing_farms = sheet.find_missing_farms(user, mongo_doc)
            if missing_farms:
                sheet.add_missing_farms(user, mongo_doc, missing_farms)
    logger.info("Finished adding new rows")            
    sheet.update_existing_rows()

    
if __name__=="__main__":
    main()
    