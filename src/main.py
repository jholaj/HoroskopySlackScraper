import requests
from bs4 import BeautifulSoup

# Base URL of the website
BASE_URL = "https://www.horoskopy.cz"

# List of zodiac signs and their corresponding URLs
ZODIACS = [
    "beran", "lev", "strelec", "byk", "panna", "kozoroh",
    "blizenci", "vahy", "vodnar", "rak", "stir", "ryby"
]

PERCENTAGES = ["100%", "80%", "60%", "40%", "20%", "0%", "-20%", "-40%", "-60%", "-80%", "-100%"]


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


if __name__ == '__main__':
    raw_compatibility_data = fetch_zodiac_data(BASE_URL, ZODIACS)
    formatted_compatibility_data = format_compatibility_data(raw_compatibility_data, PERCENTAGES)
    for sign, data in formatted_compatibility_data.items():
        print(f"{sign.capitalize()}: {data}")
