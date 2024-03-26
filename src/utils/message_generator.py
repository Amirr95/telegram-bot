import jdatetime
from jdatetime import datetime, timedelta


def generate_messages(frost_temp: list[int], frost_wind: list[int]) -> list[str]:
    dates = [(datetime.today() + timedelta(i)).strftime("%m/%d") for i in range(3)]
    weekdays = get_weekday_names(3)
    hours = ["6-0", "12-6", "18-12", "24-18"]
    messages = []
    temp_description = {
        0: "نداریم",
        1: "کم",
        2: "زیاد",
        3: "بسیار شدید"
    }
    for day_index, day_date in enumerate(dates):
        for period_index, period_hour in enumerate(hours):
            index = day_index * len(hours) + period_index
            temp = frost_temp[index]
            wind = frost_wind[index]
            if temp >= 2:
                temp_desc = temp_description[temp]
                msg = f"روز {weekdays[day_index]} {day_date} در بازه ساعت {period_hour} خطر سرمازدگی {temp_desc} وجود دارد"
                messages.append(msg)
    return messages
    
def get_weekday_names(num: int) -> list[str]:
    "Will return the weekday name of the next `num` days, starting from today."
    today = jdatetime.date.today()
    weekday_names = [today.strftime('%A')]
    for i in range(1, num):
        next_day = today + jdatetime.timedelta(days=i)
        weekday_names.append(next_day.strftime('%A'))
    
    persian_weekday_names = []
    for weekday_name in weekday_names:
        if weekday_name == 'Saturday':
            persian_weekday_names.append('شنبه')
        elif weekday_name == 'Sunday':
            persian_weekday_names.append('یکشنبه')
        elif weekday_name == 'Monday':
            persian_weekday_names.append('دوشنبه')
        elif weekday_name == 'Tuesday':
            persian_weekday_names.append('سه شنبه')
        elif weekday_name == 'Wednesday':
            persian_weekday_names.append('چهارشنبه')
        elif weekday_name == 'Thursday':
            persian_weekday_names.append('پنجشنبه')
        elif weekday_name == 'Friday':
            persian_weekday_names.append('جمعه')
    
    return persian_weekday_names