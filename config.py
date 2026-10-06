from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

DATABASE_PATH = DATA_DIR / "gifa.db"

GIFA_BASE_URL = (
    "https://widgets.messe-duesseldorf.de/vis-api/vis/v1/en/directory"
)
GIFA_DOMAIN = "www.gifa.com"

GIFA_EVENT_ID = "GMTN2023.gifa"

REQUEST_TIMEOUT = 30

DIRECTORY_LETTERS = "abcdefghijklmnopqrstuvwxyz"

# The four events share the Messe Düsseldorf VIS directory API.  Keeping the
# event-specific values here means the scraper does not need one implementation
# per event.
EVENTS = {
    "GIFA": {
        "base_url": GIFA_BASE_URL,
        "domain": GIFA_DOMAIN,
        "event_code": GIFA_EVENT_ID,
        "event_label": "GIFA 2023",
        "edition": 2023,
    },
    "METEC": {
        "base_url": GIFA_BASE_URL,
        "domain": "www.metec.com",
        "event_code": "GMTN2023.metec",
        "event_label": "METEC 2023",
        "edition": 2023,
    },
    "THERMPROCESS": {
        "base_url": GIFA_BASE_URL,
        "domain": "www.thermprocess-expo.com",
        "event_code": "GMTN2023.thermpro",
        "event_label": "THERMPROCESS 2023",
        "edition": 2023,
    },
    "NEWCAST": {
        "base_url": GIFA_BASE_URL,
        "domain": "www.newcast.com",
        "event_code": "GMTN2023.newcast",
        "event_label": "NEWCAST 2023",
        "edition": 2023,
    },
}