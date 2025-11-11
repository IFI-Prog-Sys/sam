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
        self._organization_page_endpoint = f"https://peoply.app/orgs/{peoply_organization_name}"
        self._header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
        }

    def __get_raw_organization_page(self) -> str | SamError:
        try:
            print(f"Sam: Sending request to {self._organization_page_endpoint}")
            response = requests.get(self._organization_page_endpoint, headers=self._header ,timeout=FIVE_SECONDS)
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

    def getLatestEvents(self):
        return self._pending_events