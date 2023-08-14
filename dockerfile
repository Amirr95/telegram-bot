FROM python:3.10.6-slim

WORKDIR /sheet-export

COPY requirements.txt .

RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

CMD [ "python3", "sync.py" ] python3 -u main.py