from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    handler: Callable[..., Any] | None = None


class ToolRegistry:
    def __init__(self, definitions: list[ToolDefinition]) -> None:
        self._definitions = {definition.name: definition for definition in definitions}

    def get(self, name: str) -> ToolDefinition:
        try:
            return self._definitions[name]
        except KeyError as error:
            raise ValueError(f"unregistered agent tool: {name}") from error

    def validate(self, names: list[str]) -> list[ToolDefinition]:
        return [self.get(name) for name in names]

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._definitions))


youtube_tool_registry = ToolRegistry(
    [
        ToolDefinition("youtube.search", "Discover public YouTube videos using Data API v3."),
        ToolDefinition("youtube.get_metadata", "Fetch video metadata using Data API v3."),
        ToolDefinition("youtube.get_comments", "Fetch available public comments."),
        ToolDefinition("youtube.get_caption_tracks", "Check available caption tracks."),
    ]
)
