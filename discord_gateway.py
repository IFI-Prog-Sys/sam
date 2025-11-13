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

        # Keep track of sent messages for events for future editing
        # TODO: Add a garbage collector that deletes message objects for expired events
        self._sent_messages: dict[Event, discord.Message] = {}

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
            if not isinstance(channel, discord.channel.TextChannel):
                print(f"Channel {self.channel_id} is of invalid type: {type(channel)}")
                return

            if events:
                for event in events:
                    human_readable_time = event.datetime.strftime("%d.%m.%Y | kl. %H:%M")

                    self._sent_messages[event] = await channel.send(
                        "## 🔔 Arrangement varsel 🔔\n"+
                        f"**Hva?** {event.title}\n"+
                        f"{event.description}\n"+
                        f"**Når?** {human_readable_time}\n"+
                        f"**Hvor?** {event.place}\n"+
                        f"**Påmelding:** {event.link}\n"
                        )
            else:
                print("No pending events to announce.")
        except Exception as error:
            print(f"Periodic update failed: {error}")

        finally:
            print("TRY OK LOL")

    @periodic_update_events.before_loop
    async def before_periodic_update_events(self):
        # Wait until the bot is ready before starting the loop
        await self.wait_until_ready()

    async def close(self):
        await super().close()
        await self.sam.close()
