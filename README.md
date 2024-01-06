# Abaad Telegram Bot

Abaad is a telegram bot designed to assist farmers. It allows farmers to add their farms and receive weather predictions, recommendations, warnings, and more, providing a comprehensive management tool for modern agriculture.

## Project Structure

- [`add_conv.py`](./src/utils/add_conv.py): A <a href="https://docs.python-telegram-bot.org/en/stable/telegram.ext.conversationhandler.html">Conversation Handler</a> for adding new farms.
- [`edit_conv.py`](./src/utils/edit_conv.py): A Conversation Handler for editing farms.
- [`view_conv.py`](./src/utils/view_conv.py): A Conversation Handler for viewing farms.
- [`delete_conv.py`](./src/utils/delete_conv.py): A Conversation Handler for deleting farms.
- [`register_conv.py`](./src/utils/register_conv.py): A Conversation Handler for registering new users.
- [`harvest_conv.py`](./src/utils/harvest_conv.py): A Conversation Handler for receiving pre/post harvest advice regarding a farm.
- [`weather_conv.py`](./src/utils/weather_conv.py): A Conversation Handler for receiving weather predictions regarding a farm.
- [`automn_conv.py`](./src/utils/automn_conv.py): A Conversation Handler to set the automn date of a farm, used in calculating chilling hours requirements.
- [`admin.py`](./src/utils/admin.py): A few <a href="https://docs.python-telegram-bot.org/en/stable/telegram.ext.commandhandler.html">Command Handlers</a> for admin specific commands to send message to users, set user farm locations, see bot stats.
- [`regular_jobs.py`](./src/utils/regular_jobs.py): Some pre scheduled jobs that are run regularly.
- [`keyboards.py`](./src/utils/keyboards.py): The keyboards used in the bot are defined here.
- [`table_generator.py`](./src/utils/table_generator.py): Some helper functions to generate `PNG` tables used to give weather predictions. The bot uses the `wkhtmltoimage` package to convert HTML tables to `PNG` images.  
- [`sms_funcs.py`](./src/utils/sms_funcs.py): Functions used to send the user an sms message if certain conditions are met.

## Running the Bot
### Requirements
- Python: 3.10^
- MongoDB: 6.0^
- wkhtmltoimage: ```sudo apt install -y wkhtmltopdf```

### Database Setup

This project uses MongoDB as its database. The database helper functions are accessed from the `Database` class in [`database.py`](./src/database.py). You need to set an environment variable called `MONGODB_URI` before running the code.

#### Database Schema
- `botCollection`: This collection stores data related to the bot, such as admin users list, user activity logs and number of users.
- `userCollection`: This collection stores user data, including username, phone-number, first-seen timestamp, the list of farms belonging to the user, etc.
- `dialogCollection`: This collection stores all messages sent to the user. 


### Setting up the Telegram Bot Token

To use the Abaad Telegram bot, you need to set an environment variable called `AGRIWEATHBOT_TOKEN` with a token obtained from <a href="https://t.me/BotFather">BotFather</a>. BotFather is a bot provided by Telegram that allows you to create and manage your own bots.

1. Open Telegram and search for BotFather.
2. Start a chat with BotFather and follow the instructions to create a new bot.
3. Once the bot is created, BotFather will provide you with a token. Copy this token.
4. Set the `AGRIWEATHBOT_TOKEN` environment variable in your system or in your deployment environment, and assign it the value of the token obtained from BotFather.

With the `AGRIWEATHBOT_TOKEN` environment variable set, the Abaad Telegram bot will be able to authenticate and interact with the Telegram API.

### Running the Project
Clone the project and install the required packages:

```bash
git clone <https://github.com/Amirr95/telegram-bot>
cd <telegram-bot>
pip install -r requirements.txt
python3 src/main.py
``` 

Now you can visit your own bot in telegram and see it in action.

## Features

- Add and manage multiple farms
- Receive weather predictions specific to each farm's location
- Get recommendations for improving farm productivity
- Receive warnings about potential issues

We welcome contributions that can help us improve this application and add more features. Please create a new branch before submitting a pull requests. For more information on telegram bots and the PTB library used in this project, visit this <a href="https://github.com/python-telegram-bot/python-telegram-bot/wiki/Introduction-to-the-API">wiki</a>.