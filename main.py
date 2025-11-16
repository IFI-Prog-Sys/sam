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
    print(f"Sam:Main - Extracting metadata from secrets.json")
    ORGANIZATION_NAME, CHANNEL_ID, API_KEY = extract_metadata()
    print(f"Sam:Main - Found metadata:\tOrg name: {ORGANIZATION_NAME}\n\tChannel ID: {CHANNEL_ID}\n\tAPI KEY LENGTH: {len(API_KEY)}")

    CHANNEL_ID = int(CHANNEL_ID)
    intents = discord.Intents.default()
    print(f"Sam:Main - Set Discord intentions OK")
    sam = Sam(ORGANIZATION_NAME)
    print(f"Sam:Main - Started Sam OK")
    client = DiscordGateway(sam=sam, channel_id=CHANNEL_ID, intents=intents)
    print(f"Sam:Main - Started DiscordGateway OK")
    print(f"Sam:Main - Running Discord bot client...")
    client.run(API_KEY)

if __name__ == "__main__":
    print(f"Sam:Main - Starting up... Welcome!")
    main()