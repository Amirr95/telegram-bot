import psycopg2
import os
import pytz
from typing import Dict
from datetime import datetime, time, timedelta
from jdatetime import datetime as jdatetime
from jdatetime import timedelta as jtimedelta

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
            
def query_frost_temp(latitude: float, longitude: float) -> Dict[str, int]:
    current_time = datetime.utcnow().time()
    end_time = time(20, 30)
    start_time = time(5, 30)
    frost_temp = {}
    dates = [(datetime.utcnow() + timedelta(days=i)).strftime("%Y%m%d") for i in range(3)]
    # dates = ["20240321", "20240322", "20240323"]

    if start_time <= current_time < end_time:
        labels = [(jdatetime.utcnow() + jtimedelta(days=i)).strftime("%Y/%m/%d") for i in range(3)]
        sql_today = f"""
        SELECT "d:{dates[0]}_h:06_11" AS day1h2, "d:{dates[0]}_h:12_17" AS day1h3, "d:{dates[0]}_h:18_23" AS day1h4, "d:{dates[1]}_h:00_05" AS day2h1, "d:{dates[1]}_h:06_11" AS day2h2, "d:{dates[1]}_h:12_17" AS day2h3, "d:{dates[1]}_h:18_23" AS day2h4, "d:{dates[2]}_h:00_05" AS day3h1, "d:{dates[2]}_h:06_11" AS day3h2, "d:{dates[2]}_h:12_17" AS day3h3, "d:{dates[2]}_h:18_23" AS day3h4
        FROM "spring_frost_temp"
        WHERE ST_DWithin(wkb_geometry::geography, ST_GeomFromEWKT('SRID=4326;POINT({longitude} {latitude})')::geography, 10000)
        ORDER BY ST_Distance(wkb_geometry::geography, ST_GeomFromEWKT('SRID=4326;POINT({longitude} {latitude})')::geography)
        LIMIT 1;
        """
        sql_yesterday = f"""
        SELECT "d:{dates[0]}_h:00_05" AS day1h1
        FROM "spring_frost_temp_yesterday"
        WHERE ST_DWithin(wkb_geometry::geography, ST_GeomFromEWKT('SRID=4326;POINT({longitude} {latitude})')::geography, 10000)
        ORDER BY ST_Distance(wkb_geometry::geography, ST_GeomFromEWKT('SRID=4326;POINT({longitude} {latitude})')::geography)
        LIMIT 1;
        """
        with PgSync() as pg:
            try:
                with pg.get_cursor() as cursor:
                    cursor.execute(sql_yesterday)
                    rows_yesterday = cursor.fetchall()
                    if rows_yesterday:
                        for row in rows_yesterday:
                            row_dict_yesterday = dict(zip([column[0] for column in cursor.description], row))
                            frost_temp["day1h1"] = row_dict_yesterday.get("day1h1")
                    cursor.execute(sql_today)
                    rows_today = cursor.fetchall()
                    if rows_today:
                        for row in rows_today:
                            row_dict_today = dict(zip([column[0] for column in cursor.description], row))
                            frost_temp["day1h2"] = row_dict_today.get("day1h2")
                            frost_temp["day1h3"] = row_dict_today.get("day1h3")
                            frost_temp["day1h4"] = row_dict_today.get("day1h4")
                            frost_temp["day2h1"] = row_dict_today.get("day2h1")
                            frost_temp["day2h2"] = row_dict_today.get("day2h2")
                            frost_temp["day2h3"] = row_dict_today.get("day2h3")
                            frost_temp["day2h4"] = row_dict_today.get("day2h4")
                            frost_temp["day3h1"] = row_dict_today.get("day3h1")
                            frost_temp["day3h2"] = row_dict_today.get("day3h2")
                            frost_temp["day3h3"] = row_dict_today.get("day3h3")
                            frost_temp["day3h4"] = row_dict_today.get("day3h4")
                    if rows_today and rows_yesterday:
                        return {"frost-temp": list(frost_temp.values()), "labels": labels}
                    else:
                        return {}
            except psycopg2.Error as e:
                logger.error(f"Error executing query: {e}")
                return {}
    else:
        labels = [(jdatetime.utcnow() + jtimedelta(days=i)).strftime("%Y/%m/%d") for i in range(2)]
        sql = f"""
        SELECT "d:{dates[1]}_h:00_05" AS day1h1, "d:{dates[1]}_h:06_11" AS day1h2, "d:{dates[1]}_h:12_17" AS day1h3, "d:{dates[1]}_h:18_23" AS day1h4, "d:{dates[2]}_h:00_05" AS day2h1, "d:{dates[2]}_h:06_11" AS day2h2, "d:{dates[2]}_h:12_17" AS day2h3, "d:{dates[2]}_h:18_23" AS day2h4
        FROM "spring_frost_temp"
        WHERE ST_DWithin(wkb_geometry::geography, ST_GeomFromEWKT('SRID=4326;POINT({longitude} {latitude})')::geography, 10000)
        ORDER BY ST_Distance(wkb_geometry::geography, ST_GeomFromEWKT('SRID=4326;POINT({longitude} {latitude})')::geography)
        LIMIT 1;
        """
        with PgSync() as pg:
            try:
                with pg.get_cursor() as cursor:
                    cursor.execute(sql)
                    rows = cursor.fetchall()
            except psycopg2.Error as e:
                logger.error(f"Error executing query: {e}")
                return {}
            
            if rows:
                for row in rows:
                    row_dict = dict(zip([column[0] for column in cursor.description], row))
                    frost_temp["day1h1"] = row_dict.get("day1h1")
                    frost_temp["day1h2"] = row_dict.get("day1h2")
                    frost_temp["day1h3"] = row_dict.get("day1h3")
                    frost_temp["day1h4"] = row_dict.get("day1h4")
                    frost_temp["day2h1"] = row_dict.get("day2h1")
                    frost_temp["day2h2"] = row_dict.get("day2h2")
                    frost_temp["day2h3"] = row_dict.get("day2h3")
                    frost_temp["day2h4"] = row_dict.get("day2h4")
                return {"frost-temp": list(frost_temp.values()), "labels": labels}
            else:
                return {}
            

def query_frost_wind(latitude: float, longitude: float) -> Dict[str, int]:
    current_time = datetime.utcnow().time()
    end_time = time(20, 30)
    start_time = time(5, 30)
    frost_wind = {}
    dates = [(datetime.utcnow() + timedelta(days=i)).strftime("%Y%m%d") for i in range(3)]
    # dates = ["20240321", "20240322", "20240323"]

    if start_time <= current_time < end_time:
        labels = [(jdatetime.utcnow() + jtimedelta(days=i)).strftime("%Y/%m/%d") for i in range(3)]
        sql_today = f"""
        SELECT "d:{dates[0]}_h:06_11" AS day1h2, "d:{dates[0]}_h:12_17" AS day1h3, "d:{dates[0]}_h:18_23" AS day1h4, "d:{dates[1]}_h:00_05" AS day2h1, "d:{dates[1]}_h:06_11" AS day2h2, "d:{dates[1]}_h:12_17" AS day2h3, "d:{dates[1]}_h:18_23" AS day2h4, "d:{dates[2]}_h:00_05" AS day3h1, "d:{dates[2]}_h:06_11" AS day3h2, "d:{dates[2]}_h:12_17" AS day3h3, "d:{dates[2]}_h:18_23" AS day3h4
        FROM "spring_frost_wind"
        WHERE ST_DWithin(wkb_geometry::geography, ST_GeomFromEWKT('SRID=4326;POINT({longitude} {latitude})')::geography, 10000)
        ORDER BY ST_Distance(wkb_geometry::geography, ST_GeomFromEWKT('SRID=4326;POINT({longitude} {latitude})')::geography)
        LIMIT 1;
        """
        sql_yesterday = f"""
        SELECT "d:{dates[0]}_h:00_05" AS day1h1
        FROM "spring_frost_wind_yesterday"
        WHERE ST_DWithin(wkb_geometry::geography, ST_GeomFromEWKT('SRID=4326;POINT({longitude} {latitude})')::geography, 10000)
        ORDER BY ST_Distance(wkb_geometry::geography, ST_GeomFromEWKT('SRID=4326;POINT({longitude} {latitude})')::geography)
        LIMIT 1;
        """
        with PgSync() as pg:
            try:
                with pg.get_cursor() as cursor:
                    cursor.execute(sql_yesterday)
                    rows_yesterday = cursor.fetchall()
                    if rows_yesterday:
                        for row in rows_yesterday:
                            row_dict_yesterday = dict(zip([column[0] for column in cursor.description], row))
                            frost_wind["day1h1"] = row_dict_yesterday.get("day1h1")
                    cursor.execute(sql_today)
                    rows_today = cursor.fetchall()
                    if rows_today:
                        for row in rows_today:
                            row_dict_today = dict(zip([column[0] for column in cursor.description], row))
                            frost_wind["day1h2"] = row_dict_today.get("day1h2")
                            frost_wind["day1h3"] = row_dict_today.get("day1h3")
                            frost_wind["day1h4"] = row_dict_today.get("day1h4")
                            frost_wind["day2h1"] = row_dict_today.get("day2h1")
                            frost_wind["day2h2"] = row_dict_today.get("day2h2")
                            frost_wind["day2h3"] = row_dict_today.get("day2h3")
                            frost_wind["day2h4"] = row_dict_today.get("day2h4")
                            frost_wind["day3h1"] = row_dict_today.get("day3h1")
                            frost_wind["day3h2"] = row_dict_today.get("day3h2")
                            frost_wind["day3h3"] = row_dict_today.get("day3h3")
                            frost_wind["day3h4"] = row_dict_today.get("day3h4")
                    if rows_today and rows_yesterday:
                        return {"frost-wind": list(frost_wind.values()), "labels": labels}
                    else:
                        return {}
            except psycopg2.Error as e:
                logger.error(f"Error executing query: {e}")
                return {}
    else:
        labels = [(jdatetime.utcnow() + jtimedelta(days=i)).strftime("%Y/%m/%d") for i in range(2)]
        sql = f"""
        SELECT "d:{dates[1]}_h:00_05" AS day1h1, "d:{dates[1]}_h:06_11" AS day1h2, "d:{dates[1]}_h:12_17" AS day1h3, "d:{dates[1]}_h:18_23" AS day1h4, "d:{dates[2]}_h:00_05" AS day2h1, "d:{dates[2]}_h:06_11" AS day2h2, "d:{dates[2]}_h:12_17" AS day2h3, "d:{dates[2]}_h:18_23" AS day2h4
        FROM "spring_frost_wind"
        WHERE ST_DWithin(wkb_geometry::geography, ST_GeomFromEWKT('SRID=4326;POINT({longitude} {latitude})')::geography, 10000)
        ORDER BY ST_Distance(wkb_geometry::geography, ST_GeomFromEWKT('SRID=4326;POINT({longitude} {latitude})')::geography)
        LIMIT 1;
        """
        with PgSync() as pg:
            try:
                with pg.get_cursor() as cursor:
                    cursor.execute(sql)
                    rows = cursor.fetchall()
            except psycopg2.Error as e:
                logger.error(f"Error executing query: {e}")
                return {}
            
            if rows:
                for row in rows:
                    row_dict = dict(zip([column[0] for column in cursor.description], row))
                    frost_wind["day1h1"] = row_dict.get("day1h1")
                    frost_wind["day1h2"] = row_dict.get("day1h2")
                    frost_wind["day1h3"] = row_dict.get("day1h3")
                    frost_wind["day1h4"] = row_dict.get("day1h4")
                    frost_wind["day2h1"] = row_dict.get("day2h1")
                    frost_wind["day2h2"] = row_dict.get("day2h2")
                    frost_wind["day2h3"] = row_dict.get("day2h3")
                    frost_wind["day2h4"] = row_dict.get("day2h4")
                return {"frost-wind": list(frost_wind.values()), "labels": labels}
            else:
                return {}