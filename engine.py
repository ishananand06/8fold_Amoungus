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

import copy

class ObservationGenerator:
    def __init__(self, state: GameState):
        self.state = state

    def generate_task_observation(self, player_id: str) -> dict:
        player = self.state.players[player_id]
        
        alive = [p.id for p in self.state.players.values() if p.alive]
        dead = [p.id for p in self.state.players.values() if not p.alive and not p.ejected]
        ejected = [p.id for p in self.state.players.values() if p.ejected]

        # Room obs
        if self.state.sabotage and self.state.sabotage.type == SabotageType.LIGHTS and player.role == Role.CREWMATE:
            players_present = []
            bodies_present = []
        else:
            players_present = [
                {"id": p.id, "last_action": p.last_action}
                for p in self.state.players.values()
                if p.id != player_id and p.alive and p.location == player.location
            ]
            bodies_present = [b["player_id"] for b in self.state.bodies if b["location"] == player.location]
        
        from config import MAP_ADJACENCY
        adjacent_rooms = MAP_ADJACENCY.get(player.location, [])

        events_last_round = self.state.events.get(player_id, [])

        # Tasks
        your_tasks = []
        if self.state.sabotage and self.state.sabotage.type == SabotageType.COMMS:
            your_tasks = "disabled"
        else:
            for t in self.state.tasks.get(player_id, []):
                t_dict = {
                    "task_id": t.task_id,
                    "name": t.name,
                    "location": t.location,
                    "progress": t.progress,
                    "required": t.required,
                    "visual": t.visual
                }
                if player.role == Role.IMPOSTOR:
                    t_dict["note"] = "FAKE - use for alibi"
                your_tasks.append(t_dict)

        global_task_progress = self._global_task_progress()

        # Sabotage
        sab_data = None
        if self.state.sabotage:
            sab_data = {
                "type": self.state.sabotage.type.value,
                "countdown": self.state.sabotage.countdown,
                "fix_progress": self.state.sabotage.fix_progress,
                "fix_required": self.state.sabotage.fix_required
            }
        
        # Impostor info
        impostor_info = None
        if player.role == Role.IMPOSTOR:
            impostor_info = {
                "teammates": [p.id for p in self.state.players.values() if p.role == Role.IMPOSTOR and p.id != player_id],
                "kill_cooldown": player.kill_cooldown
            }

        # Admin table
        admin_data = None
        if self.state.admin_table_snapshot and player_id in self.state.admin_table_snapshot:
            admin_data = self.state.admin_table_snapshot[player_id]

        # Available actions
        can_report = len(bodies_present) > 0
        can_emergency = player.location == "Cafeteria" and player.emergency_meetings_remaining > 0 and (not self.state.sabotage or not self.state.sabotage.critical)
        can_kill = player.role == Role.IMPOSTOR and player.kill_cooldown == 0
        can_sabotage = player.role == Role.IMPOSTOR and self.state.sabotage is None and self.state.sabotage_cooldown == 0
        can_fix = self.state.sabotage is not None and player.location in self.state.sabotage.fix_required

        # Previous action
        prev_result = None
        if player_id in self.state.action_results:
            pr = self.state.action_results[player_id]
            prev_result = {"action": pr.action, "success": pr.success, "reason": pr.reason}

        # Memory
        memory_summary = {
            "your_movement_history": self.state.movement_history.get(player_id, []),
            "player_sightings": self.state.sighting_history.get(player_id, []),
            "meetings": self.state.meeting_history
        }

        return {
            "phase": "task",
            "identity": {
                "your_id": player.id,
                "your_role": player.role.value,
                "your_location": player.location
            },
            "players": {"alive": alive, "dead": dead, "ejected": ejected},
            "room_observations": {
                "players_present": players_present,
                "bodies_present": bodies_present,
                "adjacent_rooms": adjacent_rooms
            },
            "events_last_round": events_last_round,
            "tasks": {"your_tasks": your_tasks, "global_task_progress": global_task_progress},
            "sabotage": {
                "active": sab_data,
                "cooldown_remaining": self.state.sabotage_cooldown
            },
            "impostor_info": impostor_info,
            "admin_table_data": admin_data,
            "available_actions": {
                "can_report": can_report,
                "can_emergency": can_emergency,
                "can_kill": can_kill,
                "can_sabotage": can_sabotage,
                "can_fix": can_fix
            },
            "previous_action_result": prev_result,
            "memory_summary": memory_summary,
            "game_metadata": {
                "round_number": self.state.round_number,
                "max_total_rounds": self.state.config.max_total_rounds
            }
        }

    def generate_ghost_observation(self, player_id: str) -> dict:
        player = self.state.players[player_id]
        alive = [p.id for p in self.state.players.values() if p.alive]
        dead = [p.id for p in self.state.players.values() if not p.alive and not p.ejected]
        ejected = [p.id for p in self.state.players.values() if p.ejected]
        
        your_tasks = []
        for t in self.state.tasks.get(player_id, []):
            your_tasks.append({
                "task_id": t.task_id,
                "name": t.name,
                "location": t.location,
                "progress": t.progress,
                "required": t.required,
                "visual": t.visual
            })

        return {
            "phase": "task",
            "identity": {
                "your_id": player.id,
                "your_role": player.role.value,
                "your_location": player.location
            },
            "players": {"alive": alive, "dead": dead, "ejected": ejected},
            "tasks": {"your_tasks": your_tasks, "global_task_progress": self._global_task_progress()},
            "game_metadata": {
                "round_number": self.state.round_number,
                "max_total_rounds": self.state.config.max_total_rounds
            }
        }

    def generate_discussion_observation(self, player_id: str) -> dict:
        player = self.state.players[player_id]
        alive = [p.id for p in self.state.players.values() if p.alive]
        dead = [p.id for p in self.state.players.values() if not p.alive and not p.ejected]
        ejected = [p.id for p in self.state.players.values() if p.ejected]

        return {
            "phase": "discussion",
            "identity": {
                "your_id": player.id,
                "your_role": player.role.value,
                "your_location": player.location
            },
            "players": {"alive": alive, "dead": dead, "ejected": ejected},
            "meeting_context": self.state.meeting_context,
            "chat_history": self.state.chat_history,
            "memory_summary": {
                "your_movement_history": self.state.movement_history.get(player_id, []),
                "player_sightings": self.state.sighting_history.get(player_id, []),
                "meetings": self.state.meeting_history
            },
            "game_metadata": {
                "round_number": self.state.round_number,
                "max_total_rounds": self.state.config.max_total_rounds
            }
        }

    def generate_voting_observation(self, player_id: str) -> dict:
        obs = self.generate_discussion_observation(player_id)
        obs["phase"] = "voting"
        return obs

    def generate_game_start_info(self, player_id: str) -> dict:
        player = self.state.players[player_id]
        impostor_teammates = None
        if player.role == Role.IMPOSTOR:
            impostor_teammates = [p.id for p in self.state.players.values() if p.role == Role.IMPOSTOR and p.id != player_id]
        
        from config import MAP_ADJACENCY, ALL_ROOMS
        return {
            "game_id": "game",
            "your_id": player_id,
            "your_role": player.role.value,
            "impostor_teammates": impostor_teammates,
            "map": {
                "rooms": ALL_ROOMS,
                "adjacency": MAP_ADJACENCY
            },
            "players": list(self.state.players.keys()),
            "tasks": [
                {
                    "task_id": t.task_id,
                    "location": t.location,
                    "required": t.required,
                    "visual": t.visual
                } for t in self.state.tasks.get(player_id, [])
            ],
            "config": {
                "kill_cooldown": self.state.config.kill_cooldown,
                "discussion_rotations": self.state.config.discussion_rotations,
                "max_total_rounds": self.state.config.max_total_rounds,
                "sabotage_countdown": self.state.config.sabotage_countdown,
                "confirm_ejects": self.state.config.confirm_ejects
            }
        }

    def generate_game_end_info(self, player_id: str) -> dict:
        player = self.state.players[player_id]
        return {
            "winner": self.state.winner,
            "cause": self.state.win_cause,
            "all_roles": {p.id: p.role.value for p in self.state.players.values()},
            "final_round": self.state.round_number,
            "your_stats": {
                "survived": player.alive and not player.ejected
            }
        }

    def _global_task_progress(self) -> float:
        total = 0
        done = 0
        for pid, player in self.state.players.items():
            if player.role == Role.CREWMATE:
                for t in self.state.tasks.get(pid, []):
                    total += t.required
                    done += min(t.progress, t.required)
        return done / total if total > 0 else 0.0

