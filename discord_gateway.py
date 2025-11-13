from sam import *
import discord
from discord.ext import tasks
from sam import Sam

SIXTY_SECONDS = 60

class DiscordGateway(discord.Client):
    def __init__(self, sam: Sam, channel_id: int, **kwargs):
        super().__init__(**kwargs)
        self.sam = sam
        self.channel_id = channel_id

    async def setup_hook(self):
        # Ensure Sam is initialized before the task runs (UUID fetch etc.)
        await self.sam.init()
        # Create the loop task; start it in setup_hook to ensure loop is ready
        self.periodic_update_events.start()

    async def on_ready(self):
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                name="Putting my nose to the scrapestone",
                type=discord.ActivityType.listening
            )
        )
        if self.user is None:
            print("Discord Gateway: self.user init issue")
            return

        print(f"Logged in as {self.user} (ID: {self.user.id})")

    @tasks.loop(seconds=SIXTY_SECONDS)
    async def periodic_update_events(self):
        try:
            print("Periodic task: updating events")
            await self.sam.updateLatestEvents()
            events = self.sam.extractLatestEvents()

            # Example: Post updates to the channel (only new ones; sam handles cache)
            channel = self.get_channel(self.channel_id)
            if channel is None:
                print(f"Channel {self.channel_id} not found.")
                return

            # Compose a message for any new pending events
            # You can track which were just added by comparing lengths or refactoring Sam to return newly added
            """
            if events:
                # Keep messages short to avoid rate limits; chunk if needed
                lines = []
                for ev in events:
                    lines.append(f"- {ev.title} at {ev.place} on {ev.datetime.isoformat()} -> {ev.link}")
                msg = "\n".join(lines)
                await channel.send(f"Latest events:\n{msg}")
            else:
                print("No pending events to announce.")
        except Exception as e:
            print(f"Periodic update failed: {e}")
            """
        finally:
            print("TRY OK LOL")

    @periodic_update_events.before_loop
    async def before_periodic_update_events(self):
        # Wait until the bot is ready before starting the loop
        await self.wait_until_ready()

    async def close(self):
        await super().close()
        await self.sam.close()
