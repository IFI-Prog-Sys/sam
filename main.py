from sam import *
from discord_gateway import *
from time import sleep
import json

SIXTY_SECONDS = 60
DATA_JSON_PATH = "./data.json"

# Super simple architecture
# Main loop should probably be an epoll loop that listens to updates
# sam gives it an update, and this program forwards it to the discord gateway where its formatted and sent to a text channel
# This file's responsibility is to perform this epoll loop

def extract_metadata():
    with open(DATA_JSON_PATH, "r") as file:
        external_metadata = json.load(file)

    organization_name = external_metadata.get("organization_name")
    return organization_name

if __name__ == "__main__":
    ORGANIZATION_NAME = extract_metadata()
    print(f"Main loop: Set organization name to {ORGANIZATION_NAME}")

    sam = Sam(ORGANIZATION_NAME)
    discord_gateway = DiscordGateway()

    while True:
        sam.updateLatestEvents()
        sam.extractLatestEvents()
        print("Main loop: Update done, sleeping for 60")
        sleep(SIXTY_SECONDS)