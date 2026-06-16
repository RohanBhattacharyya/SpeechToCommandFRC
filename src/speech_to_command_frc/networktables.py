from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

from .config import AppConfig


@dataclass
class PublishResult:
    ok: bool
    message: str
    sequence: int = 0


class NetworkTablesPublisher:
    def __init__(self) -> None:
        self._ntcore: Any = None
        self._inst: Any = None
        self._table: Any = None
        self._config: AppConfig | None = None
        self._sequence = 0
        self._status = "NetworkTables not started"

    def configure(self, config: AppConfig) -> PublishResult:
        self._config = config

        try:
            from ntcore import NetworkTableInstance
        except ImportError as exc:
            self._status = f"Install robotpy-ntcore to publish to the robot: {exc}"
            return PublishResult(False, self._status, self._sequence)

        self._ntcore = NetworkTableInstance
        self._inst = NetworkTableInstance.getDefault()
        self._inst.stopClient()
        self._inst.startClient4("SpeechToCommandFRC")

        server = config.server.strip()
        if server:
            self._inst.setServer(server)
            self._status = f"Connecting to {server}"
        elif config.team_number > 0:
            self._inst.setServerTeam(config.team_number)
            self._status = f"Connecting to team {config.team_number}"
        else:
            self._status = "Set a team number or server address to publish to NetworkTables"

        self._table = self._inst.getTable(config.table_name.strip() or "SpeechToCommand")
        self._table.putBoolean(config.connected_key, True)
        return PublishResult(True, self._status, self._sequence)

    def publish_command(self, command: str) -> PublishResult:
        if not self._config:
            return PublishResult(False, "NetworkTables has not been configured", self._sequence)
        if not self._table:
            return PublishResult(False, "NetworkTables table is unavailable", self._sequence)

        self._sequence += 1
        self._table.putString(self._config.command_key, command)
        self._table.putNumber(self._config.sequence_key, self._sequence)
        self._table.putNumber(self._config.heard_at_key, time.time())
        self._table.putBoolean(self._config.connected_key, True)
        return PublishResult(True, f"Published {command}", self._sequence)

    def status(self) -> dict[str, Any]:
        connected = False
        if self._inst is not None:
            try:
                connected = bool(self._inst.isConnected())
            except Exception:
                connected = False
        return {
            "connected": connected,
            "sequence": self._sequence,
            "message": self._status,
        }

    def close(self) -> None:
        if self._table is not None and self._config is not None:
            try:
                self._table.putBoolean(self._config.connected_key, False)
            except Exception:
                pass
