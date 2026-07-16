import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    required = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise ValueError(f"Missing database environment variables: {', '.join(missing)}")

    return (
        f"postgresql://{os.environ['DB_USER']}:{quote_plus(os.environ['DB_PASSWORD'])}"
        f"@{os.environ['DB_HOST']}:{os.getenv('DB_PORT', '5432')}/{os.environ['DB_NAME']}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply Yoyo migrations using environment configuration.",
        epilog="Run from the repository root: python scripts/migrate.py",
    )
    parser.add_argument("--database-url", help="Override DATABASE_URL and DB_* environment variables.")
    args = parser.parse_args()

    load_dotenv(ROOT_DIR / ".env")
    database_url = args.database_url or get_database_url()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "yoyo",
            "apply",
            "--config",
            str(ROOT_DIR / "yoyo.ini"),
            "--database",
            database_url,
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
