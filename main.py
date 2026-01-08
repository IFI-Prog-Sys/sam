"""
Main file for the Sam the Scraper bot
~~~~~~~~~~~~~~~~~~~

Responsible for extracting JSON program data,
initiating all relevant classes and connecting them together

:copyright: (c) 2025-present IFI-PROGSYS
:license: MIT, see LICENSE for more details.

▗▄▄▖  ▗▄▖ ▗▖ ▗▖▗▄▄▄▖▗▄▄▖ ▗▄▄▄▖▗▄▄▄
▐▌ ▐▌▐▌ ▐▌▐▌ ▐▌▐▌   ▐▌ ▐▌▐▌   ▐▌  █
▐▛▀▘ ▐▌ ▐▌▐▌ ▐▌▐▛▀▀▘▐▛▀▚▖▐▛▀▀▘▐▌  █
▐▌   ▝▚▄▞▘▐▙█▟▌▐▙▄▄▖▐▌ ▐▌▐▙▄▄▖▐▙▄▄▀
▗▄▄▖▗▖  ▗▖
▐▌ ▐▌▝▚▞▘
▐▛▀▚▖ ▐▌
▐▙▄▞▘ ▐▌
▗▄▄▄▖▗▖  ▗▖ ▗▄▄▖▗▄▄▖ ▗▄▄▖ ▗▄▄▄▖ ▗▄▄▖ ▗▄▄▖ ▗▄▖
▐▌   ▐▌  ▐▌▐▌   ▐▌ ▐▌▐▌ ▐▌▐▌   ▐▌   ▐▌   ▐▌ ▐▌
▐▛▀▀▘▐▌  ▐▌ ▝▀▚▖▐▛▀▘ ▐▛▀▚▖▐▛▀▀▘ ▝▀▚▖ ▝▀▚▖▐▌ ▐▌
▐▙▄▄▖ ▝▚▞▘ ▗▄▄▞▘▐▌   ▐▌ ▐▌▐▙▄▄▖▗▄▄▞▘▗▄▄▞▘▝▚▄▞▘
"""

import logging
import sys
from os import environ
import discord
import yaml
from sam import Sam
from discord_gateway import DiscordGateway

CONFIG_PATH = "./config.yaml"

logger = logging.getLogger("Sam.Main")
logger.setLevel(logging.DEBUG)

# systemd already tracks date and time so the redundancy is unnecessary
logger_formatter = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")

handler_info = logging.StreamHandler(sys.stdout)
handler_info.setLevel(logging.INFO)
handler_info.addFilter(lambda r: r.levelno < logging.ERROR)  # keep stdout to < ERROR
handler_info.setFormatter(logger_formatter)

handler_error = logging.StreamHandler(sys.stderr)
handler_error.setLevel(logging.ERROR)
handler_error.setFormatter(logger_formatter)

logger.addHandler(handler_info)
logger.addHandler(handler_error)

def get_config_data(config_path: str) -> tuple[str, str, str]:
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

    def load_config():
        try:
            with open(config_path, "r", encoding="utf-8") as file:
                config = yaml.safe_load(file)
                if isinstance(config, dict):
                    return config
                raise Exception
        except yaml.YAMLError:
            logger.error("Malformed config.yaml file. Could not load.")
            sys.exit(1)
        except Exception:
            logger.error("Unexpected behaviour when trying to load config")
            sys.exit(1)

    def safe_get(config: dict, key: str) -> str:
        element = config.get(key)
        if element is None:
            human_readable_key = " ".join(key.split("_"))
            logger.error("Couldn't load %s from config file", human_readable_key)
            sys.exit(1)
        return element

    config = load_config()

    organization_name = safe_get(config, "organization_name")
    channel_id = safe_get(config, "channel_id")
    api_key = environ.get("SAM_API_KEY")
    if api_key is None:
        logger.error("Couldn't load Discord API key from enviromental variables")
        sys.exit(1)

    return organization_name, channel_id, api_key

def main():
    """
    main function of the main file. Calls extract_metadata(), handles
    the returned program metadata, initiates Sam and DiscordGateway, and
    connects the two together.
    """
    logger.info("Starting Sam...")

    organization_name, channel_id, api_key = get_config_data(CONFIG_PATH)
    logger.info("Config loaded! Found org name: %s, channel id %s and API key", organization_name, channel_id)

    channel_id = int(channel_id)
    intents = discord.Intents.default()
    logger.info("Set Discord intents to default")

    sam = Sam(organization_name)
    logger.info("Started Sam OK")

    client = DiscordGateway(sam=sam, channel_id=channel_id, intents=intents)
    logger.info("Started Discord Gateway OK. Running...")
    client.run(api_key)

if __name__ == "__main__":
    print("Sam:Main - Starting up... Welcome!")
    main()
