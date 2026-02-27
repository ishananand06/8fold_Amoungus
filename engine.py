from enum import Enum
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Any

from config import GameConfig

class Role(Enum):
    CREWMATE = "crewmate"
    IMPOSTOR = "impostor"

class Phase(Enum):
    TASK = "task"
    DISCUSSION = "discussion"
    VOTING = "voting"
    GAME_OVER = "game_over"

class SabotageType(Enum):
    REACTOR = "reactor"
    O2 = "o2"
    LIGHTS = "lights"
    COMMS = "comms"

@dataclass
class Player:
    id: str
    role: Role
    alive: bool = True
    ejected: bool = False
    location: str = "Cafeteria"
    emergency_meetings_remaining: int = 1
    kill_cooldown: int = 0
    last_action: str = "wait"

@dataclass
class Task:
    task_id: str
    name: str
    location: str
    required: int
    progress: int = 0
    visual: bool = False

    @property
    def completed(self) -> bool:
        return self.progress >= self.required

@dataclass
class ActiveSabotage:
    type: SabotageType
    critical: bool
    countdown: int | None
    fix_progress: dict[str, int]
    fix_required: dict[str, int]

@dataclass
class ActionResult:
    action: str
    success: bool
    reason: str | None = None

@dataclass
class GameState:
    config: GameConfig
    phase: Phase = Phase.TASK
    round_number: int = 0
    winner: str | None = None
    win_cause: str | None = None

    players: dict[str, Player] = field(default_factory=dict)
    tasks: dict[str, list[Task]] = field(default_factory=dict)

    bodies: list[dict] = field(default_factory=list)
    sabotage: ActiveSabotage | None = None
    sabotage_cooldown: int = 0

    meeting_context: dict | None = None
    chat_history: list[dict] = field(default_factory=list)
    discussion_speaker_order: list[str] = field(default_factory=list)

    events: dict[str, list[str]] = field(default_factory=dict)
    admin_table_snapshot: dict[str, dict[str, int]] | None = None
    admin_table_user: str | None = None
    action_results: dict[str, ActionResult] = field(default_factory=dict)

    movement_history: dict[str, list[dict]] = field(default_factory=dict)
    sighting_history: dict[str, list[dict]] = field(default_factory=dict)
    meeting_history: list[dict] = field(default_factory=list)

    game_log: list[dict] = field(default_factory=list)

class BaseAgent(ABC):
    @abstractmethod
    def on_game_start(self, game_config: dict) -> None:
        pass

    @abstractmethod
    def on_task_phase(self, observation: dict) -> dict:
        pass

    @abstractmethod
    def on_discussion(self, observation: dict) -> str:
        pass

    @abstractmethod
    def on_vote(self, observation: dict) -> str:
        pass

    @abstractmethod
    def on_game_end(self, result: dict) -> None:
        pass
