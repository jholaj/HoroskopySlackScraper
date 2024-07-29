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
import imgkit

load_dotenv()

BASE_URL = "https://www.horoskopy.cz"

IMG_PATH = '/tmp/horoscope_table.png'

ZODIACS = [
    "beran", "lev", "strelec", "byk", "panna", "kozoroh",
    "blizenci", "vahy", "vodnar", "rak", "stir", "ryby"
]

PERCENTAGES = ["100%", "80%", "60%", "40%", "20%", "0%", "-20%", "-40%", "-60%", "-80%", "-100%"]

SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')
SLACK_APP_TOKEN = os.getenv('SLACK_APP_TOKEN')
SLACK_CHANNEL_ID = os.getenv('SLACK_CHANNEL_ID')

app = App(token=SLACK_BOT_TOKEN)
client = WebClient(token=SLACK_BOT_TOKEN)


def load_names_zodiacs(filename):
    """
    Load zodiac names from a JSON file.
    """
    with open(filename, 'r', encoding="utf-8") as file:
        return json.load(file)


NAMES_ZODIACS = load_names_zodiacs('../names_zodiacs.json')


def fetch_zodiac_data(base_url, zodiac_signs):
    """
    Fetch zodiac compatibility data from the given URL.
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
    Format zodiac compatibility data into a DataFrame.
    """
    df_data = {"Percent": percentages}

    for sign, values in horoscope_data.items():
        formatted_values = []
        for value in values:
            parts = value.split(',')
            names = []
            for part in parts:
                part = part.strip().lower()
                if part in names_zodiacs and names_zodiacs[part]:
                    names.append(", ".join(names_zodiacs[part]))
            formatted_values.append(", ".join(names))
        df_data[sign.capitalize()] = formatted_values

    df = pd.DataFrame(df_data)
    df.set_index("Percent", inplace=True)

    return df


def dataframe_to_html(df):
    """
    Converts a DataFrame to an HTML table using custom HTML and CSS styling.
    """
    # Create the HTML table structure manually
    html = '<table class="dataframe">'

    # Header row
    html += '<tr>'
    html += '<th class="percent-header"></th>'  # Add Percent to the first row with special class
    for column in df.columns:
        html += f'<th>{column}</th>'
    html += '</tr>'

    # Data rows
    for index, row in df.iterrows():
        html += '<tr>'
        html += f'<td class="percent-cell">{index}</td>'  # Percent column with special class
        for value in row:
            html += f'<td>{value}</td>'
        html += '</tr>'

    html += '</table>'

    # Define CSS for table styling
    css = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Comfortaa:wght@400;700&display=swap');

        body {
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            background-color: #2C2A63;
        }
        .dataframe {
            border-collapse: separate;
            border-spacing: 0;
            font-family: 'Comfortaa', sans-serif;
            background-color: #2C2A63;
            color: white;
            border-radius: 20px;
            overflow: hidden;
            max-width: 100%;
            margin: auto;
        }
        .dataframe th, .dataframe td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
            font-size: 14px;
            font-weight: 600;
            max-width: 150px;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .dataframe th {
            background-color: #181A1B;
            color: white;
            font-weight: bold;
            font-size: 16px;
        }
        .dataframe .percent-header, .dataframe .percent-cell {
            background-color: #181A1B;
            color: white;
            font-weight: bold;
            font-size: 16px;
        }
        .dataframe tr:first-child th:first-child {
            border-top-left-radius: 20px;
        }
        .dataframe tr:first-child th:last-child {
            border-top-right-radius: 20px;
        }
        .dataframe tr:last-child td:first-child {
            border-bottom-left-radius: 20px;
        }
        .dataframe tr:last-child td:last-child {
            border-bottom-right-radius: 20px;
        }
    </style>
    """

    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        {css}
    </head>
    <body>
        {html}
    </body>
    </html>
    """

    return full_html


def html_to_image(html_content, output_path):
    """
    Convert HTML content to an image file.
    """
    options = {
        "transparent": "",
        'format': 'png',
        'encoding': "UTF-8",
        'width': 1400,
        'quality': 100,
    }
    imgkit.from_string(html_content, output_path, options=options)


def send_message_and_table(channel_id, summary, image_path):
    """
    Send a message and an image file to Slack.
    """
    try:
        # Intro message
        intro_message = (
            f">*Vztah znamení k ostatním znamení ke dni: _{time.strftime('%d.%m.%Y')}_*\n"
            f"{summary}\n"
        )
        response_message = client.chat_postMessage(
            channel=channel_id,
            text=intro_message
        )
        print(f"Message sent to {channel_id}: {response_message['ts']}")

        # Image upload
        response_file = client.files_upload_v2(
            channels=channel_id,
            file=image_path,
            title="Horoskopy",
        )
        print(f"Image sent to {channel_id}: {response_file['file']['id']}")

    except SlackApiError as e:
        print(f"Error sending message or image to Slack: {e.response['error']}")


def _remove_diacritics(text):
    """
    Remove diacritics from a given text.
    """
    return ''.join(c for c in unicodedata.normalize('NFD', text)
                   if unicodedata.category(c) != 'Mn')


def generate_relationship_summary(df, names_zodiacs, percentage, relationship_type):
    """
    Generate a summary of relationships based on compatibility percentage.
    """
    relationships_dict = {}

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

    unique_relationships = set()
    for name, related in relationships_dict.items():
        for person in related:
            relationship = tuple(sorted([name, person]))
            unique_relationships.add(relationship)

    aggregated_relationships = {}
    for relationship in unique_relationships:
        key = relationship[0]
        if key not in aggregated_relationships:
            aggregated_relationships[key] = set()
        aggregated_relationships[key].update(relationship[1:])

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
    Fetch, format, and send daily horoscope data.
    """
    raw_compatibility_data = fetch_zodiac_data(BASE_URL, ZODIACS)
    formatted_compatibility_data = format_compatibility_data(raw_compatibility_data, PERCENTAGES, NAMES_ZODIACS)

    friends_summary = generate_relationship_summary(formatted_compatibility_data, NAMES_ZODIACS, 100, "kamarád")
    enemies_summary = generate_relationship_summary(formatted_compatibility_data, NAMES_ZODIACS, -100, "nepřítel")

    combined_summary = f"Kamarádi:\n{friends_summary}\n\nNepřátelé:\n{enemies_summary}"

    html_content = dataframe_to_html(formatted_compatibility_data)
    html_to_image(html_content, IMG_PATH)

    send_message_and_table(SLACK_CHANNEL_ID, combined_summary, IMG_PATH)


if __name__ == "__main__":
    send_daily_horoscope()
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.connect()
