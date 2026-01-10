"""
Peoply.app API interaction manager
~~~~~~~~~~~~~~~~~~~

A basic async API data fetcher and processor.

:copyright: (c) 2025-present IFI-PROGSYS
:license: MIT, see LICENSE for more details.
"""

import json
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone
import logging
import sys
import sqlite3
import aiohttp
from bs4 import BeautifulSoup, Tag

TEN_SECONDS = 10

logger = logging.getLogger("Sam.Sam")
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


class Comparison(Enum):
    """
    Enumeration describing temporal comparison outcomes between two datetimes.

    Values:
        EVENT_VALID: The event occurs in the future relative to the compared time.
        EVENT_EXPIRED: The event has passed relative to the compared time.
        EVENT_ONGOING: The event time is equal to the compared time (treated as ongoing).
    """

    EVENT_VALID = 0
    EVENT_EXPIRED = 1
    EVENT_ONGOING = 2


class SamError(Enum):
    """
    Error categories used by Sam to communicate failure causes.

    Values:
        HTTP: Network request returned an HTTP error code (>= 400).
        UNKNOWN: An unexpected network or runtime error occurred.
        METADATA_NOT_FOUND: Expected metadata was not found in HTML.
        NOT_A_TAG: Parsed element was not a BeautifulSoup Tag as expected.
        JSON_CONVERSION: Failed to convert response to JSON.
    """

    HTTP = 1
    UNKNOWN = 2
    METADATA_NOT_FOUND = 3
    NOT_A_TAG = 4
    JSON_CONVERSION = 5


@dataclass
class Event:
    """
    Data model representing an event fetched from Peoply.app.

    Attributes:
        title: Event title.
        description: Event description or summary.
        date_time: Start datetime for the event (UTC).
        last_updated: Last modification time of the event (UTC).
        place: Location or venue name.
        id: Stable identifier for the event (e.g., URL slug/ID).
        link: Public link to the event page.
    """

    title: str
    description: str
    date_time: datetime
    last_updated: datetime
    place: str
    id: str
    link: str


class Sam:
    """
    Async API interaction manager for Peoply.app.

    Responsibilities:
    - Discovers and stores the organization UUID used for API requests.
    - Polls Peoply.app for new or updated events since the last update time.
    - Maintains an in-memory cache to avoid redundant event processing.
    - Persists events to a SQLite database to allow state recovery between restarts.
    - Provides a queue of deduplicated Event instances for downstream consumers.
    """

    def __init__(
        self,
        peoply_organization_name: str,
        database_path: str,
        session: aiohttp.ClientSession | None = None,
    ):
        """
        Initialize the Sam scraper/manager.

        Args:
            peoply_organization_name: The organization slug/name used to locate
                the organization page and derive the internal UUID.
            database_path: The file path to the SQLite database used for
                persistent event storage.
            session: Optional externally managed aiohttp.ClientSession. If not
                provided, Sam will lazily create and manage its own session.

        Notes:
            Organization UUID lookup is deferred to init() to avoid synchronous
            I/O in the constructor.
        """
        logger.info("Initialising Sam")
        self._regular_header = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/141.0.0.0 Safari/537.36"
            )
        }
        self._api_header = {
            "Accept": "application/json",
            "User-Agent": "SamTheScraper/1.0 (+https://github.com/IFI-Prog-Sys/sam/)",
        }

        self._organization_name = peoply_organization_name

        self._cached_events: dict[str, Event] = {}
        # This refers to Sam's last update, as opposed to the Event dataclass that keeps
        # track of the server's last update timestamp
        self._sam_event_last_updated: dict[str, datetime] = {}
        self._outbound_event_queue: list[Event] = []
        self._last_update = self.__get_curent_formatted_time()

        # Externally provided session preferred; otherwise create lazily on first request
        self._session = session

        # Initialize UUID asynchronously later via init() to avoid sync call in __init__
        self._organization_uuid: str = "null"

        self._database_connection = sqlite3.connect(database_path)
        self._database_cursor = self._database_connection.cursor()
        logger.info("Connect to database OK")

        query_result = self._database_cursor.execute("SELECT * FROM sqlite_master")
        table_not_exist = query_result.fetchone is None
        if table_not_exist:
            logger.info("Database was empty; Creating new table")
            self._database_cursor.execute(
                "CREATE TABLE events(title, description, date_time, last_updated, place, id link)"
            )
            logger.info("Create Table OK")
        else:
            logger.info("Database already populdated. Recalling events")
            self.__recall_past_events()
            logger.info("Recall OK")

        logger.info("Initialising Sam 1/2 DONE.")

    async def init(self):
        """
        Perform asynchronous initialization tasks.

        - Fetches and stores the organization's UUID by scraping the org page.
        - Logs progress for diagnostics.

        Raises:
            RuntimeError, TypeError: If the organization page or metadata cannot
            be fetched or parsed.
        """
        self._organization_uuid = await self.__get_organization_uuid()
        logger.info(f"Fetched organization UID: {self._organization_uuid}.")
        logger.info("Initialising Sam 2/2 DONE.")
        logger.info("Initialising Sam OK.")

    def __deserialize_raw_event(self, raw_event: tuple) -> Event:
        event = Event(
            title=raw_event[0],
            description=raw_event[1],
            date_time=datetime.fromisoformat(raw_event[2]),
            last_updated=datetime.fromisoformat(raw_event[3]),
            place=raw_event[4],
            id=raw_event[5],
            link=raw_event[6],
        )
        return event

    def __recall_past_events(self):
        result = self._database_cursor.execute("SELECT * FROM events")
        all_raw_events = result.fetchall()

        for raw_event in all_raw_events:
            event = self.__deserialize_raw_event(raw_event)
            self._sam_event_last_updated[event.id] = event.last_updated
            self._cached_events[event.id] = event

        logger.info(f"Recalled {len(all_raw_events)} events")
        self.__purge_expired_events()

    def __get_curent_formatted_time(self):
        """
        Get the current UTC time formatted as an ISO-8601 string with milliseconds.

        Returns:
            A string in the format: YYYY-MM-DDTHH:MM:SS.mmmZ (UTC, 'Z' suffix).
        """
        current_utc_time = datetime.now(timezone.utc)
        formatted_time = current_utc_time.isoformat(timespec="milliseconds").replace(
            "+00:00", "Z"
        )
        return formatted_time

    def __compare_time(
        self, current_time: datetime, event_time: datetime
    ) -> Comparison:
        """
        Compare two datetimes to classify an event's temporal status.

        Args:
            current_time: The reference time.
            event_time: The event's time to compare against the reference.

        Returns:
            Comparison: EVENT_VALID if event_time is in the future,
                        EVENT_EXPIRED if in the past,
                        EVENT_ONGOING if equal.
        """
        if current_time < event_time:
            return Comparison.EVENT_VALID
        if current_time > event_time:
            return Comparison.EVENT_EXPIRED
        return Comparison.EVENT_ONGOING

    async def __get_session(self) -> aiohttp.ClientSession:
        """
        Get or lazily create an aiohttp.ClientSession with a default timeout.

        Returns:
            An active aiohttp.ClientSession instance.
        """
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=TEN_SECONDS)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def __get_organization_uuid(self) -> str:
        """
        Resolve and return the organization's UUID by scraping the org page.

        Returns:
            The organization UUID as a string. If not found, returns "null".

        Raises:
            RuntimeError: When required metadata is missing or malformed.
            TypeError: If the organization page fetch returns an unexpected type.
        """

        async def get_raw_organization_page() -> str | SamError:
            """
            Fetch the raw HTML for the organization's Peoply page.

            Returns:
                The response text on success, or a SamError on failure.
            """
            try:
                session = await self.__get_session()
                async with session.get(
                    f"https://peoply.app/orgs/{self._organization_name}",
                    headers=self._regular_header,
                ) as response:
                    if response.status >= 400:
                        logger.error(
                            f"Request all events FAIL | HTTP error {response.status}"
                        )
                        return SamError.HTTP
                    text = await response.text()
                    return text
            except aiohttp.ClientError as error:
                logger.error(f"Request all events FAIL | Unknown error: {error}")
                return SamError.UNKNOWN

        def extract_organization_json(raw_data):
            """
            Parse the organization's HTML page and extract the embedded Next.js JSON.

            Args:
                raw_data: The HTML string of the organization's page.

            Returns:
                A dict containing the parsed JSON, or a SamError indicating the reason
                for failure.
            """
            soup = BeautifulSoup(raw_data, "lxml")
            event_metadata = soup.find(
                "script", id="__NEXT_DATA__", type="application/json"
            )
            if isinstance(event_metadata, Tag):
                if not event_metadata or not event_metadata.string:
                    logger.warning("Couldn't find the requested metadata")
                    return SamError.METADATA_NOT_FOUND
                try:
                    return json.loads(event_metadata.string)
                except json.JSONDecodeError:
                    # Sometimes the contents may include whitespace
                    # or be malformed; try .get_text() as fallback
                    return json.loads(event_metadata.get_text())
            else:
                logger.warning("Event metadata wasn't a Tag instance, returning...")
                return SamError.NOT_A_TAG

        def extract_organization_uuid(organization_json: dict) -> str | None:
            """
            Traverse the Next.js JSON object to extract the organization UUID.

            Args:
                organization_json: Parsed JSON dictionary from the org page.

            Returns:
                The organization UUID string if found, otherwise None.
            """
            props = organization_json.get("props")
            if props is None:
                return None

            page_props = props.get("pageProps")
            if page_props is None:
                return None

            organization = page_props.get("organization")
            if organization is None:
                return None

            org_id = organization.get("id")
            if org_id is None:
                return None
            return org_id

        organization_page_response = await get_raw_organization_page()
        org_uuid = "null"

        if organization_page_response in (SamError.HTTP, SamError.UNKNOWN):
            raise RuntimeError(
                f"Failed to fetch organization page: {organization_page_response}"
            )

        if not isinstance(organization_page_response, str):
            raise TypeError("Unexpected return type from __get_raw_organization_page()")

        organization_json = extract_organization_json(organization_page_response)

        match organization_json:
            case SamError.NOT_A_TAG:
                raise RuntimeError("Organization JSON not a tag")
            case SamError.METADATA_NOT_FOUND:
                raise RuntimeError("Organization metadata not found")
            case dict():
                uuid_response = extract_organization_uuid(organization_json)
                org_uuid = "null" if uuid_response is None else uuid_response
            case _:
                raise RuntimeError("Unexpected organization JSON type")

        return org_uuid

    async def __get_latest_raw_events(self):
        """
        Query the Peoply API for events updated since the last update checkpoint.

        Returns:
            A list or dict of raw event JSON on success, or a SamError on failure.
        """
        api_endpoint = f"https://api.peoply.app/events?afterDate={self._last_update}&organizationId={self._organization_uuid}"
        try:
            session = await self.__get_session()
            async with session.get(api_endpoint, headers=self._api_header) as response:
                if response.status >= 400:
                    logger.error(
                        f"Request API endpoint FAIL | HTTP error {response.status}"
                    )
                    return SamError.HTTP

                json_data = await response.json(content_type=None)
                return json_data

        except aiohttp.ClientError as error:
            logger.error(f"Request API endpoint FAIL | Unknown error: {error}")
            return SamError.UNKNOWN

        except (json.JSONDecodeError, ValueError) as error:
            logger.error(f"Parse API reply to JSON FAIL | {error}")
            return SamError.JSON_CONVERSION

    def __safe_json_get(self, attribute, json_file) -> str:
        """
        Safely get an attribute from a JSON-like dict with a "null" fallback.

        Args:
            attribute: The key to fetch.
            json_file: The JSON-like dictionary.

        Returns:
            The value if present, otherwise the string "null".
        """
        fetched_attribute = json_file.get(attribute)
        if fetched_attribute is None:
            return "null"
        return fetched_attribute

    def __purge_expired_events(self):
        """
        Remove events from the pending queue that have expired or are ongoing now.

        Uses the current UTC time to compare against each event's start time.
        """
        current_time = datetime.fromisoformat(self.__get_curent_formatted_time())
        to_be_deleted = []

        for event_key, event in self._cached_events.items():
            comparison_result = self.__compare_time(current_time, event.date_time)

            match comparison_result:
                case Comparison.EVENT_VALID:
                    continue
                case Comparison.EVENT_EXPIRED | Comparison.EVENT_ONGOING:
                    to_be_deleted.append(event_key)

        if len(to_be_deleted) > 0:
            logger.info(
                f"Purging {len(to_be_deleted)} events from queue of size {len(self._cached_events)}."
            )

        for event_key in to_be_deleted:
            del self._cached_events[event_key]
            self._database_cursor.execute(f"""
            DELETE FROM events
            WHERE id={event_key}
            """)

    def __event_exists_in_cache(self, raw_event_json) -> bool:
        """
        Determine whether a raw event payload already exists in cache without updates.

        Logic:
        - Uses 'urlId' as a stable key and 'updatedAt' to detect freshness.
        - Updates the cache if a newer 'updatedAt' is observed.
        - Handles malformed JSON defensively by assuming existence.

        Args:
            raw_event_json: The raw event JSON dict from the API.

        Returns:
            True if the event should be treated as existing (no new action),
            False if it's new or updated and should be processed.
        """
        event_link_id = raw_event_json.get("urlId")
        new_event_last_updated = datetime.fromisoformat(
            self.__safe_json_get("updatedAt", raw_event_json)
        )

        if event_link_id is None or new_event_last_updated == "null":
            logger.critical(
                "JSON integrity issue when checking cache. Assuming event exists"
            )
            return True

        if event_link_id in self._sam_event_last_updated:
            cached_event_last_updated = self._sam_event_last_updated[event_link_id]
            time_comparison_verdict = self.__compare_time(
                cached_event_last_updated, new_event_last_updated
            )
            match time_comparison_verdict:
                case Comparison.EVENT_EXPIRED:
                    logger.critical(
                        "Cached event has newer 'updatedAt' time. Defaulting to not updating cache"
                    )
                    return True
                case Comparison.EVENT_ONGOING:
                    return True
                case Comparison.EVENT_VALID:
                    self._sam_event_last_updated[event_link_id] = (
                        new_event_last_updated  # Update cache with new last updated time
                    )
                    return False
                case _:
                    logger.critical(
                        "Reached default case in __event_exists. Defaulting to not updating cache"
                    )
                    return True
        return False

    def __parse_raw_event_data(self, raw_event_json) -> Event:
        """
        Convert a raw event JSON payload into an Event dataclass instance.

        Args:
            raw_event_json: The raw event dict from the Peoply API.

        Returns:
            An Event instance populated with normalized data. For missing dates,
            sentinel datetime values (year=1) are used.
        """
        start_date = self.__safe_json_get("startDate", raw_event_json)
        last_updated = self.__safe_json_get("updatedAt", raw_event_json)
        link_id = self.__safe_json_get("urlId", raw_event_json)

        event = Event(
            title=self.__safe_json_get("title", raw_event_json),
            description=self.__safe_json_get("description", raw_event_json),
            date_time=datetime.fromisoformat(start_date)
            if start_date != "null"
            else datetime(year=1, month=1, day=1),
            last_updated=datetime.fromisoformat(last_updated)
            if last_updated != "null"
            else datetime(year=1, month=1, day=1),
            place=self.__safe_json_get("locationName", raw_event_json),
            id=link_id,
            link=f"https://peoply.app/events/{link_id}",
        )

        return event

    def __non_redundant_event_add(self, raw_event):
        """
        Add a new or updated event to internal queues if not redundant.

        - Skips events that already exist in cache without updates.
        - Populates pending and outbound queues for downstream consumption.

        Args:
            raw_event: The raw event JSON dict.
        """
        if self.__event_exists_in_cache(raw_event):
            return

        event = self.__parse_raw_event_data(raw_event)

        self._sam_event_last_updated[event.id] = event.last_updated
        self._cached_events[event.id] = event
        self._outbound_event_queue.append(event)

        self._database_cursor.execute(f"""
            INSERT INTO events VALUES
            ('{event.title}', '{event.description}', '{event.date_time}', '{event.last_updated}', '{event.place}', '{event.id}', '{event.link}')
        """)
        self._database_connection.commit()

    async def __update_sam_events_list(self):
        """
        Refresh the internal list of events from the Peoply API.

        Steps:
        - Fetches latest raw events since the last update time.
        - Deduplicates and queues new/updated events.
        - Advances the internal last-update checkpoint on success-like paths.

        Notes:
            Gracefully handles HTTP, network, and JSON parsing errors by
            logging and skipping the commit.
        """
        get_events_response = await self.__get_latest_raw_events()
        events_last_updated = self.__get_curent_formatted_time()

        match get_events_response:
            case SamError.HTTP:
                logger.warning(
                    "Update events list FAIL | HTTP error. Not committing to update."
                )
                return
            case SamError.UNKNOWN:
                logger.warning(
                    "Update events list FAIL | UNKNOWN network error. Not committing to update."
                )
                return
            case SamError.JSON_CONVERSION:
                logger.warning(
                    "Update events list FAIL | JSON_CONVERSION error. Not committing to update."
                )
                return
            case dict():
                # Some endpoints may return a single dict instead of list
                self.__non_redundant_event_add(get_events_response)
            case list():
                for raw_event in get_events_response:
                    self.__non_redundant_event_add(raw_event)
            case _:
                logger.critical(
                    "Unknown case occurred in __update_sam_events_list(). Aborting update."
                )
                return

        # Only commit last updated time if no errors occur
        self._last_update = events_last_updated

    def purge_expired_events(self):  # Step 1 of update schedule in Discord Gateway
        """
        Public method to trigger the expiration of events.

        This wraps the internal purge routine to be called by external schedulers.
        """
        self.__purge_expired_events()

    async def update_latest_events(
        self,
    ):  # Step 2 of update schedule in Discord Gateway
        """
        Public method to trigger a refresh of the latest events.

        This wraps the internal update routine to be called by external schedulers.
        """
        await self.__update_sam_events_list()

    def extract_latest_events(
        self,
    ) -> list[Event]:  # Step 3 of update schedule in Discord Gateway
        """
        Retrieve and clear the queue of newly discovered or updated events.

        Returns:
            A list of Event instances since the previous extraction. The internal
            outbound queue is reset after retrieval.
        """
        outbound_event_queue = self._outbound_event_queue
        if len(outbound_event_queue) > 0:
            logger.info(
                f"Extracted {len(outbound_event_queue)} new/updated events. {len(self._cached_events)} events in pending queue."
            )
        self._outbound_event_queue = []
        return outbound_event_queue

    async def close(self):
        """
        Clean up resources owned by Sam.

        - Logs shutdown message.
        - Closes the aiohttp session if it is owned and still open.
        - Commits any pending changes and closes the database connection.
        """
        logger.info("Closing Sam. Goodbye!")
        if self._session and not self._session.closed:
            await self._session.close()

        self._database_connection.commit()
        self._database_connection.close()
