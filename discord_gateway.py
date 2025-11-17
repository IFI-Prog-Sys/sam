"""
Interface between Sam and Discord API
~~~~~~~~~~~~~~~~~~~

A basic interface class meant to connect Sam the Scraper and the Discord API.

:copyright: (c) 2025-present IFI-PROGSYS
:license: MIT, see LICENSE for more details.

"""

from dataclasses import dataclass
from datetime import datetime, timezone
import discord
from discord.ext import tasks
from sam import Sam

SIXTY_SECONDS = 60


@dataclass
class EventMessage:
    """
    Container for a Discord message associated with an event and its expiration.

    Attributes:
        message: The Discord message object that displays event information.
        expires: The UTC datetime when this event should be considered expired
                 and removed from the internal tracking cache.
    """

    message: discord.Message
    expires: datetime


class DiscordGateway(discord.Client):
    """
    A Discord client that bridges Sam (the scraper) with a Discord text channel.

    Responsibilities:
    - Initializes and coordinates with the Sam scraper lifecycle.
    - Periodically fetches latest events from Sam and posts/edits messages in a
      configured Discord channel.
    - Tracks posted event messages to update them if metadata changes and
      garbage-collects expired entries.
    """

    def __init__(self, sam: Sam, channel_id: int, **kwargs):
        """
        Initialize the Discord gateway client.

        Args:
            sam: An initialized instance of Sam used to fetch event data.
            channel_id: The target Discord text channel ID for posting updates.
            **kwargs: Additional keyword arguments forwarded to discord.Client.
        """

        print("Sam:DiscordGateway - Initialising Discord Gateway")
        super().__init__(**kwargs)
        self.sam = sam
        self.channel_id = channel_id

        # Keep track of sent messages for events for future editing
        self._sent_messages: dict[str, EventMessage] = {}  # event id -> message id
        print("Sam:DiscordGateway - Initialising Discord Gateway 1/3 DONE")

    async def setup_hook(self):
        """
        Discord lifecycle hook executed during setup.

        - Ensures Sam is initialized before starting periodic tasks.
        - Starts the periodic event update loop.
        """

        # Ensure Sam is initialized before the task runs (UUID fetch etc.)
        await self.sam.init()
        print("Sam:DiscordGateway - Initialising Discord Gateway 2/3 DONE")
        # Create the loop task; start it in setup_hook to ensure loop is ready
        self.periodic_update_events.start()

    async def on_ready(self):
        """
        Called when the Discord client is fully connected and ready.

        - Sets a custom presence/activity for the bot.
        - Logs identity information for diagnostics.
        """
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                name="Putting my nose to the scrapestone",
                type=discord.ActivityType.listening,
            ),
        )
        if self.user is None:
            print("Discord Gateway: self.user init issue")
            return

        print("Sam:DiscordGateway - Initialising Discord Gateway 3/3 DONE")
        print("Sam:DiscordGateway - Initialising Discord Gateway OK")
        print(f"Sam:DiscordGateway - Logged in as {self.user} (ID: {self.user.id})")

    def __event_garbage_collector(self):
        """
        Remove expired event messages from the internal tracking cache.

        This does not delete messages from Discord; it only prunes local state
        for events whose expiration time has passed, so they are no longer
        considered for updates.
        """
        current_time = datetime.now(timezone.utc)
        chopping_block = []

        for event_message_key, event_message in self._sent_messages.items():
            if current_time >= event_message.expires:
                chopping_block.append(event_message_key)

        if len(chopping_block) > 0:
            print(
                "Sam:DiscordGateway - Event garbage collector ->"
                + f"{len(chopping_block)} candidates found for deletion. Purging..."
            )
            print(
                "Sam:DiscordGateway - Event garbage collector ->"
                + f"New event message queue size: {len(self._sent_messages)}"
            )

        for purge_candidate_key in chopping_block:
            del self._sent_messages[purge_candidate_key]

    @tasks.loop(seconds=SIXTY_SECONDS)
    async def periodic_update_events(self):
        """
        Periodic task loop that fetches, posts, and updates event messages.

        Every SIXTY_SECONDS:
        - Calls Sam to update and extract latest events.
        - Posts new events to the configured channel.
        - Edits existing event messages when metadata changes.
        - Logs progress and errors for observability.
        - Prunes expired events from local tracking via the garbage collector.

        Exceptions are caught and logged; the garbage collector runs in the
        finally block to ensure state remains consistent.
        """
        try:
            await self.sam.update_latest_events()
            events = self.sam.extract_latest_events()

            if events:
                print(
                    "Sam:DiscordGateway - Update Events Task Loop ->"
                    + f"{len(events)} new/modified events recieved"
                )

                # Example: Post updates to the channel (only new ones; sam handles cache)
                channel = self.get_channel(self.channel_id)

                if channel is None:
                    print(f"Channel {self.channel_id} not found.")
                    return
                if not isinstance(channel, discord.channel.TextChannel):
                    print(
                        f"Channel {self.channel_id} is of invalid type: {type(channel)}"
                    )
                    return

                print(
                    "Sam:DiscordGateway - Update Events Task Loop -> Connected to channel"
                )
                for event in events:
                    human_readable_time = event.date_time.strftime(
                        "%d.%m.%Y | kl. %H:%M"
                    )

                    # Update existing message
                    if event.id in self._sent_messages.keys():
                        event_message = self._sent_messages[event.id]
                        message = event_message.message
                        await message.edit(
                            content=f"## 🔔 {event.title}\n"
                            + f"{event.description}\n"
                            + f"__**Når?**__ {human_readable_time}\n"
                            + f"__**Hvor?**__ {event.place}\n"
                            + f"__**Påmelding:**__ {event.link}\n"
                        )
                        print(
                            "Sam:DiscordGateway - Update Events Task Loop ->"
                            + f"Updated event {event.id} with new metadata"
                        )

                    # Or send a new one
                    else:
                        message = await channel.send(
                            f"## 🔔 {event.title}\n"
                            + f"{event.description}\n"
                            + f"__**Når?**__ {human_readable_time}\n"
                            + f"__**Hvor?**__ {event.place}\n"
                            + f"__**Påmelding:**__ {event.link}\n"
                        )
                        event_message = EventMessage(
                            message=message, expires=event.date_time
                        )
                        self._sent_messages[event.id] = event_message
                        print(
                            "Sam:DiscordGateway - Update Events Task Loop ->"
                            + f"Created event {event.id}"
                        )
                print(
                    "Sam:DiscordGateway - Update Events Task Loop ->"
                    + f"Currently managing {len(self._sent_messages)} events"
                )
        except Exception as error:
            print(f"Periodic update failed: {error}")

        finally:
            self.__event_garbage_collector()

    @periodic_update_events.before_loop
    async def before_periodic_update_events(self):
        """
        Ensure the client is ready before starting the periodic event loop.

        This waits on Discord client's readiness to avoid race conditions with
        channel access and presence updates.
        """
        # Wait until the bot is ready before starting the loop
        await self.wait_until_ready()

    async def close(self):
        """
        Gracefully shut down the Discord client and Sam.

        - Closes the Discord client via the superclass implementation.
        - Closes Sam to release any resources (e.g., sessions, files).
        """
        await super().close()
        await self.sam.close()
