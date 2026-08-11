"""Default PantryPilot configuration."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "instance" / "pantrypilot.db"
BACKUP_DIRECTORY = BASE_DIR / "instance" / "backups"
RESTOCK_THRESHOLD = 1
PDF_FONT_SIZE = 12


class Config:
    SECRET_KEY = "dev-change-me"
    DATABASE = str(DATABASE_PATH)
    RESTOCK_THRESHOLD = RESTOCK_THRESHOLD
    PDF_FONT_SIZE = PDF_FONT_SIZE


class TestConfig(Config):
    TESTING = True
