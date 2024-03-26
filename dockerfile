FROM python:3.10.6-slim

WORKDIR /sms

COPY requirements.txt .

RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT [ "python3", "src/main.py" ]