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
