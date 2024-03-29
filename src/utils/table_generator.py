from imgkit import from_string
from typing import List
from itertools import zip_longest
import re
import jdatetime as jdt
from .logger import logger

def weather_table(
    days: List[str],
    source: List[str],
    tmin: List[float],
    tmax: List[float],
    rh: List[float],
    wind_direction: List[float],
    wind_speed: List[float],
    rain_sum: List[float],
    snow_sum: list[float],
    precip_probability: List[float],
    direct_comparisons: int,
    output: str = "table.png",
) -> None:
    
    rows = len(days)
    style = """
<style type="text/css">
.tg  {border-collapse:collapse;border-color:#001d87;border-spacing:0; width: 100%;}
.tg td{background-color:#aabcfe;border-color:#aabcfe;border-style:solid;border-width:1px;color:#669;
  font-family:Arial, sans-serif;font-size:24px;font-weight:bold;overflow:hidden;padding:10px 5px;word-break:normal;}
table.tg tbody tr.t-content:nth-child(even) td{background: #fbfbff;}
.tg th{background-color:#f4f7ff;border-color:#aabcfe;border-style:solid;border-width:1px;color:#3f00e5;
  font-family:Arial, sans-serif;font-size:26px;font-weight:bold;overflow:hidden;padding:10px 5px;word-break:normal;}
tr.span-2 {border-bottom: #aabcfe;}
td.date-cell {border-bottom: #000;}
.tg .tg-qivn{border-color:inherit;font-family:Impact, Charcoal, sans-serif !important;text-align:center;vertical-align:top}
.tg .tg-s7u5{border-color:inherit;font-family:Impact, Charcoal, sans-serif !important;text-align:center;vertical-align:middle}
</style>"""

    header = """
<table class="tg">
<thead>
  <tr>
    <th class="tg-s7u5" rowspan="2">(٪) رطوبت</th>
    <th class="tg-qivn" colspan="3">بارش</th>
    <th class="tg-qivn" colspan="2">(Km/h) باد</th>
    <th class="tg-qivn" colspan="2">(&deg;C) دما</th>
    <th class="tg-s7u5" rowspan="2">منبع</th>
    <th class="tg-s7u5" rowspan="2">تاریخ</th>
  </tr>
  <tr>
    <th class="tg-qivn">(٪) احتمال</th>
    <th class="tg-qivn">باران<br>(م م)</th>
    <th class="tg-qivn">برف<br>(س م)</th>
    <th class="tg-qivn">سرعت</th>
    <th class="tg-qivn">جهت</th>
    <th class="tg-qivn">کمینه</th>
    <th class="tg-qivn">بیشینه</th>

  </tr>
</thead>
<tbody>"""

    ending = """
</tbody>
</table>
"""
    num_rows = len(tmin)

    row = """<tr class="t-content {}">
    <td class="tg-qivn">{}</td>
    <td class="tg-qivn">{}</td>
    <td class="tg-qivn">{}</td>
    <td class="tg-qivn">{}</td>
    <td class="tg-qivn">{}</td>
    <td class="tg-qivn">{}</td>
    <td class="tg-qivn">{}</td>
    <td class="tg-qivn">{}</td>
    <td class="tg-qivn">{}</td>"""
    
    date_cell_span_2 = """
    <td class="tg-qivn date-cell" style="vertical-align:middle;" rowspan="2">{}</td>
  </tr>
  """
    date_cell = """
    <td class="tg-qivn date-cell" style="vertical-align:middle;">{}</td>
  </tr>
  """
    rows = ""
    compare = 0
    for i in range(num_rows):
      if not all([tmin[i] == "--", tmax[i] == "--", rh[i] == "--", wind_direction[i] == "--", wind_speed[i] == "--", rain_sum[i] == "--", snow_sum[i] == "--", precip_probability[i] == "--"]):
        if compare < direct_comparisons:
          if i % 2 == 0:
            rows = rows + row.format('span-2', rh[i], precip_probability[i], rain_sum[i], snow_sum[i], wind_speed[i], wind_direction[i], tmin[i], tmax[i], source[i]) + date_cell_span_2.format(days[i])
            
            compare += 1
          else:
            rows = rows + row.format('', rh[i], precip_probability[i], rain_sum[i], snow_sum[i], wind_speed[i], wind_direction[i], tmin[i], tmax[i], source[i]) + "</tr>"
            
        else:
          rows = rows + row.format('', rh[i], precip_probability[i], rain_sum[i], snow_sum[i], wind_speed[i], wind_direction[i], tmin[i], tmax[i], source[i]) + date_cell.format(days[i])
          
    ## This is the old code that was used to generate the table without OpenMeteoWeather data
    # for i in range(num_rows):
    #   if not all([tmin[i] == "--", tmax[i] == "--", rh[i] == "--", wind_direction[i] == "--", wind_speed[i] == "--", rain_sum[i] == "--", rain_probability[i] == "--"]): 
    #     rows = rows + row.format(rh[i], rain_probability[i], rain_sum[i], wind_speed[i], wind_direction[i], tmin[i], tmax[i], source[i], days[i])

    html = style + header + rows + ending

    # Split the HTML into lines
    lines = html.split('\n')

    # Use a set to keep track of seen contents
    seen = set()

    # Initialize an empty string to store the new HTML
    new_html = ""

    for line in lines:
        # Extract the contents of the td element
        match = re.search(r'<td class="tg-qivn date-cell" style="vertical-align:middle;"( rowspan="2")?>(.*?)</td>', line)
        if match:
            contents = match.group(2)
            # If we've seen this content before and this td doesn't have rowspan="2", skip it
            if contents in seen and match.group(1) is None:
                continue
            # Otherwise, add it to the set of seen contents
            seen.add(contents)
        # Add the line to the new HTML
        new_html += line + '\n'

    # Now new_html contains the HTML with duplicate lines removed
    # with open("table.html", "w") as f:
    #     f.write(new_html)
    options = {"width": 1400}
    from_string(new_html, output, options=options)


def chilling_hours_table(
    methods: List[str],
    dates: List[str],
    hours: List[float],
    output: str = "table.png",
) -> None:
    if not len(methods) == len(dates) == len(hours):
        raise ValueError(f"""
All lists must be the same length.
methods: {len(methods)} {methods}
dates: {len(dates)} {dates}
hours: {len(hours)} {hours}
""")
    style = """
<style type="text/css">
.tg  {border-collapse:collapse;border-color:#aabcfe;border-spacing:0;width:100%}
.tg td{background-color:#e8edff;border-color:#aabcfe;border-style:solid;border-width:1px;color:#669;direction:rtl;
  font-family:Arial, sans-serif;font-size:25px;overflow:hidden;padding:10px 5px;word-break:normal;}
.tg td.chill-hour{font-weight:bold;}
.tg th{background-color:#b9c9fe;border-color:#aabcfe;border-style:solid;border-width:1px;color:#039;direction:rtl;
  font-family:Arial, sans-serif;font-size:25px;font-weight:normal;overflow:hidden;padding:10px 5px;word-break:normal;}
.tg .tg-qivn{border-color:inherit;font-family:Impact, Charcoal, sans-serif !important;text-align:center;}
</style>
"""

    header = """
<table class="tg">
<thead>
  <tr>
    <th class="tg-qivn">نیاز سرمایی تامین شده</th>
    <th class="tg-qivn">تاریخ محاسبه</th>
    <th class="tg-qivn">روش</th>
  </tr>
</thead>
<tbody>"""

    ending = """
</tbody>
</table>
"""
    num_rows = len(methods)

    row = """<tr>
    <td class="tg-qivn chill-hour">{}</td>
    <td class="tg-qivn">{}</td>
    <td class="tg-qivn method">{}</td>
  </tr>"""

    rows = ""
    for i in range(num_rows):
        rows = rows + row.format(hours[i], dates[i], methods[i])

    html = style + header + rows + ending

    options = {"width": 600}
    from_string(html, output, options=options)

def remaining_chilling_hours_table(
    pesteh_types: List[str],
    complete_hours: List[float],
    hours_difference: List[float],
    hours: int,
    output: str = "table.png",
) -> None:
    date = (jdt.date.today() - jdt.timedelta(days=1 )).strftime("%Y/%m/%d")
    style = """
<style type="text/css">
.tg  {border-collapse:collapse;border-spacing:0;width:100%}
.tg td{border-style:solid;border-width:3px;direction:rtl;
  font-family:Arial, sans-serif;font-size:25px;overflow:hidden;padding:10px 5px;word-break:normal;}
.tg td.left-column{font-weight:bold; width:20%}
.tg td.middle-column{font-weight:bold; width: 30%}
.tg td.right-column{width:100%; text-align:center;}
.tg th{border-style:solid;border-width:3px;direction:rtl;
  font-family:Arial, sans-serif;font-size:25px;font-weight:normal;overflow:hidden;padding:10px 5px;word-break:normal;}
.tg .tg-qivn{border-color:inherit;font-family:Impact, Charcoal, sans-serif !important;text-align:center;}
</style>
"""

    header = """
<table class="tg">
<thead>
    <tr>
          <td style="background-color:chartreuse">نیاز سرمایی تامین شده</td>
          <td rowspan="2" colspan="2" style="text-align: center !important; overflow:visible">
    سرمای تامین شده باغ شما تا تاریخ {} بر حسب ساعت: {}
    </td>
    </tr>
    <tr>
      <td style="background-color:chocolate">نیاز سرمایی تامین نشده</td>
    </tr>
  <tr>
    <th class="tg-qivn">باقیمانده نیاز سرمایی<br>(ساعت)</th>
    <th class="tg-qivn">حد نیاز سرمایی <br>مدل ساعت سرمایی صفر تا هفت</th>
    <th class="tg-qivn">رقم پسته</th>
  </tr>
</thead>
<tbody>
""".format(date, hours)

    ending = """
</tbody>
</table>
"""
    num_rows = len(pesteh_types)

    row_red = """<tr>
      <td class="tg-qivn left-column" style="background-color:chocolate">{}</td>
      <td class="tg-qivn middle-column">{}</td>
      <td class="right-column">{}</td>
    </tr>"""
  
    row_green = """<tr>
      <td class="tg-qivn left-column" style="background-color:chartreuse">{}</td>
      <td class="tg-qivn middle-column">{}</td>
      <td class="right-column">{}</td>
    </tr>"""

    rows = ""
    for i in range(num_rows):
      if hours_difference[i] < 0:
        rows = rows + row_red.format(hours_difference[i], complete_hours[i], pesteh_types[i])
      else:
        rows = rows + row_green.format(hours_difference[i], complete_hours[i], pesteh_types[i])
    
    html = style + header + rows + ending
    # with open("table2.html", "w") as file:
    #   file.write(html)
    options = {"width": 1600}
    from_string(html, output, options=options)

def spring_frost_table(frost_advice: zip, messages: list[str], output = "frost-table.png"):
  head = """
  <!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Document</title>
      <style>
        * {
          font-family:Impact, Charcoal, sans-serif !important;
        }
        table { 
          width: 100%;
          border-collapse: collapse;
        }
        th, td {
          border: 1.5px solid black;
          text-align: center;
        }
        .th-border {
          border-left: 4px solid black;
        }
        .table-green, .table-green > th, .table-green > td {
            background-color: #92f496;
        }
        .table-yellow, .table-yellow > th, .table-yellow > td {
            background-color: #fff178 ;
        }
        .table-orange, .table-orange > th, .table-orange > td {
            background-color: #ffc268 ;
        }
        .table-red, .table-red > th, .table-red > td {
            background-color: #ff8178 ;
        }
        .messages {
          padding-inline-start: 25px;
        }
        .message {
          padding: 5px;
          font-size: larger;
        }
      </style>
    </head>
  """
  thead = """
    <body>
      <table class="table text-center">
        <thead>
          <tr>
            <th rowspan="2" class="text-center th-border">ساعت</th>
            <th colspan="2" class="text-center th-border">0-6</th>
            <th colspan="2" class="text-center th-border">6-12</th>
            <th colspan="2" class="text-center th-border">12-18</th>
            <th colspan="2" class="text-center th-border">18-24</th>
          </tr>
          <tr>
            <th class="text-center">احتمال </br> سرمازدگی</th>
            <th class="th-border text-center">وضعیت </br> باد</th>
            <th class="text-center">احتمال </br> سرمازدگی</th>
            <th class="th-border text-center">وضعیت </br> باد</th>
            <th class="text-center">احتمال </br> سرمازدگی</th>
            <th class="th-border text-center">وضعیت </br> باد</th>
            <th class="text-center">احتمال </br> سرمازدگی</th>
            <th class="th-border text-center">وضعیت </br> باد</th>
          </tr>
        </thead>
          <tbody>
  """
  row = """
  <tr>
  <th scope="row" class="th-border">{{ label }}</th>
  <td {% if temp1 == 0 %} class="table-green" {% elif temp1 == 1 %} class="table-yellow" {% elif temp1 == 2 %} class="table-orange" {% elif temp1 == 3 %} class="table-red" {% endif %}>{% if temp1 == 0 %} نداریم {% elif temp1 == 1 %} کم {% elif temp1 == 2 %} زیاد {% elif temp1 == 3 %} بسیار شدید {% endif %}</td>
  <td class="th-border">{% if wind1 == 0 %} مناسب {% elif wind1 == 1 %} با احتیاط {% elif wind1 == 2 %} نامناسب {% endif %}</td>
  <td {% if temp2 == 0 %} class="table-green" {% elif temp2 == 1 %} class="table-yellow" {% elif temp2 == 2 %} class="table-orange" {% elif temp2 == 3 %} class="table-red" {% endif %}>{% if temp2 == 0 %} نداریم {% elif temp2 == 1 %} کم {% elif temp2 == 2 %} زیاد {% elif temp2 == 3 %} بسیار شدید {% endif %}</td>
  <td class="th-border">{% if wind2 == 0 %} مناسب {% elif wind2 == 1 %} با احتیاط {% elif wind2 == 2 %} نامناسب {% endif %}</td>
  <td {% if temp3 == 0 %} class="table-green" {% elif temp3 == 1 %} class="table-yellow" {% elif temp3 == 2 %} class="table-orange" {% elif temp3 == 3 %} class="table-red" {% endif %}>{% if temp3 == 0 %} نداریم {% elif temp3 == 1 %} کم {% elif temp3 == 2 %} زیاد {% elif temp3 == 3 %} بسیار شدید {% endif %}</td>
  <td class="th-border">{% if wind3 == 0 %} مناسب {% elif wind3 == 1 %} با احتیاط {% elif wind3 == 2 %} نامناسب {% endif %}</td>
  <td {% if temp4 == 0 %} class="table-green" {% elif temp4 == 1 %} class="table-yellow" {% elif temp4 == 2 %} class="table-orange" {% elif temp4 == 3 %} class="table-red" {% endif %}>{% if temp4 == 0 %} نداریم {% elif temp4 == 1 %} کم {% elif temp4 == 2 %} زیاد {% elif temp4 == 3 %} بسیار شدید {% endif %}</td>
  <td class="th-border">{% if wind4 == 0 %} مناسب {% elif wind4 == 1 %} با احتیاط {% elif wind4 == 2 %} نامناسب {% endif %}</td>
  </tr>
  """
  end = """
          </tbody>
      </table>
      <div class="messages">{}</div>
    </body>
  </html>
  """
  rows = ""
  for label, temp1, wind1, temp2, wind2, temp3, wind3, temp4, wind4 in frost_advice:
    row = "<tr>"
    row += f"<th scope='row' class='th-border'>{label}</th>"
    row += "<td class='table-green'>نداریم</td>" if temp1 == 0 else \
           "<td class='table-yellow'>کم</td>" if temp1 == 1 else \
           "<td class='table-orange'>زیاد</td>" if temp1 == 2 else \
           "<td class='table-red'>بسیار شدید</td>"
    row += "<td class='th-border'>--</td>" if temp1 == 0 else \
           "<td class='th-border'>مناسب</td>" if wind1 == 0 else \
           "<td class='th-border'>با احتیاط</td>" if wind1 == 1 else \
           "<td class='th-border'>نامناسب</td>"
    row += "<td class='table-green'>نداریم</td>" if temp2 == 0 else \
           "<td class='table-yellow'>کم</td>" if temp2 == 1 else \
           "<td class='table-orange'>زیاد</td>" if temp2 == 2 else \
           "<td class='table-red'>بسیار شدید</td>"
    row += "<td class='th-border'>--</td>" if temp2 == 0 else \
           "<td class='th-border'>مناسب</td>" if wind2 == 0 else \
           "<td class='th-border'>با احتیاط</td>" if wind2 == 1 else \
           "<td class='th-border'>نامناسب</td>"
    row += "<td class='table-green'>نداریم</td>" if temp3 == 0 else \
           "<td class='table-yellow'>کم</td>" if temp3 == 1 else \
           "<td class='table-orange'>زیاد</td>" if temp3 == 2 else \
           "<td class='table-red'>بسیار شدید</td>"
    row += "<td class='th-border'>--</td>" if temp3 == 0 else \
           "<td class='th-border'>مناسب</td>" if wind3 == 0 else \
           "<td class='th-border'>با احتیاط</td>" if wind3 == 1 else \
           "<td class='th-border'>نامناسب</td>"
    row += "<td class='table-green'>نداریم</td>" if temp4 == 0 else \
           "<td class='table-yellow'>کم</td>" if temp4 == 1 else \
           "<td class='table-orange'>زیاد</td>" if temp4 == 2 else \
           "<td class='table-red'>بسیار شدید</td>"
    row += "<td class='th-border'>--</td>" if temp4 == 0 else \
           "<td class='th-border'>مناسب</td>" if wind4 == 0 else \
           "<td class='th-border'>با احتیاط</td>" if wind4 == 1 else \
           "<td class='th-border'>نامناسب</td>"
    row += "</tr>"
    rows = rows + row 
  # if messages: 
  #   message_list = [f"<p class='message'>{message}</p>" for message in messages]
  #   html = head + thead + rows + end.format("\n".join(message_list))
  # else:
  html = head + thead + rows + end.format("")
  # with open("frost-table.html", "w") as file:
  #     file.write(html)
  options = {}
  from_string(html, output, options=options)