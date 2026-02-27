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


class ActionResolver:
    def __init__(self, state: GameState):
        self.state = state

    def resolve_round(self, actions: dict[str, dict]) -> None:
        all_players = list(self.state.players.keys())

        # Step 0: CLEAR transient state
        self.state.events = {pid: [] for pid in all_players}
        self.state.admin_table_snapshot = None
        self.state.admin_table_user = None
        self.state.round_number += 1
        self.state.action_results = {}

        # Step 1: DECREMENT COOLDOWNS
        for p in self.state.players.values():
            if p.role == Role.IMPOSTOR:
                p.kill_cooldown = max(0, p.kill_cooldown - 1)
        self.state.sabotage_cooldown = max(0, self.state.sabotage_cooldown - 1)

        # Step 2: TICK SABOTAGE COUNTDOWN
        if self.state.sabotage and self.state.sabotage.critical:
            if self.state.sabotage.countdown is not None:
                self.state.sabotage.countdown -= 1
                if self.state.sabotage.countdown <= 0:
                    self.state.winner = "impostors"
                    self.state.win_cause = f"sabotage_{self.state.sabotage.type.value}"
                    self.state.phase = Phase.GAME_OVER
                    return

        # Step 3: VALIDATE ALL ACTIONS
        validated_actions = {}
        for pid, action in actions.items():
            result = self._validate(pid, action)
            self.state.action_results[pid] = result
            if not result.success:
                validated_actions[pid] = {"action": "wait", "target": None}
            else:
                validated_actions[pid] = action
        
        # Add wait for missing players
        for pid in all_players:
            if pid not in validated_actions:
                validated_actions[pid] = {"action": "wait", "target": None}
                self.state.action_results[pid] = ActionResult("wait", True)

        # Step 4: RESOLVE MOVEMENT
        moves = []
        for pid, action in validated_actions.items():
            if action.get("action") == "move":
                moves.append((pid, self.state.players[pid].location, action.get("target")))
                self.state.players[pid].last_action = "moving"
        
        for pid, origin, target in moves:
            self.state.players[pid].location = target
            for other_p in self.state.players.values():
                if other_p.id != pid and other_p.alive:
                    if other_p.location == origin and other_p.id not in [m[0] for m in moves]:
                        self.state.events[other_p.id].append(f"{pid} left toward {target}")
                    elif other_p.location == target and other_p.id not in [m[0] for m in moves]:
                        self.state.events[other_p.id].append(f"{pid} arrived from {origin}")

        for i, (pid1, orig1, tgt1) in enumerate(moves):
            for pid2, orig2, tgt2 in moves[i+1:]:
                if orig1 == tgt2 and tgt1 == orig2:
                    self.state.events[pid1].append(f"You passed {pid2} between {orig1} and {tgt1}")
                    self.state.events[pid2].append(f"You passed {pid1} between {orig2} and {tgt2}")
            
            hist = self.state.movement_history.setdefault(pid1, [])
            hist.append({"round": self.state.round_number, "location": tgt1})
            if len(hist) > self.state.config.memory_movement_cap:
                self.state.movement_history[pid1] = hist[-self.state.config.memory_movement_cap:]

        # Step 5: RESOLVE KILLS
        kill_actions = sorted([pid for pid, act in validated_actions.items() if act.get("action") == "kill"])
        for pid in kill_actions:
            killer = self.state.players[pid]
            target_id = validated_actions[pid].get("target")
            target = self.state.players.get(target_id)
            if target and target.alive and target.location == killer.location:
                target.alive = False
                self.state.bodies.append({"player_id": target_id, "location": target.location})
                killer.kill_cooldown = self.state.config.kill_cooldown
                self.state.action_results[pid].success = True
                
                for w in self.state.players.values():
                    blinded = self.state.sabotage and self.state.sabotage.type == SabotageType.LIGHTS and w.role == Role.CREWMATE
                    if w.alive and w.location == killer.location and not blinded and w.id != killer.id and w.id != target.id:
                        self.state.events[w.id].append(f"{target_id} was killed!")
            else:
                self.state.action_results[pid].success = False
                self.state.action_results[pid].reason = f"Target {target_id} is not in your room after movement resolved or is dead."

        if self._check_win_condition(): return

        # Step 6: RESOLVE TASKS
        for pid, action in validated_actions.items():
            act_type = action.get("action")
            if act_type == "do_task":
                p = self.state.players[pid]
                tid = action.get("target")
                task = next((t for t in self.state.tasks.get(pid, []) if t.task_id == tid), None)
                if task:
                    task.progress += 1
                    p.last_action = "doing_task"
                    if task.completed and task.visual:
                        for w in self.state.players.values():
                            blinded = self.state.sabotage and self.state.sabotage.type == SabotageType.LIGHTS and w.role == Role.CREWMATE
                            if w.alive and w.location == p.location and not blinded and w.id != p.id:
                                self.state.events[w.id].append(f"{pid} completed visual task {task.name} in {p.location}")
            elif act_type == "fake_task":
                self.state.players[pid].last_action = "doing_task"

        if self._check_win_condition(): return

        # Step 7: RESOLVE REPORTS AND EMERGENCY MEETINGS
        reports = sorted([pid for pid, act in validated_actions.items() if act.get("action") == "report"])
        emergencies = sorted([pid for pid, act in validated_actions.items() if act.get("action") == "call_emergency"])
        
        meeting_trigger = None
        caller = None
        body_found = None
        
        if reports:
            caller = reports[0]
            meeting_trigger = "body_report"
            room = self.state.players[caller].location
            for b in self.state.bodies:
                if b["location"] == room:
                    body_found = b
                    break
        elif emergencies:
            caller = emergencies[0]
            meeting_trigger = "emergency_meeting"
            self.state.players[caller].emergency_meetings_remaining -= 1

        if meeting_trigger:
            self.state.meeting_context = {
                "trigger": meeting_trigger,
                "called_by": caller,
                "body_found": body_found["player_id"] if body_found else None,
                "body_location": body_found["location"] if body_found else None
            }
            self.state.phase = Phase.DISCUSSION
            for other in reports + emergencies:
                if other != caller:
                    self.state.action_results[other].success = False
                    self.state.action_results[other].reason = "Meeting was triggered by another player this round."
            return # STOP RESOLUTION

        # Step 8: RESOLVE SABOTAGE TRIGGERS
        sabotages = sorted([pid for pid, act in validated_actions.items() if act.get("action") == "sabotage"])
        if sabotages and self.state.sabotage is None:
            pid = sabotages[0]
            sab_name = validated_actions[pid].get("target")
            from config import SABOTAGE_DEFINITIONS
            if sab_name in SABOTAGE_DEFINITIONS:
                sdef = SABOTAGE_DEFINITIONS[sab_name]
                sab_type = SabotageType(sab_name)
                countdown = self.state.config.sabotage_countdown if sdef["critical"] else None
                self.state.sabotage = ActiveSabotage(
                    type=sab_type,
                    critical=sdef["critical"],
                    countdown=countdown,
                    fix_progress={k: 0 for k in sdef["fix_locations"]},
                    fix_required=sdef["fix_locations"].copy()
                )

        # Step 9: RESOLVE FIX ACTIONS
        for pid, action in validated_actions.items():
            if action.get("action") == "fix_sabotage":
                p = self.state.players[pid]
                p.last_action = "fixing"
                if self.state.sabotage and p.location in self.state.sabotage.fix_progress:
                    self.state.sabotage.fix_progress[p.location] += 1
        
        if self.state.sabotage:
            resolved = True
            for loc, req in self.state.sabotage.fix_required.items():
                if self.state.sabotage.fix_progress.get(loc, 0) < req:
                    resolved = False
                    break
            if resolved:
                self.state.sabotage = None
                self.state.sabotage_cooldown = self.state.config.sabotage_cooldown

        # Step 10: RESOLVE ADMIN TABLE
        admin_users = [pid for pid, act in validated_actions.items() if act.get("action") == "use_admin"]
        if admin_users:
            from config import MAP_ADJACENCY
            counts = {r: 0 for r in MAP_ADJACENCY.keys()}
            for p in self.state.players.values():
                if p.alive:
                    counts[p.location] = counts.get(p.location, 0) + 1
            if self.state.admin_table_snapshot is None:
                self.state.admin_table_snapshot = {}
            for pid in admin_users:
                self.state.players[pid].last_action = "admin"
                self.state.admin_table_snapshot[pid] = counts.copy()

        # Step 11: UPDATE REMAINING last_action
        for pid, action in validated_actions.items():
            act = action.get("action")
            if act in ("wait", "report", "call_emergency", "sabotage"):
                self.state.players[pid].last_action = "idle"

        # Step 12: UPDATE SIGHTING HISTORY
        for p in self.state.players.values():
            if not p.alive: continue
            blinded = self.state.sabotage and self.state.sabotage.type == SabotageType.LIGHTS and p.role == Role.CREWMATE
            if blinded: continue
            for other_p in self.state.players.values():
                if other_p.id != p.id and other_p.alive and other_p.location == p.location:
                    hist = self.state.sighting_history.setdefault(p.id, [])
                    hist.append({
                        "round": self.state.round_number,
                        "player": other_p.id,
                        "location": p.location,
                        "action": other_p.last_action
                    })
                    if len(hist) > self.state.config.memory_sighting_cap:
                        self.state.sighting_history[p.id] = hist[-self.state.config.memory_sighting_cap:]

        # Step 13: LOG ROUND (minimalist placeholder)
        self.state.game_log.append({
            "round": self.state.round_number,
            "actions": validated_actions,
            "results": {pid: {"success": r.success, "reason": r.reason} for pid, r in self.state.action_results.items()}
        })

        self._check_win_condition()

    def _validate(self, player_id: str, action: dict) -> ActionResult:
        if not isinstance(action, dict) or "action" not in action:
            return ActionResult(action.get("action", "wait") if isinstance(action, dict) else "wait", False, "Malformed action")
        
        act = action.get("action")
        p = self.state.players.get(player_id)
        if not p: return ActionResult(act, False, "Player not found")
        
        if act == "wait":
            return ActionResult(act, True)
            
        if not p.alive:
            if act == "move":
                from config import MAP_ADJACENCY
                if action.get("target") in MAP_ADJACENCY.get(p.location, []):
                    return ActionResult(act, True)
                return ActionResult(act, False, "Invalid move target")
            if act == "do_task" and p.role == Role.CREWMATE and self.state.config.ghost_tasks_enabled:
                tid = action.get("target")
                task = next((t for t in self.state.tasks.get(player_id, []) if t.task_id == tid), None)
                if task and not task.completed and task.location == p.location:
                    return ActionResult(act, True)
                return ActionResult(act, False, "Invalid task or location")
            return ActionResult(act, False, "Ghosts can only move or do tasks")

        from config import MAP_ADJACENCY, SABOTAGE_DEFINITIONS
        if act == "move":
            if action.get("target") in MAP_ADJACENCY.get(p.location, []):
                return ActionResult(act, True)
            return ActionResult(act, False, "Invalid move target")
        
        if act == "do_task":
            if p.role != Role.CREWMATE: return ActionResult(act, False, "Only crewmates do tasks")
            tid = action.get("target")
            task = next((t for t in self.state.tasks.get(player_id, []) if t.task_id == tid), None)
            if not task: return ActionResult(act, False, "Task not found")
            if task.completed: return ActionResult(act, False, "Task already complete")
            if task.location != p.location: return ActionResult(act, False, "Wrong room for task")
            return ActionResult(act, True)
            
        if act == "fake_task":
            if p.role != Role.IMPOSTOR: return ActionResult(act, False, "Only impostors can fake tasks")
            return ActionResult(act, True)
            
        if act == "kill":
            if p.role != Role.IMPOSTOR: return ActionResult(act, False, "Only impostors can kill")
            if p.kill_cooldown > 0: return ActionResult(act, False, "Kill cooldown active")
            tgt_id = action.get("target")
            tgt = self.state.players.get(tgt_id)
            if not tgt or not tgt.alive: return ActionResult(act, False, "Invalid target")
            if tgt.role == Role.IMPOSTOR: return ActionResult(act, False, "Cannot kill teammate")
            return ActionResult(act, True)
            
        if act == "report":
            if any(b["location"] == p.location for b in self.state.bodies):
                return ActionResult(act, True)
            return ActionResult(act, False, "No body to report")
            
        if act == "call_emergency":
            if p.location != "Cafeteria": return ActionResult(act, False, "Must be in Cafeteria")
            if p.emergency_meetings_remaining <= 0: return ActionResult(act, False, "No meetings left")
            if self.state.sabotage and self.state.sabotage.critical: return ActionResult(act, False, "Critical sabotage active")
            return ActionResult(act, True)
            
        if act == "sabotage":
            if p.role != Role.IMPOSTOR: return ActionResult(act, False, "Only impostors can sabotage")
            if self.state.sabotage is not None: return ActionResult(act, False, "Sabotage already active")
            if self.state.sabotage_cooldown > 0: return ActionResult(act, False, "Sabotage cooldown active")
            if action.get("target") not in SABOTAGE_DEFINITIONS: return ActionResult(act, False, "Invalid sabotage")
            return ActionResult(act, True)
            
        if act == "fix_sabotage":
            if not self.state.sabotage: return ActionResult(act, False, "No active sabotage")
            if p.location not in self.state.sabotage.fix_required: return ActionResult(act, False, "Wrong room to fix")
            return ActionResult(act, True)
            
        if act == "use_admin":
            if p.location != "Admin": return ActionResult(act, False, "Must be in Admin")
            return ActionResult(act, True)
            
        return ActionResult(act, False, "Unknown action")

    def _check_win_condition(self) -> bool:
        if self.state.winner: return True
        living_crewmates = sum(1 for p in self.state.players.values() if p.role == Role.CREWMATE and p.alive)
        living_impostors = sum(1 for p in self.state.players.values() if p.role == Role.IMPOSTOR and p.alive)
        
        if living_impostors == 0:
            self.state.winner = "crewmates"
            self.state.win_cause = "all_impostors_eliminated"
            self.state.phase = Phase.GAME_OVER
            return True
            
        if living_impostors >= living_crewmates:
            self.state.winner = "impostors"
            self.state.win_cause = "impostors_majority"
            self.state.phase = Phase.GAME_OVER
            return True
            
        if self.state.sabotage and self.state.sabotage.critical and self.state.sabotage.countdown is not None and self.state.sabotage.countdown <= 0:
            self.state.winner = "impostors"
            self.state.win_cause = f"sabotage_{self.state.sabotage.type.value}"
            self.state.phase = Phase.GAME_OVER
            return True

        # Need to re-import ObservationGenerator safely if used here, or use the helper 
        total = 0
        done = 0
        for pid, p in self.state.players.items():
            if p.role == Role.CREWMATE:
                for t in self.state.tasks.get(pid, []):
                    total += t.required
                    done += min(t.progress, t.required)
        global_prog = done / total if total > 0 else 0.0
        
        if global_prog >= 1.0:
            self.state.winner = "crewmates"
            self.state.win_cause = "all_tasks_completed"
            self.state.phase = Phase.GAME_OVER
            return True
            
        if self.state.round_number >= self.state.config.max_total_rounds:
            self.state.winner = "crewmates"
            self.state.win_cause = "timeout"
            self.state.phase = Phase.GAME_OVER
            return True
            
        return False
