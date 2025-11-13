import json
import discord
from sam import Sam
from discord_gateway import DiscordGateway

DATA_JSON_PATH = "./secrets.json"

def extract_metadata():
    with open(DATA_JSON_PATH, "r") as file:
        external_metadata = json.load(file)

    organization_name = external_metadata.get("organization_name")
    channel_id = external_metadata.get("channel_id")
    api_key = external_metadata.get("discord_api_key")
    return organization_name, channel_id, api_key

def main():
    ORGANIZATION_NAME, CHANNEL_ID, API_KEY = extract_metadata()
    print(f"Main loop: Set organization name to {ORGANIZATION_NAME}")

    CHANNEL_ID = int(CHANNEL_ID)

    intents = discord.Intents.default()
    sam = Sam(ORGANIZATION_NAME)
    print(f"CAHNNEL ID -> {CHANNEL_ID}")
    client = DiscordGateway(sam=sam, channel_id=CHANNEL_ID, intents=intents)
    client.run(API_KEY)

if __name__ == "__main__":
    main()