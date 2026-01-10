"""
Main file for the Sam the Scraper bot
~~~~~~~~~~~~~~~~~~~

Responsible for loading configuration,
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

from dataclasses import dataclass
import logging
import sys
from os import environ
import dataclasses
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

@dataclass
class ConfigData:
    organization_name: str
    channel_id: str
    database_path: str
    api_key: str

def get_config_data(config_path: str) -> ConfigData
    """
    Reads configuration data from a YAML file and environment variables.

    This function loads configuration from the specified YAML file, expecting
    'organization_name' and 'channel_id'. It also retrieves the Discord API
    key from the 'SAM_API_KEY' environment variable.

    The program will exit with a status code of 1 if the config file cannot be
    found or is malformed, or if any of the required configuration values
    are missing.

    Parameters
    ----------
    config_path : str
        The path to the configuration YAML file.

    Returns
    -------
    tuple[str, str, str]
        A tuple containing the organization name, channel ID, and API key.
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
    database_path = safe_get(config, "database_path")
    api_key = environ.get("SAM_API_KEY")
    if api_key is None:
        logger.error("Couldn't load Discord API key from enviromental variables")
        sys.exit(1)

    config_data = ConfigData(
        organization_name=organization_name,
        channel_id=channel_id,
        database_path=database_path,
        api_key=api_key
    )

    return config_data


def main():
    """
    Main entry point for the Sam the Scraper bot.

    This function loads the configuration, initializes the main 'Sam' logic
    and the 'DiscordGateway' client, and then starts the bot.
    """
    logger.info("Starting Sam...Welcome!")

    config_data = get_config_data(CONFIG_PATH)
    logger.info(
        "Config loaded! Found org name: %s, channel id %s and API key",
        config_data.organization_name,
        config_data.channel_id,
    )

    channel_id = int(config_data.channel_id)
    intents = discord.Intents.default()
    logger.info("Set Discord intents to default")

    sam = Sam(config_data.organization_name)
    logger.info("Started Sam OK")

    client = DiscordGateway(sam=sam, channel_id=channel_id, intents=intents)
    logger.info("Started Discord Gateway OK. Running...")
    client.run(config_data.api_key)


if __name__ == "__main__":
    main()
