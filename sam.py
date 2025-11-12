from dataclasses import dataclass
from enum import Enum
from bs4 import BeautifulSoup, Tag
import requests
import json
from datetime import datetime, timezone

FIVE_SECONDS = 5

class Comparison(Enum):
    EVENT_VALID = 0
    EVENT_EXPIRED = 1
    EVENT_ONGOING = 2

class SamError(Enum):
    HTTP = 1
    UNKNOWN = 2
    METADATA_NOT_FOUND = 3
    NOT_A_TAG = 4
    JSON_CONVERSION = 5

@dataclass
class Event:
    title: str
    description: str
    datetime: datetime | str
    place: str
    link: str

class Sam():
    def __init__(self, peoply_organization_name):
        self._http_header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
        }
        self._api_header = {
            "Accept": "application/json",
            "User-Agent": "SamTheScraper/0.5 (+https://progsys.no)"
        }

        self._organization_page_endpoint = f"https://peoply.app/orgs/{peoply_organization_name}"
        self._organization_uuid = self.__updateOrganizationUuid()
        print(f"Sam: Set self. value to {self._organization_uuid}")

        self._pending_events: list[Event] = list()
        self._last_update = self.__get_curent_formatted_time()
        self._cached_event_ids: list[str] = list()

    def __get_curent_formatted_time(self):
        current_utc_time = datetime.now(timezone.utc)
        formatted_time = current_utc_time.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        return formatted_time
    
    def __compare_time(self, current_time, event_time) -> Comparison:
        currnet_time_parsed = datetime.fromisoformat(current_time)
        if currnet_time_parsed < event_time:
            return Comparison.EVENT_VALID
        elif currnet_time_parsed > event_time:
            return Comparison.EVENT_EXPIRED
        else:
            return Comparison.EVENT_ONGOING

    def __get_raw_organization_page(self) -> str | SamError:
        try:
            print(f"Sam: Sending request to {self._organization_page_endpoint}")
            response = requests.get(self._organization_page_endpoint, headers=self._http_header ,timeout=FIVE_SECONDS)
            response.raise_for_status()
        except requests.exceptions.HTTPError as error:
            print(f"Sam: Request all events FAIL | HTTP error {error}")
            print(f"Sam: -> Status code: {error.response.status_code}")
            return SamError.HTTP
        except requests.exceptions.RequestException as error:
            print(f"Sam: Request all events FAIL | Unknown error")
            return SamError.UNKNOWN
        else:
            print(f"Sam: Response OK. Returning... \n")
            return response.text

    def __extract_organization_json(self, raw_data):
        soup = BeautifulSoup(raw_data, "lxml")
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

    def __extract_organization_uuid(self, organization_json: dict) -> str | None:
        props = organization_json.get("props")
        if props is None: return None

        pageProps = props.get("pageProps")
        if pageProps is None: return None
        
        organization = pageProps.get("organization")
        if organization is None: return None
        
        id = organization.get("id")
        if id is None: return None
        return id

    def __updateOrganizationUuid(self) -> str | int:
        print(f"Sam: Starting UUID update")
        organization_page_response = self.__get_raw_organization_page()
        org_uuid = "null"

        match organization_page_response:
            case SamError.HTTP:
                print("Sam: Caught HTTP error from __get_raw_organization_page()")
                print("Sam: -> Exiting...")
                exit(1)
            case SamError.UNKNOWN:
                print("Sam: Caught UNKNOWN error from __get_raw_organization_page()")
                print("Sam: -> Exiting...")
                exit(1)
            case str() as text:
                organization_json = self.__extract_organization_json(organization_page_response)
            case _:
                print("Sam: Encountered unexpected type when fetching organization page")
                raise TypeError("Unexpected return type from __get_raw_organization_page()")

        match organization_json:
            case SamError.NOT_A_TAG:
                print("Sam: Caught NOT_A_TAG error from __extract_organization_json()")
                print("Sam: -> Exiting...")
                exit(1)
            case SamError.METADATA_NOT_FOUND:
                print("Sam: Caught METADATA_NOT_FOUND error from __extract_organization_json()")
                print("Sam: -> Exiting...")
                exit(1)
            case dict() as dictionary:
                uuid_response = self.__extract_organization_uuid(organization_json)
                org_uuid = "null" if uuid_response is None else uuid_response
            case _:
                exit(1)

        print(f"Sam: Organization id: {org_uuid}")

        return org_uuid
    
    def __get_latest_raw_events(self):
        api_endpoint = f"https://api.peoply.app/events?afterDate={self._last_update}&organizationId={self._organization_uuid}"

        try:
            api_request_response = requests.get(api_endpoint, headers=self._api_header, timeout=FIVE_SECONDS)
            api_request_response.raise_for_status()
            json_data = api_request_response.json()
            return json_data
        except requests.exceptions.HTTPError as error:
            print(f"Sam: Request API endpoint FAIL | HTTP error {error}")
            print(f"Sam: -> Status code: {error.response.status_code}")
            return SamError.HTTP
        except requests.exceptions.RequestException as error:
            print(f"Sam: Request API endpoint FAIL | Unknown error")
            return SamError.UNKNOWN
        except ValueError as error:
            print(f"Sam: Parson API reply to JSON FAIL | Unknown error")
            return SamError.JSON_CONVERSION
        
    def __safe_json_get(self, attribute, json_file) -> str:
        fetched_attribute = json_file.get(attribute)
        if fetched_attribute is None:
            return "null"
        else:
            return fetched_attribute
        
    def __purge_expired_events(self):
        current_time = self.__get_curent_formatted_time()
        to_be_deleted = list()

        for event in self._pending_events:
            comparison_result = self.__compare_time(current_time, event.datetime)

            match comparison_result:
                case Comparison.EVENT_VALID:
                    continue
                case Comparison.EVENT_EXPIRED:
                    to_be_deleted.append(event)
                case Comparison.EVENT_ONGOING:
                    to_be_deleted.append(event)

        for event in to_be_deleted:
            self._pending_events.remove(event)
        
    def __event_exists_in_cache(self, raw_event_json) -> int:
        link_id = raw_event_json.get("urlId")
        if link_id is None:
            print("Sam: CRITICAL link_id was None when checking if exists in cache. Falling back to 'assume exists'")
            return True

        if link_id in self._cached_event_ids:
            return True
        else:
            self._cached_event_ids.append(link_id)
            return False
        
    def __parse_raw_event_data(self, raw_event_json) -> Event:
        start_date = self.__safe_json_get("startDate", raw_event_json)
        link_id = self.__safe_json_get("urlId", raw_event_json)

        event = Event(
            title = self.__safe_json_get("title", raw_event_json),
            description = self.__safe_json_get("description", raw_event_json),
            datetime = datetime.fromisoformat(start_date) if start_date != "null" else datetime(year = 0, month = 0, day = 0),
            place = self.__safe_json_get("locationName", raw_event_json),
            link = f"https://peoply.app/events/{link_id}"
        )

        return event
    
    def __non_redundant_event_add(self, raw_event):
        if self.__event_exists_in_cache(raw_event): return
        event = self.__parse_raw_event_data(raw_event)
        self._pending_events.append(event)
    
    def __update_sam_events_list(self):
        self.__purge_expired_events()
        get_events_response = self.__get_latest_raw_events()

        match get_events_response:
            case SamError.HTTP:
                print(f"Sam: Update events list FAIL | HTTP error. Not commiting to update.")
                return
            case SamError.UNKNOWN:
                print(f"Sam: Update events list FAIL | UKNOWN network error. Not commiting to update.")
                return
            case SamError.JSON_CONVERSION:
                print(f"Sam: Update events list FAIL | JSON_CONVERSION error. Not commiting to update.")
                return
            case dict() as d:
                self.__non_redundant_event_add(get_events_response)
            case list() as l:
                for raw_event in get_events_response:
                    self.__non_redundant_event_add(raw_event)
            case _:
                print(f"Sam: Unknown case occured in __update_sam_events_list(). Panic! Exiting...")
                exit(1)

        self._last_update = self.__get_curent_formatted_time()
        print(f"Sam: Pending events: {self._pending_events}")

    def updateLatestEvents(self):
        self.__update_sam_events_list()

    def extractLatestEvents(self) -> list[Event]:
        print(f"Sam: Length of pending events: {len(self._pending_events)}")
        return self._pending_events