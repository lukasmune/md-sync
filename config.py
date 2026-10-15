from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

DATABASE_PATH = DATA_DIR / "md-sync.db"
LEGACY_DATABASE_PATH = DATA_DIR / "gifa.db"
EXPORTS_DIR = BASE_DIR / "exports"
CHANGES_DIR = EXPORTS_DIR / "changes"

GIFA_BASE_URL = (
    "https://widgets.messe-duesseldorf.de/vis-api/vis/v1/en/directory"
)
GIFA_DOMAIN = "www.gifa.com"
FINDER_BASE_URL = "https://finder.messe-duesseldorf.de/vis-api/vis/v1"

GMTN_EDITION = 2027
GIFA_EDITION = GMTN_EDITION
GIFA_EVENT_LABEL = f"GIFA {GIFA_EDITION}"
GIFA_EVENT_ID = f"GMTN{GIFA_EDITION}.gifa"

REQUEST_TIMEOUT = 30
PROFILE_REQUEST_RETRIES = 4
PROFILE_REQUEST_DELAY = 0.25
DIRECTORY_REQUEST_RETRIES = 4
DIRECTORY_REQUEST_DELAY = 0.5

DIRECTORY_LETTERS = "abcdefghijklmnopqrstuvwxyz"

# The four events share the Messe Düsseldorf VIS directory API.  Keeping the
# event-specific values here means the scraper does not need one implementation
# per event.
EVENTS = {
    "GIFA": {
        "base_url": GIFA_BASE_URL,
        "domain": GIFA_DOMAIN,
        "event_code": GIFA_EVENT_ID,
        "event_label": GIFA_EVENT_LABEL,
        "edition": GIFA_EDITION,
        "enrich_profiles": True,
    },
    "METEC": {
        "base_url": GIFA_BASE_URL,
        "domain": "www.metec.com",
        "event_code": f"GMTN{GMTN_EDITION}.metec",
        "event_label": f"METEC {GMTN_EDITION}",
        "edition": GMTN_EDITION,
        "enrich_profiles": True,
    },
    "THERMPROCESS": {
        "base_url": GIFA_BASE_URL,
        "domain": "www.thermprocess-expo.com",
        "event_code": f"GMTN{GMTN_EDITION}.thermpro",
        "event_label": f"THERMPROCESS {GMTN_EDITION}",
        "edition": GMTN_EDITION,
        "enrich_profiles": True,
    },
    "NEWCAST": {
        "base_url": GIFA_BASE_URL,
        "domain": "www.newcast.com",
        "event_code": f"GMTN{GMTN_EDITION}.newcast",
        "event_label": f"NEWCAST {GMTN_EDITION}",
        "edition": GMTN_EDITION,
        "enrich_profiles": True,
    },
}