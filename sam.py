from dataclasses import dataclass
from enum import Enum
from bs4 import BeautifulSoup, Tag
import requests
import json
import datetime

FIVE_SECONDS = 5

class SamError(Enum):
    HTTP = 1
    UNKNOWN = 2
    METADATA_NOT_FOUND = 3
    NOT_A_TAG = 4

@dataclass
class Event:
    title: str
    description: str
    datetime: datetime.datetime
    place: str
    link: str

class Sam():
    def __init__(self, peoply_organization_name):
        self._pending_events: list[Event] = list()
        self._all_events_endpoint = f"https://peoply.app/orgs/{peoply_organization_name}"
        self._header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
        }

    def __get_all_raw_events(self) -> str | SamError:
        """
        @brief Fetch all raw events from the peoply organization page

        @return
            - SamError.HTTP_ERROR (1) on HTTP error.
            - SamError.UNKNOWN (2) on uknown error.
            - Else return raw payload
        """
        try:
            print(f"Sam: Sending request to {self._all_events_endpoint}")
            response = requests.get(self._all_events_endpoint, timeout=FIVE_SECONDS)
            response.raise_for_status()
        except requests.exceptions.HTTPError as error:
            print(f"Sam: Request all events FAIL | HTTP error {error}")
            print(f"Sam: -> Status code: {error.response.status_code}")
            return SamError.HTTP
        except requests.exceptions.RequestException as error:
            print(f"Sam: Request all events FAIL | Unknown error")
            return SamError.UNKNOWN
        else:
            print(f"Sam: Response OK. Returning... \n{response.text}")
            return response.text

    def __extract_event_links(self, raw_event_html: str) -> list[str]:
        print(f"Sam: Extracting event links from raw response")
        soup = BeautifulSoup(raw_event_html, "lxml")
        event_cards = soup.find_all("a", class_="LargeEventCard_cardWrapper__QACXr", href=True)

        print(f"Sam: Length of event cards: {len(event_cards)}")

        event_links = list()
        for element in event_cards:
            if not isinstance(element, Tag):
                print("Sam: Element wasn't Tag in __extract_event_links; Skipping...")
                continue

            href_value = element.get("href")
            if href_value is None:
                print("Sam: Got None value in __extract_event_links; Skipping...")
                continue

            print(f"Sam: Iterating over href value -> {href_value}")

            formatted_link = f"https://peoply.app{href_value}"
            event_links.append(formatted_link)

        print(f"Sam: Extracting event links done | {event_links}")
        return event_links

    def __get_raw_event(self, event_link: str):
        """
        @brief Fetch the raw event from the specified peoply event endpoint

        @return
        - Return SamError.HTTP_ERROR (1) on HTTP error.
        - Return SamError.UNKNOWN (2) on uknown error.
        - Else return raw payload
        """
        try:
            response = requests.get(event_link, timeout=FIVE_SECONDS)
            response.raise_for_status()
        except requests.exceptions.HTTPError as error:
            print(f"Sam: Request all events FAIL | HTTP error {error}")
            print(f"Sam: -> Status code: {error.response.status_code}")
            return SamError.HTTP
        except requests.exceptions.RequestException as error:
            print(f"Sam: Request all events FAIL | Unknown error")
            return SamError.UNKNOWN
        else:
            return response.text

    def __extract_event_json(self, raw_event):
        soup = BeautifulSoup(raw_event, "lxml")
        event_metadata = soup.find("script", id="__NEXT_DATA__", type="application/json")
        if isinstance(event_metadata, Tag):
            if not event_metadata or not event_metadata.string:
                print("Sam: Couldn't find event the requested metadata json")
                return SamError.METADATA_NOT_FOUND
            try:
                return json.loads(event_metadata.string)
            except json.JSONDecodeError:
                # Sometimes the contents may include whitespace or be malformed; try .get_text() as fallback
                return json.loads(event_metadata.get_text())
        else:
            print(f"Sam: Event metadata wasn't a Tag instance, returning...")
            return SamError.NOT_A_TAG
        
    def __atribute_typecheck(self, attribute):
        return attribute if attribute is not None else "null"

    def __produce_event_from_json(self, event_json: dict, event_link: str) -> Event:
        title=event_json.get("title")
        description=event_json.get("description")
        start_date = event_json.get("startDate")
        if start_date is not None:
            date_time=datetime.datetime.fromisoformat(start_date)
        else:
            date_time = datetime.datetime.fromisoformat("2000-00-00T00:00:00.000Z")
        place = event_json.get("locationName")


        event = Event(
            title = self.__atribute_typecheck(title),
            description = self.__atribute_typecheck(description),
            datetime = date_time,
            place = self.__atribute_typecheck(place),
            link=event_link
        )

        return event

    def checkForUpdates(self) -> int:
        print(f"Sam: Checking for event updates")
        all_raw_events_response = self.__get_all_raw_events()

        match all_raw_events_response:
            case SamError.HTTP:
                print("Sam: Caught HTTP error from __get_all_raw_events()")
                print("Sam: -> Returning with no updates")
                return -1
            case SamError.UNKNOWN:
                print("Sam: Caught UNKNOWN error from __get_all_raw_events()")
                print("Sam: -> Returning with no updates")
                return -1
            case str() as text:
                event_links = self.__extract_event_links(all_raw_events_response)
            case _:
                print("Sam: Encountered unexpected type when checking raw events response")
                raise TypeError("Unexpected return type from __get_all_raw_events()")

        for link in event_links:
            raw_event_response = self.__get_raw_event(link)

            match raw_event_response:
                case SamError.HTTP:
                    print("Sam: Caught HTTP error from __get_raw_event(); Skipping endpoint...")
                    continue
                case SamError.UNKNOWN:
                    print("Sam: Caught UNKNOWN error from __get_raw_event(); Skipping endpoint...")
                    continue
        
            event_json_response  = self.__extract_event_json(raw_event_response)

            match event_json_response:
                case SamError.METADATA_NOT_FOUND:
                    print("Sam: Caught METADATA_NOT_FOUND error from __extract_event_json(); Skipping endpoint...")
                    continue
                case SamError.NOT_A_TAG:
                    print("Sam: Caught NOT_A_TAG error from __extract_event_json(); Skipping endpoint...")
                    continue

            if not isinstance(event_json_response, dict):
                print(f"Sam: Returned JSON from __extract_event_json() wasn't dictionary; Skipping endpoint...")
                continue

            event = self.__produce_event_from_json(event_json_response, link)
            self._pending_events.append(event)

        return len(self._pending_events)

    def getLatestEvents(self):
        return self._pending_events