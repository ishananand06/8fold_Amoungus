import pygame
import json
import sys
import math
import time
from pathlib import Path

# --- Constants & Styling ---
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60

COLORS = {
    "space": (5, 8, 15),
    "panel": (20, 25, 35),
    "border": (50, 60, 80),
    "accent": (0, 212, 255),
    "crewmate": (0, 255, 255),
    "impostor": (255, 62, 62),
    "dead": (80, 80, 80),
    "text": (220, 220, 220),
    "sabotage": (255, 215, 0),
    "body": (255, 0, 0),
    "white": (255, 255, 255)
}

ROOM_POSITIONS = {
    "Cafeteria": (640, 100),
    "Medbay": (340, 200),
    "Admin": (640, 200),
    "Weapons": (940, 200),
    "Upper Engine": (340, 380),
    "Storage": (640, 380),
    "Navigation": (940, 380),
    "Reactor": (340, 560),
    "Electrical": (640, 560),
    "Shields": (940, 560)
}

ADJACENCY = {
    "Cafeteria": ["Medbay", "Admin", "Weapons"],
    "Medbay": ["Cafeteria", "Upper Engine"],
    "Admin": ["Cafeteria", "Storage"],
    "Weapons": ["Cafeteria", "Navigation"],
    "Upper Engine": ["Medbay", "Reactor"],
    "Storage": ["Admin", "Electrical"],
    "Navigation": ["Weapons", "Shields"],
    "Reactor": ["Upper Engine", "Electrical"],
    "Electrical": ["Storage", "Reactor"],
    "Shields": ["Navigation"]
}

class ReplayTheater:
    def __init__(self, log_path):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Among Us LLM Replay Theater")
        self.clock = pygame.time.Clock()
        self.font_main = pygame.font.SysFont("Segoe UI", 24, bold=True)
        self.font_small = pygame.font.SysFont("Consolas", 14)
        self.font_ui = pygame.font.SysFont("Segoe UI", 16)
        
        self.load_log(log_path)
        
        self.current_round_idx = 0
        self.total_rounds = len(self.game_log)
        self.is_playing = False
        self.play_speed = 1.0 
        self.last_round_time = 0
        
        self.player_lerp = 1.0 
        self.prev_positions = {}
        self.target_positions = {}
        
        self.running = True
        self.init_positions()

    def load_log(self, path):
        with open(path, 'r') as f:
            data = json.load(f)
        self.game_log = data.get("game_log", [])
        self.all_roles = data.get("all_roles", {})
        self.meeting_history = data.get("meeting_history", [])
        self.winner = data.get("winner")
        self.cause = data.get("cause")

    def init_positions(self):
        state = self.game_log[0].get("state", {})
        locs = state.get("player_locations", {})
        for pid, room in locs.items():
            self.prev_positions[pid] = ROOM_POSITIONS[room]
            self.target_positions[pid] = ROOM_POSITIONS[room]

    def update_animation_targets(self):
        self.prev_positions = self.target_positions.copy()
        state = self.game_log[self.current_round_idx].get("state", {})
        locs = state.get("player_locations", {})
        for pid, room in locs.items():
            base_pos = ROOM_POSITIONS[room]
            idx = int(pid.split('_')[1]) if '_' in pid else 0
            offset_x = (idx % 3 - 1) * 25
            offset_y = (idx // 3) * 25 + 20
            self.target_positions[pid] = (base_pos[0] + offset_x, base_pos[1] + offset_y)
        self.player_lerp = 0.0

    def draw_rounded_rect(self, rect, color, radius=10, width=0):
        pygame.draw.rect(self.screen, color, rect, width, border_radius=radius)

    def draw_map(self):
        for room, neighbors in ADJACENCY.items():
            start = ROOM_POSITIONS[room]
            for n in neighbors:
                pygame.draw.line(self.screen, COLORS["border"], start, ROOM_POSITIONS[n], 2)

        state = self.game_log[self.current_round_idx].get("state", {})
        sab = state.get("sabotage")
        active_sab_rooms = sab.get("fix_progress", {}).keys() if sab else []

        for name, pos in ROOM_POSITIONS.items():
            rect = pygame.Rect(pos[0]-70, pos[1]-40, 140, 80)
            if name in active_sab_rooms:
                pygame.draw.rect(self.screen, COLORS["sabotage"], rect.inflate(10, 10), 2, border_radius=12)
            self.draw_rounded_rect(rect, COLORS["panel"])
            self.draw_rounded_rect(rect, COLORS["border"], width=2)
            text = self.font_small.render(name.upper(), True, COLORS["accent"])
            self.screen.blit(text, (pos[0] - text.get_width()//2, pos[1] - 30))
            bodies = [b for b in state.get("bodies", []) if b["location"] == name]
            if bodies:
                pygame.draw.circle(self.screen, COLORS["body"], (pos[0], pos[1] + 15), 10)
                mark = self.font_small.render("!", True, COLORS["white"])
                self.screen.blit(mark, (pos[0]-3, pos[1]+7))

    def draw_players(self):
        state = self.game_log[self.current_round_idx].get("state", {})
        alive_players = state.get("alive_players", [])
        for pid in self.target_positions.keys():
            p1 = self.prev_positions.get(pid, self.target_positions[pid])
            p2 = self.target_positions[pid]
            curr_x = p1[0] + (p2[0] - p1[0]) * self.player_lerp
            curr_y = p1[1] + (p2[1] - p1[1]) * self.player_lerp
            color = COLORS["crewmate"] if self.all_roles.get(pid) == "crewmate" else COLORS["impostor"]
            is_alive = pid in alive_players
            draw_color = color if is_alive else COLORS["dead"]
            pygame.draw.rect(self.screen, draw_color, (curr_x-18, curr_y-8, 10, 16))
            pygame.draw.circle(self.screen, draw_color, (int(curr_x), int(curr_y)), 12)
            pygame.draw.circle(self.screen, COLORS["white"] if is_alive else (100,100,100), (int(curr_x), int(curr_y)), 12, 2)
            lbl = self.font_small.render(pid, True, COLORS["white"])
            self.screen.blit(lbl, (curr_x - lbl.get_width()//2, curr_y + 15))

    def draw_ui(self):
        panel_rect = pygame.Rect(SCREEN_WIDTH - 300, 0, 300, SCREEN_HEIGHT)
        pygame.draw.rect(self.screen, COLORS["panel"], panel_rect)
        pygame.draw.line(self.screen, COLORS["border"], (SCREEN_WIDTH-300, 0), (SCREEN_WIDTH-300, SCREEN_HEIGHT), 2)
        title = self.font_main.render("MISSION LOG", True, COLORS["accent"])
        self.screen.blit(title, (SCREEN_WIDTH - 280, 20))
        r_num = self.game_log[self.current_round_idx].get("round", self.current_round_idx + 1)
        rnd_text = self.font_main.render(f"ROUND {r_num:02d}", True, COLORS["white"])
        self.screen.blit(rnd_text, (20, 20))
        actions = self.game_log[self.current_round_idx].get("actions", {})
        results = self.game_log[self.current_round_idx].get("results", {})
        y_off = 70
        for pid in sorted(actions.keys()):
            act = actions[pid].get("action", "wait")
            res = results.get(pid, {}).get("success", False)
            color = COLORS["accent"] if res else (150, 150, 150)
            txt = self.font_small.render(f"{pid}: {act}", True, color)
            self.screen.blit(txt, (SCREEN_WIDTH - 280, y_off))
            y_off += 20
            if y_off > SCREEN_HEIGHT - 50: break
        hint = self.font_small.render("SPACE: Play/Pause | LEFT/RIGHT: Seek | +/-: Speed", True, (100, 100, 100))
        self.screen.blit(hint, (20, SCREEN_HEIGHT - 30))

    def draw_meeting(self, meeting):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 230))
        self.screen.blit(overlay, (0,0))
        title = self.font_main.render(f"--- EMERGENCY MEETING: ROUND {meeting['round_called']} ---", True, COLORS["impostor"])
        self.screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 50))
        y = 110
        transcript = meeting.get("transcript", [])
        # Show more messages (up to 18)
        for msg in transcript[-18:]:
            color = COLORS["crewmate"] if self.all_roles.get(msg['speaker']) == "crewmate" else COLORS["impostor"]
            txt = self.font_small.render(f"{msg['speaker']}: {msg['message'][:100]}", True, color)
            self.screen.blit(txt, (SCREEN_WIDTH//2 - 500, y))
            y += 22
        res_text = f"RESULT: {meeting['voted_out']} EJECTED ({meeting.get('role_revealed')})" if meeting['voted_out'] else "RESULT: SKIP"
        res_render = self.font_main.render(res_text, True, COLORS["sabotage"])
        self.screen.blit(res_render, (SCREEN_WIDTH//2 - res_render.get_width()//2, SCREEN_HEIGHT - 80))

    def run_theater(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT: self.running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE: self.is_playing = not self.is_playing
                    if event.key == pygame.K_RIGHT:
                        self.current_round_idx = min(self.total_rounds - 1, self.current_round_idx + 1)
                        self.update_animation_targets()
                    if event.key == pygame.K_LEFT:
                        self.current_round_idx = max(0, self.current_round_idx - 1)
                        self.update_animation_targets()
                    if event.key == pygame.K_EQUALS: self.play_speed = max(0.1, self.play_speed - 0.2)
                    if event.key == pygame.K_MINUS: self.play_speed = min(3.0, self.play_speed + 0.2)
            if self.is_playing:
                self.player_lerp = min(1.0, self.player_lerp + dt * (1.0 / self.play_speed))
                if self.player_lerp >= 1.0:
                    if time.time() - self.last_round_time > self.play_speed:
                        if self.current_round_idx < self.total_rounds - 1:
                            self.current_round_idx += 1
                            self.update_animation_targets()
                            self.last_round_time = time.time()
                        else: self.is_playing = False
            self.screen.fill(COLORS["space"])
            self.draw_map()
            self.draw_players()
            self.draw_ui()
            r_num = self.game_log[self.current_round_idx].get("round", self.current_round_idx + 1)
            meeting = next((m for m in self.meeting_history if m["round_called"] == r_num), None)
            if meeting and self.player_lerp >= 1.0:
                self.draw_meeting(meeting)
                if self.is_playing: self.last_round_time = time.time() + 1.5 
            pygame.display.flip()
        pygame.quit()

if __name__ == "__main__":
    if len(sys.argv) < 2: print("Usage: python replay_theater.py <path_to_log.json>")
    else:
        theater = ReplayTheater(sys.argv[1])
        theater.run_theater()
