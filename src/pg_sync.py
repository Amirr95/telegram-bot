import psycopg2
import os
import pytz
from datetime import datetime

from utils.logger import logger


class PgSync:
    def __init__(self):
        try:
            self.conn = psycopg2.connect(
                database=os.getenv('DB_NAME'),
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD'),
                host=os.getenv('DB_HOST'),
                port=os.getenv('DB_PORT')
            )
        except psycopg2.OperationalError as e:
            logger.error(f"Error connecting to PostGres database: {e}")
            self.conn = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
    
    def get_cursor(self):
        if self.conn is not None:
            try:
                return self.conn.cursor()
            except psycopg2.Error as e:
                logger.error(f"Error getting cursor: {e}")
                return None
    
    def close(self):
        if self.conn is not None:
            try:
                self.conn.close()
            except psycopg2.Error as e:
                logger.error(f"Error closing connection to Database: {e}")
            self.conn = None

def check_user_in_postgres(phone: str):
    with PgSync() as pg:
        cursor = pg.get_cursor()
        if cursor is not None:
            cursor.execute("SELECT * FROM users_user WHERE phone_number = %s", (phone,))
            result = cursor.fetchone()
            cursor.close()
            if result is not None:
                return True
            else:
                return False
        else:
            logger.error("Error getting cursor")
            return False

def add_user_to_postgres(name: str, phone: str):
    now = datetime.now(pytz.timezone('Asia/Tehran'))
    timestamp = now.isoformat()
    timestamp = timestamp.replace("T", " ")
    with PgSync() as pg:
        cursor = pg.get_cursor()
        if cursor is not None:
            # Check if a user with the same phone number already exists
            cursor.execute("SELECT * FROM users_user WHERE phone_number = %s", (phone,))
            if cursor.fetchone() is not None:
                return
            cursor.execute("""
                    INSERT INTO users_user (
                        name, phone_number, date_joined, is_superuser,
                        is_staff, is_active, first_name, last_name, email
                    ) 
                    VALUES (%s, %s, %s, false, false, true,'','','')
                    """, (name, phone, timestamp,))
            cursor.close()
            pg.conn.commit()
        else:
            logger.error("Error getting cursor")

def add_farm_to_postgres(phone_number: str, farm_name: str):
    with PgSync() as pg:
        try:
            with pg.get_cursor() as cursor:
                # Retrieve the owner_id from the users_user table
                cursor.execute("SELECT id FROM users_user WHERE phone_number = %s", (phone_number,))
                result = cursor.fetchone()
                if result is None:
                    raise ValueError(f"No user found in PG with phone number {phone_number}")
                owner_id = result[0]
                
                cursor.execute("""
                    INSERT INTO core_farm (
                        owner_id, name, status
                    ) 
                    VALUES (%s, %s, 'incomplete')
                """, (owner_id, farm_name))
                pg.conn.commit()
        except psycopg2.Error as e:
            logger.error(f"Error executing query: {e}")

def update_farm_in_postgres(phone_number: str,
                            farm_name: str,
                            **kwargs):
    with PgSync() as pg:
        try:
            with pg.get_cursor() as cursor:
                # Start a transaction block to ensure atomicity. Needed because we are executing multiple operations.
                cursor.execute("BEGIN") 
                cursor.execute("SELECT id FROM users_user WHERE phone_number = %s", (phone_number,))
                result = cursor.fetchone()
                if result is None:
                    raise ValueError(f"No user found in PG with phone number {phone_number}")
                owner_id = result[0]
                cursor.execute("SELECT id FROM core_farm WHERE name = %s AND owner_id = %s", (farm_name, owner_id))
                result = cursor.fetchone()
                if result is None:
                    raise ValueError(f"No farm found in PG with name {farm_name} and owner_id {owner_id}")
                farm_id = result[0]
                
                # Handle location column separately
                location = kwargs.pop('location', None)
                if location:
                    # Location is received as a tuple of (longitude, latitude)
                    cursor.execute("""UPDATE core_farm 
                                   SET location = ST_SetSRID(ST_MakePoint(%s, %s), 4326) 
                                   WHERE id = %s""", (*location, farm_id))
                # Handle province_id column separately
                province = kwargs.pop('province', None)
                if province:
                    cursor.execute("SELECT id FROM core_province WHERE name = %s", (province,))
                    result = cursor.fetchone()
                    if result is None:
                        province_id = 31
                    else:
                        province_id = result[0]
                    cursor.execute("""UPDATE core_farm 
                                   SET province_id = %s 
                                   WHERE id = %s""", (province_id, farm_id))
                if kwargs:
                    updated_columns = ', '.join([f"{key} = %s" for key in kwargs.keys()])
                    updated_values = tuple(kwargs.values())
                    update_statement = f"UPDATE core_farm SET {updated_columns} WHERE id = %s"
                    cursor.execute(update_statement, updated_values + (farm_id,))
                
                cursor.execute("COMMIT")
        except psycopg2.Error as e:
            cursor.execute("ROLLBACK")
            logger.error(f"Error executing query: {e}")
            
def delete_farm_from_pg(phone_number: str, farm_name: str):
    with PgSync() as pg:
        try:
            with pg.get_cursor() as cursor:
                cursor.execute("SELECT id FROM users_user WHERE phone_number = %s", (phone_number,))
                result = cursor.fetchone()
                if result is None:
                    raise ValueError(f"No user found in PG with phone number {phone_number}")
                owner_id = result[0]
                cursor.execute("DELETE FROM core_farm WHERE name = %s AND owner_id = %s", (farm_name, owner_id))
                pg.conn.commit()
        except psycopg2.Error as e:
            logger.error(f"Error executing query: {e}")

# function to add a row to core_farm      
def sync_farm_with_postgres(phone_number: str,
                            farm_name: str,
                            farm_type: str = None,
                            product: str = None,
                            province: str = None,
                            city: str = None,
                            village: str = None,
                            area: int = None,
                            longitude: float = None,
                            latitude: float = None,
                            pesteh_type: str = None,
                            automn_date: str = None):
    if (farm_type and 
        product and 
        province and 
        city and 
        area and 
        longitude and 
        latitude):
        status = 'complete'
    else:
        status = 'incomplete'        
    with PgSync() as pg:
        try:
            with pg.get_cursor() as cursor:
                # Retrieve the owner_id from the users_user table
                cursor.execute("SELECT id FROM users_user WHERE phone_number = %s", (phone_number,))
                result = cursor.fetchone()
                if result is None:
                    raise ValueError(f"No user found in PG with phone number {phone_number}")
                owner_id = result[0]
                cursor.execute("SELECT id FROM core_province WHERE name = %s", (province,))
                result = cursor.fetchone()
                if result is None:
                    province_id = 31 # If province is not found, set it to "Unknown"
                else:
                    province_id = result[0]

                # Insert the new row into the core_farm table
                cursor.execute("""
                    INSERT INTO core_farm (
                        owner_id, name, farm_type, products, province_id, city, 
                        village, area, location, automn_date, status
                    ) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s)
                """, (owner_id, farm_name, farm_type, product, province_id, city, village, area, longitude, latitude, automn_date, status))
                pg.conn.commit()
        except psycopg2.Error as e:
            logger.error(f"Error executing query: {e}")
            
