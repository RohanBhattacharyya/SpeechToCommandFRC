from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any


CONFIG_DIR = Path.home() / ".speech_to_command_frc"
CONFIG_PATH = CONFIG_DIR / "config.json"


@dataclass
class AppConfig:
    commands: list[str] = field(default_factory=lambda: ["move", "move diagonally", "stop"])
    team_number: int = 0
    server: str = ""
    table_name: str = "SpeechToCommand"
    command_key: str = "command"
    sequence_key: str = "sequence"
    heard_at_key: str = "heardAt"
    connected_key: str = "connected"
    vosk_model_path: str = ""
    sample_rate: int = 16000
    debounce_seconds: float = 1.5

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "AppConfig":
        if not path.exists():
            return cls()

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()

        defaults = asdict(cls())
        clean: dict[str, Any] = {**defaults, **{k: v for k, v in data.items() if k in defaults}}
        clean["commands"] = [str(command).strip() for command in clean.get("commands", []) if str(command).strip()]
        return cls(**clean)

    def save(self, path: Path = CONFIG_PATH) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
