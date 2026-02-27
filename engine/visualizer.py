import tkinter as tk
from tkinter import ttk, filedialog
import json
import sys
from pathlib import Path

# Map Layout Constants (X, Y coordinates for rooms)
ROOM_COORDS = {
    "Cafeteria": (400, 100),
    "Medbay": (200, 200),
    "Admin": (400, 200),
    "Weapons": (600, 200),
    "Upper Engine": (200, 350),
    "Storage": (400, 350),
    "Navigation": (600, 350),
    "Reactor": (200, 500),
    "Electrical": (400, 500),
    "Shields": (600, 500)
}

# Room Adjacency for drawing connections
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

class AmongUsVisualizer:
    def __init__(self, root):
        self.root = root
        self.root.title("Among Us LLM Replay Visualizer")
        self.root.geometry("1200x800")
        
        self.game_data = None
        self.current_round = 0
        self.max_rounds = 0
        
        self._setup_ui()
        
    def _setup_ui(self):
        # Top Panel
        top_frame = ttk.Frame(self.root)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        
        self.load_btn = ttk.Button(top_frame, text="Load Game Log", command=self.load_file)
        self.load_btn.pack(side=tk.LEFT)
        
        self.file_label = ttk.Label(top_frame, text="No file loaded")
        self.file_label.pack(side=tk.LEFT, padx=10)
        
        # Main Content
        main_frame = ttk.Frame(self.root)
        main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Canvas for Map
        self.canvas = tk.Canvas(main_frame, bg="white", width=800, height=600)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Right Side Panels
        info_frame = ttk.Frame(main_frame, width=400)
        info_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=10)
        
        # Tabs for Round Info and Chat
        self.tabs = ttk.Notebook(info_frame)
        self.tabs.pack(fill=tk.BOTH, expand=True)
        
        self.round_info_txt = tk.Text(self.tabs, wrap=tk.WORD, width=40)
        self.tabs.add(self.round_info_txt, text="Round Info")
        
        self.chat_txt = tk.Text(self.tabs, wrap=tk.WORD, width=40)
        self.tabs.add(self.chat_txt, text="Chat Transcript")
        
        # Bottom Controls
        ctrl_frame = ttk.Frame(self.root)
        ctrl_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        
        self.prev_btn = ttk.Button(ctrl_frame, text="< Previous", command=self.prev_round)
        self.prev_btn.pack(side=tk.LEFT)
        
        self.round_slider = ttk.Scale(ctrl_frame, from_=0, to=100, orient=tk.HORIZONTAL, command=self.on_slider)
        self.round_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=20)
        
        self.next_btn = ttk.Button(ctrl_frame, text="Next >", command=self.next_round)
        self.next_btn.pack(side=tk.LEFT)
        
        self.round_lbl = ttk.Label(ctrl_frame, text="Round: 0 / 0")
        self.round_lbl.pack(side=tk.LEFT, padx=10)
        
    def load_file(self):
        filename = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if filename:
            self._process_data(filename)
            
    def _process_data(self, filename):
        with open(filename, "r") as f:
            self.game_data = json.load(f)
            
        self.max_rounds = len(self.game_data.get("game_log", [])) - 1
        self.current_round = 0
        self.file_label.config(text=Path(filename).name)
        self.round_slider.config(to=self.max_rounds)
        self.round_slider.set(0)
        self.update_display()
        
    def on_slider(self, val):
        if self.game_data:
            self.current_round = int(float(val))
            self.update_display()
            
    def prev_round(self):
        if self.current_round > 0:
            self.current_round -= 1
            self.round_slider.set(self.current_round)
            self.update_display()
            
    def next_round(self):
        if self.current_round < self.max_rounds:
            self.current_round += 1
            self.round_slider.set(self.current_round)
            self.update_display()
            
    def update_display(self):
        if not self.game_data:
            return
            
        log = self.game_data["game_log"][self.current_round]
        state = log.get("state", {})
        
        self.round_lbl.config(text=f"Round: {self.current_round} / {self.max_rounds}")
        
        # Draw Map
        self.canvas.delete("all")
        
        # Draw connections
        for room, neighbors in ADJACENCY.items():
            x1, y1 = ROOM_COORDS[room]
            for n in neighbors:
                x2, y2 = ROOM_COORDS[n]
                self.canvas.create_line(x1, y1, x2, y2, fill="gray80", width=2)
                
        # Draw rooms
        for room, (x, y) in ROOM_COORDS.items():
            # Check for bodies or sabotage
            bg_color = "white"
            bodies = [b for b in state.get("bodies", []) if b["location"] == room]
            if bodies:
                bg_color = "#FFE4E1"  # Light pink for body
            
            sab = state.get("sabotage")
            if sab and sab.get("type") in ("reactor", "o2") and room in sab.get("fix_progress", {}):
                bg_color = "#FFD700"  # Gold for critical sabotage fix location

            self.canvas.create_rectangle(x-50, y-30, x+50, y+30, fill=bg_color, outline="black", width=2)
            self.canvas.create_text(x, y, text=room, font=("Arial", 10, "bold"))
            
            if bodies:
                self.canvas.create_text(x, y+20, text=f"BODY ({len(bodies)})", fill="red", font=("Arial", 8, "bold"))

        # Draw Players
        player_locs = state.get("player_locations", {})
        alive_players = state.get("alive_players", [])
        all_roles = self.game_data.get("all_roles", {})
        
        # Group players by room to stack them
        room_stacks = {}
        for pid, loc in player_locs.items():
            room_stacks.setdefault(loc, []).append(pid)
            
        for loc, pids in room_stacks.items():
            if loc not in ROOM_COORDS: continue
            rx, ry = ROOM_COORDS[loc]
            for i, pid in enumerate(pids):
                offset_x = (i % 3 - 1) * 20
                offset_y = (i // 3 + 1) * 20
                
                color = "blue" if all_roles.get(pid) == "crewmate" else "red"
                outline = "black" if pid in alive_players else "gray"
                
                self.canvas.create_oval(rx+offset_x-8, ry+offset_y-8, rx+offset_x+8, ry+offset_y+8, fill=color, outline=outline, width=2)
                self.canvas.create_text(rx+offset_x, ry+offset_y+15, text=pid, font=("Arial", 8))

        # Update Info Text
        self.round_info_txt.delete(1.0, tk.END)
        self.round_info_txt.insert(tk.END, f"--- Round {self.current_round} Actions ---\n\n")
        
        results = log.get("results", {})
        actions = log.get("actions", {})
        for pid in sorted(results.keys()):
            res = results[pid]
            act = actions.get(pid, {}).get("action", "wait")
            tgt = actions.get(pid, {}).get("target", "")
            status = "SUCCESS" if res.get("success") else f"FAILED ({res.get('reason')})"
            self.round_info_txt.insert(tk.END, f"{pid}: {act} {tgt}\n  -> {status}\n\n")

        # Update Chat Transcript
        self.chat_txt.delete(1.0, tk.END)
        meetings = self.game_data.get("meeting_history", [])
        current_meetings = [m for m in meetings if m["round_called"] == self.current_round + 1] # meetings happen after resolution
        
        if current_meetings:
            for m in current_meetings:
                self.chat_txt.insert(tk.END, f"--- MEETING CALLED BY {m['called_by']} ---\n")
                self.chat_txt.insert(tk.END, f"Trigger: {m['trigger']}\n")
                if m['voted_out']:
                    self.chat_txt.insert(tk.END, f"Result: {m['voted_out']} EJECTED ({m['role_revealed']})\n")
                else:
                    self.chat_txt.insert(tk.END, "Result: NO EJECTION\n")
                self.chat_txt.insert(tk.END, "\nTranscript:\n")
                
                for msg in m.get("transcript", []):
                    self.chat_txt.insert(tk.END, f"[{msg['rotation']}] {msg['speaker']}: {msg['message']}\n")
                self.chat_txt.insert(tk.END, "\n")
        else:
            self.chat_txt.insert(tk.END, "No meeting this round.")

if __name__ == "__main__":
    root = tk.Tk()
    app = AmongUsVisualizer(root)
    if len(sys.argv) > 1:
        app._process_data(sys.argv[1])
    root.mainloop()
