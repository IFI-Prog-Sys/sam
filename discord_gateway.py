import discord
from sam import *
from discord.ext import tasks
from sam import Sam
from datetime import datetime

SIXTY_SECONDS = 60

@dataclass
class EventMessage:
    message: discord.Message
    expires: datetime

class DiscordGateway(discord.Client):
    def __init__(self, sam: Sam, channel_id: int, **kwargs):
        print(f"Sam:DiscordGateway - Initialising Discord Gateway")
        super().__init__(**kwargs)
        self.sam = sam
        self.channel_id = channel_id

        # Keep track of sent messages for events for future editing
        # TODO: Add a garbage collector that deletes message objects for expired events
        self._sent_messages: dict[str, EventMessage] = {} # event id -> message id
        print(f"Sam:DiscordGateway - Initialising Discord Gateway 1/3 DONE")

    async def setup_hook(self):
        # Ensure Sam is initialized before the task runs (UUID fetch etc.)
        await self.sam.init()
        print(f"Sam:DiscordGateway - Initialising Discord Gateway 2/3 DONE")
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

        print(f"Sam:DiscordGateway - Initialising Discord Gateway 3/3 DONE")
        print(f"Sam:DiscordGateway - Initialising Discord Gateway OK")
        print(f"Sam:DiscordGateway - Logged in as {self.user} (ID: {self.user.id})")

    def __event_garbage_collector(self):
        current_time = datetime.now(timezone.utc)
        chopping_block = []

        for event_message_key in self._sent_messages.keys():
            event_message = self._sent_messages[event_message_key]

            if current_time >= event_message.expires:
                chopping_block.append(event_message_key)


        if len(chopping_block) > 0:
            print(f"Sam:DiscordGateway - Event garbage collector -> {len(chopping_block)} candidates found for deletion. Purging...")
            print(f"Sam:DiscordGateway - Event garbage collector -> New event message queue size: {len(self._sent_messages)}")

        for purge_candidate_key in chopping_block:
            del self._sent_messages[purge_candidate_key]


    @tasks.loop(seconds=SIXTY_SECONDS)
    async def periodic_update_events(self):
        try:
            await self.sam.updateLatestEvents()
            events = self.sam.extractLatestEvents()

            if events:
                print(f"Sam:DiscordGateway - Update Events Task Loop -> {len(events)} new/modified events recieved")

                # Example: Post updates to the channel (only new ones; sam handles cache)
                channel = self.get_channel(self.channel_id)

                if channel is None:
                    print(f"Channel {self.channel_id} not found.")
                    return
                if not isinstance(channel, discord.channel.TextChannel):
                    print(f"Channel {self.channel_id} is of invalid type: {type(channel)}")
                    return

                print(f"Sam:DiscordGateway - Update Events Task Loop -> Connected to channel")
                for event in events:
                    human_readable_time = event.date_time.strftime("%d.%m.%Y | kl. %H:%M")

                    # Update existing message
                    if event.id in self._sent_messages.keys():
                        event_message = self._sent_messages[event.id]
                        message = event_message.message
                        await message.edit(
                                content =
                                f"## 🔔 {event.title}\n"+
                                f"{event.description}\n"+
                                f"__**Når?**__ {human_readable_time}\n"+
                                f"__**Hvor?**__ {event.place}\n"+
                                f"__**Påmelding:**__ {event.link}\n"
                                )
                        print(f"Sam:DiscordGateway - Update Events Task Loop -> Updated event {event.id} with new metadata")
                    
                    # Or send a new one
                    else:
                        message = await channel.send(
                            f"## 🔔 {event.title}\n"+
                            f"{event.description}\n"+
                            f"__**Når?**__ {human_readable_time}\n"+
                            f"__**Hvor?**__ {event.place}\n"+
                            f"__**Påmelding:**__ {event.link}\n"
                            )
                        event_message = EventMessage(
                            message = message,
                            expires = event.date_time)
                        self._sent_messages[event.id] = event_message
                        print(f"Sam:DiscordGateway - Update Events Task Loop -> Created event {event.id}")
                print(f"Sam:DiscordGateway - Update Events Task Loop -> Currently managing {len(self._sent_messages)} events")
        except Exception as error:
            print(f"Periodic update failed: {error}")

        finally:
            self.__event_garbage_collector()

    @periodic_update_events.before_loop
    async def before_periodic_update_events(self):
        # Wait until the bot is ready before starting the loop
        await self.wait_until_ready()

    async def close(self):
        await super().close()
        await self.sam.close()
