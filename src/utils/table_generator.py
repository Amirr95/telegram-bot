from imgkit import from_string
from typing import List
from itertools import zip_longest
import re
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
    rain_probability: List[float],
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
.tg .tg-qivn{border-color:inherit;font-family:Impact, Charcoal, sans-serif !important;text-align:center;vertical-align:top}
.tg .tg-s7u5{border-color:inherit;font-family:Impact, Charcoal, sans-serif !important;text-align:center;vertical-align:middle}
</style>"""

    header = """
<table class="tg">
<thead>
  <tr>
    <th class="tg-qivn">رطوبت</th>
    <th class="tg-qivn" colspan="2">بارش</th>
    <th class="tg-qivn" colspan="2">باد</th>
    <th class="tg-qivn" colspan="2">(&deg;C) دما</th>
    <th class="tg-s7u5" rowspan="2">منبع</th>
    <th class="tg-s7u5" rowspan="2">تاریخ</th>
  </tr>
  <tr>
    <th class="tg-qivn">درصد</th>
    <th class="tg-qivn">احتمال</th>
    <th class="tg-qivn">م م</th>
    <th class="tg-qivn">Km/h</th>
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

    row = """<tr class="t-content">
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
      if not all([tmin[i] == "--", tmax[i] == "--", rh[i] == "--", wind_direction[i] == "--", wind_speed[i] == "--", rain_sum[i] == "--", rain_probability[i] == "--"]):
        if compare < direct_comparisons:
          if i % 2 == 0:
            rows = rows + row.format(rh[i], rain_probability[i], rain_sum[i], wind_speed[i], wind_direction[i], tmin[i], tmax[i], source[i]) + date_cell_span_2.format(days[i])
            
            compare += 1
          else:
            rows = rows + row.format(rh[i], rain_probability[i], rain_sum[i], wind_speed[i], wind_direction[i], tmin[i], tmax[i], source[i]) + "</tr>"
            
        else:
          rows = rows + row.format(rh[i], rain_probability[i], rain_sum[i], wind_speed[i], wind_direction[i], tmin[i], tmax[i], source[i]) + date_cell.format(days[i])
          
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

    options = {"width": 1200}
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
