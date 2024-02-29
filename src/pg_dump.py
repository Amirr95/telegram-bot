import database
from pg_sync import check_user_in_postgres, add_user_to_postgres, sync_farm_with_postgres

from src.utils.number_transformer import extract_number
from utils.logger import logger

if __name__ == "__main__":
    mongo = database.Database()
    print("Getting registered users from Mongo")
    registered_mongo_users = mongo.get_registered_users()
    
    for user in registered_mongo_users:
        if not check_user_in_postgres(user['phone-number']):
            add_user_to_postgres(user['name'], user['phone-number'])
        farms = user.get('farms')
        if farms:
            for farm in user['farms']:
                area = farms[farm].get('area', '')
                if not isinstance(area, float):
                    area = extract_number(area)
                if not area:
                    area = 0
                sync_farm_with_postgres(
                    phone_number=user['phone-number'],
                    farm_name=farm,
                    farm_type=farms[farm].get('type'),
                    product=farms[farm].get('product'),
                    province=farms[farm].get('province'),
                    city=farms[farm].get('city'),
                    village=farms[farm].get('village'),
                    area=area,
                    longitude=farms[farm].get('location', {}).get('longitude'), 
                    latitude=farms[farm].get('location', {}).get('latitude'),
                    automn_date=farms[farm].get('automn-time')
                )
        