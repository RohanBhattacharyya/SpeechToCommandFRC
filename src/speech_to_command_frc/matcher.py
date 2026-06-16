from __future__ import annotations

from dataclasses import dataclass
import re


WORD_RE = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?")


@dataclass(frozen=True)
class CommandMatch:
    command: str
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start


def normalize_tokens(text: str) -> tuple[str, ...]:
    return tuple(match.group(0) for match in WORD_RE.finditer(text.lower()))


def find_command_matches(transcript: str, commands: list[str]) -> list[CommandMatch]:
    transcript_tokens = normalize_tokens(transcript)
    if not transcript_tokens:
        return []

    raw_matches: list[CommandMatch] = []
    normalized_commands: list[tuple[str, tuple[str, ...]]] = []
    seen: set[tuple[str, ...]] = set()

    for command in commands:
        clean_command = command.strip()
        command_tokens = normalize_tokens(clean_command)
        if not clean_command or not command_tokens or command_tokens in seen:
            continue
        seen.add(command_tokens)
        normalized_commands.append((clean_command, command_tokens))

    for command, command_tokens in normalized_commands:
        width = len(command_tokens)
        for start in range(0, len(transcript_tokens) - width + 1):
            end = start + width
            if transcript_tokens[start:end] == command_tokens:
                raw_matches.append(CommandMatch(command=command, start=start, end=end))

    raw_matches.sort(key=lambda match: (-match.length, match.start, match.command.lower()))

    selected: list[CommandMatch] = []
    occupied: set[int] = set()
    for match in raw_matches:
        span = set(range(match.start, match.end))
        if occupied.isdisjoint(span):
            selected.append(match)
            occupied.update(span)

    return sorted(selected, key=lambda match: match.start)
