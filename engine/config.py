from dataclasses import dataclass

@dataclass
class GameConfig:
    num_players: int = 7
    num_impostors: int = 2
    max_total_rounds: int = 60
    kill_cooldown: int = 6
    discussion_rotations: int = 3
    message_char_limit: int = 500
    emergency_meetings_per_player: int = 1
    sabotage_countdown: int = 12
    sabotage_cooldown: int = 8
    sabotage_fix_cost_critical: int = 4
    sabotage_fix_cost_disruptive: int = 3
    tasks_per_crewmate: int = 8
    visual_tasks_per_crewmate: int = 1
    confirm_ejects: bool = True
    ghost_tasks_enabled: bool = True
    agent_timeout_seconds: int = 30
    memory_sighting_cap: int = 20
    memory_movement_cap: int = 15

    def validate(self) -> None:
        assert self.num_players >= 4, "Need at least 4 players"
        assert self.num_impostors >= 1, "Need at least 1 impostor"
        assert self.num_impostors < self.num_players / 2, "Impostors must be less than half"
        assert self.tasks_per_crewmate >= self.visual_tasks_per_crewmate, "Visual tasks can't exceed total tasks"
        assert self.max_total_rounds >= 10, "Game must have at least 10 rounds"

MAP_ADJACENCY: dict[str, list[str]] = {
    "Cafeteria":    ["Medbay", "Admin", "Weapons"],
    "Medbay":       ["Cafeteria", "Upper Engine"],
    "Admin":        ["Cafeteria", "Storage"],
    "Weapons":      ["Cafeteria", "Navigation"],
    "Upper Engine": ["Medbay", "Reactor"],
    "Storage":      ["Admin", "Electrical"],
    "Navigation":   ["Weapons", "Shields"],
    "Reactor":      ["Upper Engine", "Electrical"],
    "Electrical":   ["Storage", "Reactor"],
    "Shields":      ["Navigation"]
}

ALL_ROOMS: list[str] = list(MAP_ADJACENCY.keys())

TASK_POOL: list[dict] = [
    {"name": "Fix Wiring",        "location": "Electrical",   "required": 3, "visual": False},
    {"name": "Divert Power",      "location": "Electrical",   "required": 2, "visual": False},
    {"name": "Upload Data",       "location": "Admin",        "required": 2, "visual": False},
    {"name": "Swipe Card",        "location": "Admin",        "required": 2, "visual": False},
    {"name": "Body Scan",         "location": "Medbay",       "required": 3, "visual": True},
    {"name": "Calibrate Engines", "location": "Upper Engine", "required": 2, "visual": False},
    {"name": "Fuel Engines",      "location": "Upper Engine", "required": 2, "visual": False},
    {"name": "Clear Asteroids",   "location": "Weapons",      "required": 3, "visual": True},
    {"name": "Chart Course",      "location": "Navigation",   "required": 2, "visual": False},
    {"name": "Stabilize Steering","location": "Navigation",   "required": 2, "visual": False},
    {"name": "Prime Shields",     "location": "Shields",      "required": 2, "visual": False},
    {"name": "Align Telescope",   "location": "Shields",      "required": 2, "visual": False},
    {"name": "Clean Filter",      "location": "Storage",      "required": 2, "visual": False},
    {"name": "Fill Canisters",    "location": "Storage",      "required": 2, "visual": False},
    {"name": "Start Reactor",     "location": "Reactor",      "required": 3, "visual": False},
    {"name": "Unlock Manifolds",  "location": "Reactor",      "required": 2, "visual": False}
]

SABOTAGE_DEFINITIONS: dict[str, dict] = {
    "reactor": {"fix_locations": {"Reactor": 4},       "critical": True},
    "o2":      {"fix_locations": {"Admin": 2, "Shields": 2}, "critical": True},
    "lights":  {"fix_locations": {"Electrical": 3},     "critical": False},
    "comms":   {"fix_locations": {"Admin": 3},          "critical": False}
}

VALID_ACTIONS: list[str] = [
    "move", "do_task", "fake_task", "kill", "report",
    "call_emergency", "sabotage", "fix_sabotage", "use_admin", "wait"
]
