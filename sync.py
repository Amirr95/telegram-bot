import gspread
import database
import time
# Get the MongoDB database
db = database.Database()


# Convert from MongoDB to Sheet
def to_sheet(spread_sheet: gspread.Spreadsheet) -> None:
    users = db.user_collection.distinct("_id")
    row_index = 1
    sheet.sheet1.row_count
    header_row = [  "UserID",
                    "Username",
                    "Name",
                    "First Seen",
                    "Phone",
                    "Farm Name",
                    "Product",
                    "Province",
                    "City",
                    "Village",
                    "Longitude",
                    "Latitude",
                    "Blocked"]
    spread_sheet.sheet1.insert_row(header_row, index=row_index)
    row_index += 1
    time.sleep(1)
    # SHEET.INSTER_ROW(header_row)
    for user_id in users:
        print(user_id)
        document = db.user_collection.find_one({"_id": user_id})
        farms = db.get_farms(user_id=user_id)
        if not farms:
            row = [ user_id,
                    document.get('username'),
                    document.get('name'),
                    document.get('first-seen'),
                    document.get('phone-number'),
                    document.get('farm name'),
                    document.get('product'),
                    document.get('province'),
                    document.get('city'),
                    document.get('village'),
                    document.get('area'),
                    document.get('longitude'),
                    document.get('latitude'),
                    document.get('location-method'),
                    document.get('blocked')]
            spread_sheet.sheet1.insert_row(row, index=row_index)
            row_index += 1
            time.sleep(1)
        elif len(farms) == 1:
            farm_name = list(farms.keys())[0]
            row = [ user_id,
                    document.get('username'),
                    document.get('name'),
                    document.get('first-seen'),
                    document.get('phone-number'),
                    farm_name,
                    farms[farm_name].get('product'),
                    farms[farm_name].get('province'),
                    farms[farm_name].get('city'),
                    farms[farm_name].get('village'),
                    farms[farm_name].get('area'),
                    farms[farm_name]['location'].get('longitude'),
                    farms[farm_name]['location'].get('latitude'),
                    farms[farm_name].get('location-method'),
                    document.get('blocked')]
            spread_sheet.sheet1.insert_row(row, index=row_index)
            row_index += 1
            time.sleep(1)
        elif len(farms) > 1:
            for key in farms:
                row = [ user_id,
                        document.get('username'),
                        document.get('name'),
                        document.get('first-seen'),
                        document.get('phone-number'),
                        key,
                        farms[key].get('product'),
                        farms[key].get('province'),
                        farms[key].get('city'),
                        farms[key].get('village'),
                        farms[key].get('area'),
                        farms[key]['location'].get('longitude'),
                        farms[key]['location'].get('latitude'),
                        farms[key].get('location-method'),
                        document.get('blocked')]
                spread_sheet.sheet1.insert_row(row, index=row_index)
                row_index += 1
                time.sleep(1)


def update_sheet(spread_sheet: gspread.Spreadsheet):
    sheet_values = spread_sheet.sheet1.get_all_values()
    for i, row in enumerate(sheet_values[1:]):
        user_id = row[0]
        user_document = db.user_collection.find_one({"_id": int(user_id)})
        user_farms = user_document.get("farms")
        if not user_farms:
            continue
        farm_name = row[5]
        username = user_document.get("username")
        name = user_document.get("name")
        first_seen = user_document.get("first-seen")
        phone = user_document.get("phone-number")
        product = user_document["farms"][farm_name].get("product")
        province = user_document["farms"][farm_name].get("province")
        city = user_document["farms"][farm_name].get("city")
        village = user_document["farms"][farm_name].get("village")
        area = user_document["farms"][farm_name].get("area")
        longitude = str(user_document["farms"][farm_name]['location'].get("longitude"))
        latitude = str(user_document["farms"][farm_name]['location'].get("latitude"))
        loc_method = user_document.get('location-method')
        blocked = user_document["blocked"]
        if not (product==row[6] and province==row[7] and city==row[8] and village==row[9] and
                    area==row[10] and longitude==row[11] and latitude==row[12] and blocked==row[13]):
            new_row = [user_id, username, name, first_seen, phone, 
                   farm_name, product, province, city, village, 
                   area, longitude, latitude, loc_method, blocked]
            print(new_row)
            spread_sheet.sheet1.update(f"A{i+2}:O{i+2}", [new_row])
            time.sleep(1)
    # Add new users to the sheet
    users = db.user_collection.distinct("_id")
    users_in_sheet = set([int(row[0]) for row in sheet_values[1:]])
    row_index = len(sheet_values) + 1
    for user_id in users:
        if user_id not in users_in_sheet:
            print(f"{user_id} was not in the sheet")
            document = db.user_collection.find_one({"_id": user_id})
            farms = db.get_farms(user_id=user_id)
            if not farms:
                row = [ user_id,
                        document.get('username'),
                        document.get('name'),
                        document.get('first-seen'),
                        document.get('phone-number'),
                        document.get('farm name'),
                        document.get('product'),
                        document.get('province'),
                        document.get('city'),
                        document.get('village'),
                        document.get('area'),
                        document.get('longitude'),
                        document.get('latitude'),
                        document.get('location-method'),
                        document.get('blocked')]
                spread_sheet.sheet1.insert_row(row, index=row_index)
                row_index += 1
                time.sleep(1)
            elif len(farms) == 1:
                farm_name = list(farms.keys())[0]
                row = [ user_id,
                        document.get('username'),
                        document.get('name'),
                        document.get('first-seen'),
                        document.get('phone-number'),
                        farm_name,
                        farms[farm_name].get('product'),
                        farms[farm_name].get('province'),
                        farms[farm_name].get('city'),
                        farms[farm_name].get('village'),
                        farms[farm_name].get('area'),
                        farms[farm_name]['location'].get('longitude'),
                        farms[farm_name]['location'].get('latitude'),
                        farms[farm_name].get('location-method'),
                        document.get('blocked')]
                spread_sheet.sheet1.insert_row(row, index=row_index)
                row_index += 1
                time.sleep(1)
            elif len(farms) > 1:
                for key in farms:
                    row = [ user_id,
                            document.get('username'),
                            document.get('name'),
                            document.get('first-seen'),
                            document.get('phone-number'),
                            key,
                            farms[key].get('product'),
                            farms[key].get('province'),
                            farms[key].get('city'),
                            farms[key].get('village'),
                            farms[key].get('area'),
                            farms[key]['location'].get('longitude'),
                            farms[key]['location'].get('latitude'),
                            farms[key].get('location-method'),
                            document.get('blocked')]
                    spread_sheet.sheet1.insert_row(row, index=row_index)
                    row_index += 1
                    time.sleep(1)




if __name__=="__main__":
     # Get the google Sheet
    gc = gspread.service_account("./.gspread/sheet-database-395306-fa93d0ea2e6e.json")
    sheet = gc.open("database")
    update_sheet(sheet)