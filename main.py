"""
Main file for the Sam the Scraper bot
~~~~~~~~~~~~~~~~~~~

Responsible for extracting JSON program data,
initiating all relevant classes and connecting them together

:copyright: (c) 2025-present IFI-PROGSYS
:license: MIT, see LICENSE for more details.

"""

import json
import discord
from sam import Sam
from discord_gateway import DiscordGateway

DATA_JSON_PATH = "./secrets.json"


def extract_metadata():
    """
    Read program metadata from the JSON file at DATA_JSON_PATH and return
    the three expected fields.

    The function opens the file at the module-level constant DATA_JSON_PATH
    using UTF-8 encoding, parses it as JSON, and returns a 3-tuple with the
    values of the following keys (in this order):

    - "organization_name": the human-readable name of the organization (str or None)
    - "channel_id": the channel identifier used by the program (str/int or None)
    - "discord_api_key": the API key/secret used for Discord integration (str or None)

    Returns
    -------
    tuple:
        (organization_name, channel_id, api_key) where each item will be the
        value from the JSON file or None if the key is not present.

    Raises
    ------
    FileNotFoundError
        If the file at DATA_JSON_PATH does not exist.
    json.JSONDecodeError
        If the file contents are not valid JSON.
    OSError
        For other I/O related errors when opening/reading the file.
    """

    with open(DATA_JSON_PATH, "r", encoding="utf-8") as file:
        external_metadata = json.load(file)

    organization_name = external_metadata.get("organization_name")
    channel_id = external_metadata.get("channel_id")
    api_key = external_metadata.get("discord_api_key")
    return organization_name, channel_id, api_key


def main():
    """
    main function of the main file. Calls extract_metadata(), handles
    the returned program metadata, initiates Sam and DiscordGateway, and
    connects the two together.
    """

    print("Sam:Main - Extracting metadata from secrets.json")
    organization_name, channel_id, api_key = extract_metadata()
    print(
        "Sam:Main - Found metadata:\n"
        + f"\tOrg name: {organization_name}\n"
        + f"\tChannel ID: {channel_id}\n"
        + "\tAPI KEY LENGTH: {len(API_KEY)}"
    )

    channel_id = int(channel_id)
    intents = discord.Intents.default()
    print("Sam:Main - Set Discord intentions OK")
    sam = Sam(organization_name)
    print("Sam:Main - Started Sam OK")
    client = DiscordGateway(sam=sam, channel_id=channel_id, intents=intents)
    print("Sam:Main - Started DiscordGateway OK")
    print("Sam:Main - Running Discord bot client...")
    client.run(api_key)


if __name__ == "__main__":
    print("Sam:Main - Starting up... Welcome!")
    main()
