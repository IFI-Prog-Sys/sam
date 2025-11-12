from sam import *
from time import sleep
import json
import discord

SIXTY_SECONDS = 60
DATA_JSON_PATH = "./secrets.json"

def extract_metadata():
    with open(DATA_JSON_PATH, "r") as file:
        external_metadata = json.load(file)

    organization_name = external_metadata.get("organization_name")
    channel_id = external_metadata.get("channel_id")
    api_key = external_metadata.get("discord_api_key")
    return organization_name, channel_id, api_key

def main():
    ORGANIZATION_NAME, CHANNEL_ID ,API_KEY = extract_metadata()
    print(f"Main loop: Set organization name to {ORGANIZATION_NAME}")

    sam = Sam(ORGANIZATION_NAME)

    discord_client_intents = discord.Intents.default()
    discord_client = discord.Client(intents=discord_client_intents)

    @discord_client.event
    async def on_ready():
        await discord_client.change_presence(
            status = discord.Status.online,
            activity=discord.Activity(name="Putting my nose to the scrapestone",
            type=discord.ActivityType.listening))
        
        while True:
            sam.updateLatestEvents()
            sam.extractLatestEvents()
            print("Main loop: Update done, sleeping for 60")
            sleep(SIXTY_SECONDS)

    discord_client.run(API_KEY)

if __name__ == "__main__":
    main()