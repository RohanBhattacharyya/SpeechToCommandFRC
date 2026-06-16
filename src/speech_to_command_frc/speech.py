from __future__ import annotations

from dataclasses import dataclass
import json
import queue
import threading
import time
from typing import Callable

from .config import AppConfig
from .matcher import find_command_matches
from .networktables import NetworkTablesPublisher


EventCallback = Callable[[dict], None]


@dataclass
class SpeechStatus:
    listening: bool = False
    message: str = "Idle"
    partial: str = ""
    last_text: str = ""


class SpeechCommandService:
    def __init__(self, publisher: NetworkTablesPublisher, emit: EventCallback) -> None:
        self._publisher = publisher
        self._emit = emit
        self._config = AppConfig.load()
        self._status = SpeechStatus()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_heard: dict[str, float] = {}

    @property
    def config(self) -> AppConfig:
        return self._config

    def update_config(self, config: AppConfig) -> None:
        self._config = config
        self._config.save()
        self._publisher.configure(config)
        self._emit_state()

    def start(self) -> bool:
        if self._thread and self._thread.is_alive():
            return True

        if not self._config.vosk_model_path.strip():
            self._status = SpeechStatus(False, "Choose a Vosk model directory before listening")
            self._emit_state()
            return False

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._status.listening = False
        self._status.message = "Stopped"
        self._emit_state()

    def status(self) -> dict:
        return {
            "listening": self._status.listening,
            "message": self._status.message,
            "partial": self._status.partial,
            "lastText": self._status.last_text,
        }

    def test_transcript(self, text: str) -> list[str]:
        return self._process_text(text)

    def _run(self) -> None:
        audio_queue: queue.Queue[bytes] = queue.Queue()

        try:
            import sounddevice as sd
            from vosk import KaldiRecognizer, Model
        except ImportError as exc:
            self._status = SpeechStatus(False, f"Install dependencies from requirements.txt: {exc}")
            self._emit_state()
            return

        try:
            model = Model(self._config.vosk_model_path)
            grammar = [command.strip().lower() for command in self._config.commands if command.strip()]
            if "[unk]" not in grammar:
                grammar.append("[unk]")
            recognizer = KaldiRecognizer(model, self._config.sample_rate, json.dumps(grammar))
        except Exception as exc:
            self._status = SpeechStatus(False, f"Could not load Vosk model: {exc}")
            self._emit_state()
            return

        def callback(indata, frames, time_info, status) -> None:  # noqa: ANN001
            if status:
                self._status.message = str(status)
            audio_queue.put(bytes(indata))

        self._status = SpeechStatus(True, "Listening")
        self._emit_state()

        try:
            with sd.RawInputStream(
                samplerate=self._config.sample_rate,
                blocksize=8000,
                dtype="int16",
                channels=1,
                callback=callback,
            ):
                while not self._stop_event.is_set():
                    try:
                        data = audio_queue.get(timeout=0.25)
                    except queue.Empty:
                        continue

                    if recognizer.AcceptWaveform(data):
                        payload = json.loads(recognizer.Result())
                        text = str(payload.get("text", "")).strip()
                        if text:
                            self._status.last_text = text
                            self._status.partial = ""
                            self._process_text(text)
                            self._emit_state()
                    else:
                        payload = json.loads(recognizer.PartialResult())
                        partial = str(payload.get("partial", "")).strip()
                        if partial != self._status.partial:
                            self._status.partial = partial
                            self._emit_state()
        except Exception as exc:
            self._status = SpeechStatus(False, f"Audio error: {exc}", last_text=self._status.last_text)
            self._emit_state()
            return

        self._status.listening = False
        self._status.message = "Stopped"
        self._emit_state()

    def _process_text(self, text: str) -> list[str]:
        matches = find_command_matches(text, self._config.commands)
        now = time.monotonic()
        published: list[str] = []

        for match in matches:
            last = self._last_heard.get(match.command, 0.0)
            if now - last < self._config.debounce_seconds:
                continue
            self._last_heard[match.command] = now
            result = self._publisher.publish_command(match.command)
            published.append(match.command)
            self._emit(
                {
                    "type": "heard",
                    "command": match.command,
                    "text": text,
                    "publishOk": result.ok,
                    "publishMessage": result.message,
                    "sequence": result.sequence,
                }
            )

        if not published:
            self._emit({"type": "transcript", "text": text})

        return published

    def _emit_state(self) -> None:
        self._emit({"type": "state", "speech": self.status(), "networkTables": self._publisher.status()})
