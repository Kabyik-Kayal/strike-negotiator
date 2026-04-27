from functools import lru_cache
from pathlib import Path
import os


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_HASH_SALT = "dev-salt-change-me"


class Settings:
    def __init__(self) -> None:
        self.data_dir = Path(os.getenv("STRIKE_DATA_DIR", ROOT_DIR / "data"))
        self.audio_dir = Path(os.getenv("STRIKE_AUDIO_DIR", self.data_dir / "audio"))
        self.database_url = os.getenv(
            "STRIKE_DB_URL",
            f"sqlite:///{self.data_dir / 'strike.db'}",
        )
        self.hash_salt = os.getenv("STRIKE_HASH_SALT")
        if not self.hash_salt or self.hash_salt == DEFAULT_HASH_SALT:
            raise RuntimeError(
                "STRIKE_HASH_SALT must be set to a non-default value before startup."
            )
        self.max_audio_bytes = int(os.getenv("STRIKE_MAX_AUDIO_BYTES", str(15 * 1024 * 1024)))

    def ensure_runtime_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
