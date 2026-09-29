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