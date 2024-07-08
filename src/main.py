import os
import time
import requests
from bs4 import BeautifulSoup
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

load_dotenv()


# Base URL of the website
BASE_URL = "https://www.horoskopy.cz"

# List of zodiac signs and their corresponding URLs
ZODIACS = [
    "beran", "lev", "strelec", "byk", "panna", "kozoroh",
    "blizenci", "vahy", "vodnar", "rak", "stir", "ryby"
]

PERCENTAGES = ["100%", "80%", "60%", "40%", "20%", "0%", "-20%", "-40%", "-60%", "-80%", "-100%"]

# Load tokens from environment variables for security
SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')  # xoxb- token
SLACK_APP_TOKEN = os.getenv('SLACK_APP_TOKEN')  # xapp- token
SLACK_CHANNEL_ID = os.getenv('SLACK_CHANNEL_ID')  # slack channel ID

# Initialize a Bolt for Python app with the bot token
app = App(token=SLACK_BOT_TOKEN)


def fetch_zodiac_data(base_url, zodiac_signs):
    """
    Fetches compatibility data for each zodiac sign from the given base URL.

    This function visits each zodiac sign's page on the provided base URL, scrapes the compatibility data
    from the 'teplomer' div, and stores the data in a dictionary. Each key in the dictionary is a zodiac sign,
    and its value is a list of compatibility data strings. Empty list items in the div are represented as
    single spaces.
    """
    horoscope_data = {}

    for sign in zodiac_signs:
        url = f"{base_url}/{sign}"
        response = requests.get(url, timeout=5)
        soup = BeautifulSoup(response.content, 'html.parser')

        teplomer_div = soup.find('div', id='teplomer', attrs={'data-dot': 'd_vztah_k_ostatnim'})
        if teplomer_div:
            values = []
            for li in teplomer_div.find_all('li'):
                text = li.get_text(strip=True)
                values.append(text if text else " ")
            horoscope_data[sign] = values

    return horoscope_data


def format_compatibility_data(horoscope_data, percentages):
    """
    Formats the horoscope compatibility data to be more readable.

    This function takes in the raw horoscope data and the corresponding percentages, and
    outputs a formatted version of the data.
    """
    formatted_data = {}

    for sign, values in horoscope_data.items():
        formatted_values = [f"{percent}: {value}" for percent, value in zip(percentages, values)]
        formatted_data[sign] = formatted_values

    return formatted_data


def send_to_slack(channel_id, message):
    """
    Sends a formatted message to a Slack channel.

    Parameters:
    - channel_id (str): The ID of the Slack channel where the message will be sent.
    - message (str): The message to send to Slack.
    """
    try:
        response = app.client.chat_postMessage(channel=channel_id, text=message)
        print(f"Message sent to {channel_id}: {response['message']['text']}")
    except SlackApiError as e:
        print(f"Error sending message to Slack: {e.response['error']}")


def send_daily_horoscope():
    """
    Fetches and sends the daily horoscope data to the Slack channel.
    """
    raw_compatibility_data = fetch_zodiac_data(BASE_URL, ZODIACS)
    formatted_compatibility_data = format_compatibility_data(raw_compatibility_data, PERCENTAGES)

    intro_message = f"*VZTAH ZNAMENÍ K OSTATNÍM ZNAMENÍ KE DNI: _{time.strftime('%d.%m.%Y').upper()}_*\n\n"

    # Prepare the message to send
    message = intro_message

    for sign, data in formatted_compatibility_data.items():
        message += f"\n*_>{sign.capitalize().upper()}_*\n"
        message += "\n".join(data) + "\n\n"

    # Send the complete message to Slack
    send_to_slack(SLACK_CHANNEL_ID, message)

if __name__ == "__main__":
    send_daily_horoscope()

    # Run the Slack bot using Socket Mode
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.connect()
