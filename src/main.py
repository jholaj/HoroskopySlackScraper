import os
import json
import time
import unicodedata
import requests
from bs4 import BeautifulSoup
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.errors import SlackApiError
from slack_sdk import WebClient
from dotenv import load_dotenv
import pandas as pd
from tabulate import tabulate

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
client = WebClient(token=SLACK_BOT_TOKEN)


# Load zodiac names from a JSON file
def load_names_zodiacs(filename):
    with open(filename, 'r') as file:
        return json.load(file)


# Names and their corresponding zodiac signs
NAMES_ZODIACS = load_names_zodiacs('../names_zodiacs.json')


def fetch_zodiac_data(base_url, zodiac_signs):
    """
    Fetches compatibility data for each zodiac sign from the given base URL.
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


def format_compatibility_data(horoscope_data, percentages, names_zodiacs):
    """
    Formats the horoscope compatibility data into a DataFrame.
    """
    # Create a dictionary to hold the DataFrame data
    df_data = {"Percent": percentages}
    
    for sign, values in horoscope_data.items():
        formatted_values = []
        for value in values:
            # Split the value by commas to handle multiple signs
            parts = value.split(',')
            names = []
            for part in parts:
                part = part.strip().lower()
                if part in names_zodiacs and names_zodiacs[part]:
                    names.append(",".join(names_zodiacs[part]))
            formatted_values.append(",".join(names))
        df_data[sign.capitalize()] = formatted_values

    # Create DataFrame
    df = pd.DataFrame(df_data)
    df.set_index("Percent", inplace=True)

    return df

def split_dataframe(df):
    """
    Splits the DataFrame into two parts for better readability in Slack.
    """
    num_columns = len(df.columns)
    split_point = num_columns // 2
    df1 = df.iloc[:, :split_point]
    df2 = df.iloc[:, split_point:]
    return df1, df2


def format_table_for_slack(df):
    """
    Formats the DataFrame into a tabulated string for Slack with dashed lines under headers.
    """
    # Convert DataFrame to string with tabulate using 'plain' format
    table_str = tabulate(df, headers='keys', tablefmt='simple')

    return table_str


def send_intro_message(channel_id, summary):
    try:
        intro_message = (
            f">*Vztah znamení k ostatním znamení ke dni: _{time.strftime('%d.%m.%Y')}_*\n"
            f"{summary}\n"
        )
        response = client.chat_postMessage(
            channel=channel_id,
            text=intro_message
        )
        print(f"Message sent to {channel_id}: {response['ts']}")

    except SlackApiError as e:
        print(f"Error sending message to Slack: {e.response['error']}")


def send_table_to_slack(channel_id, table_str):
    """
    Sends a tabulated string to a Slack channel.
    """
    try:
        # Split table into multiple messages if necessary
        message_chunks = [table_str[i:i + 4000] for i in range(0, len(table_str), 4000)]

        for chunk in message_chunks:
            response = client.chat_postMessage(
                channel=channel_id,
                text=f"\n```\n{chunk}\n```"
            )
            print(f"Message sent to {channel_id}: {response['ts']}")

    except SlackApiError as e:
        print(f"Error sending message to Slack: {e.response['error']}")


def _remove_diacritics(text):
    """
    Removes diacritics (accents) from the text.
    """
    return ''.join(c for c in unicodedata.normalize('NFD', text)
                   if unicodedata.category(c) != 'Mn')


def generate_relationship_summary(df, names_zodiacs, percentage, relationship_type):
    """
    Generates a summary of relationships based on specified compatibility percentage.

    :param df: DataFrame containing compatibility data
    :param names_zodiacs: Dictionary mapping zodiac signs to names
    :param percentage: Compatibility percentage to look for (100 or -100)
    :param relationship_type: Type of relationship ("kamarád" or "nepřítel")
    :return: Summary of relationships
    """
    relationships_dict = {}

    # Iterate over each zodiac sign and corresponding names
    for zodiac, names in names_zodiacs.items():
        zodiac_no_diacritics = _remove_diacritics(zodiac).capitalize()
        if zodiac_no_diacritics in df.columns:
            column_data = df[zodiac_no_diacritics]
            for name in names:
                for percent, related_names in column_data.items():
                    if int(percent[:-1]) == percentage:
                        related_names_list = [n.strip() for n in related_names.split(',') if n]
                        if name in related_names_list:
                            related_names_list.remove(name)
                        if related_names_list:
                            if name not in relationships_dict:
                                relationships_dict[name] = set()
                            relationships_dict[name].update(related_names_list)

    # Create a set of unique relationships
    unique_relationships = set()
    for name, related in relationships_dict.items():
        for person in related:
            relationship = tuple(sorted([name, person]))
            unique_relationships.add(relationship)

    # Aggregate relationships
    aggregated_relationships = {}
    for relationship in unique_relationships:
        key = relationship[0]
        if key not in aggregated_relationships:
            aggregated_relationships[key] = set()
        aggregated_relationships[key].add(relationship[1])

    # Create summary lines
    summary_lines = []
    for name, related in aggregated_relationships.items():
        related_string = ', '.join(sorted(related))
        if relationship_type == "nepřítel":
            summary_lines.append(f"- {name} je s {related_string} dnes {relationship_type}!")
        else:
            summary_lines.append(f"+ {name} je s {related_string} dnes {relationship_type}!")

    return "\n".join(summary_lines)


def send_daily_horoscope():
    """
    Fetches and sends the daily horoscope data to the Slack channel.
    """
    raw_compatibility_data = fetch_zodiac_data(BASE_URL, ZODIACS)
    formatted_compatibility_data = format_compatibility_data(raw_compatibility_data, PERCENTAGES, NAMES_ZODIACS)

    # Split DataFrame into two parts for better readability
    df1, df2 = split_dataframe(formatted_compatibility_data)

    # Generate summaries for friends and enemies
    friends_summary = generate_relationship_summary(formatted_compatibility_data, NAMES_ZODIACS, 100, "kamarád")
    enemies_summary = generate_relationship_summary(formatted_compatibility_data, NAMES_ZODIACS, -100, "nepřítel")

    # Combine summaries
    combined_summary = f"Kamarádi:\n{friends_summary}\n\nNepřátelé:\n{enemies_summary}"

    # Send intro message with summaries
    send_intro_message(SLACK_CHANNEL_ID, combined_summary)

    # Format DataFrame parts into tabulated strings
    table_str1 = format_table_for_slack(df1)
    table_str2 = format_table_for_slack(df2)

    # Send the tabulated strings to Slack
    send_table_to_slack(SLACK_CHANNEL_ID, table_str1)
    send_table_to_slack(SLACK_CHANNEL_ID, table_str2)

if __name__ == "__main__":
    send_daily_horoscope()

    # Run the Slack bot using Socket Mode
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.connect()
