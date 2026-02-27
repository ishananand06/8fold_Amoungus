# Among Us LLM Agent Simulation - Participant Kit

Welcome to the Among Us LLM Agent Simulation hackathon! This repository contains a complete simulation engine for a social deduction game optimized for Large Language Models.

## 🚀 Quick Start

### 1. Installation
The simulation requires Python 3.9+ and has **zero** core dependencies.
To use the high-end **Replay Theater** visualizer, you need `pygame`:
```bash
pip install pygame
```

### 2. Run a Local Game
Test the simulation immediately with built-in rule-based and random bots. Use the `--verbose` flag to see round-by-round actions in your terminal:
```bash
python main.py play --agents random random rulebased rulebased --verbose
```

### 3. Visualize a Match
After running a game, a `game_log.json` is created. View it in the high-end **Replay Theater** (requires `pygame`):
```bash
python main.py theater game_log.json
```
*Note: You can also use `python main.py visualize game_log.json` for a basic view.*

## 🛠 Building Your Agent

To participate, you must implement a Python class that inherits from `BaseAgent`. 

1.  **Copy the template**: Use `template_agent.py` as your starting point.
2.  **Implement the 5 core methods**:
    *   `on_game_start`: Initialize your model and strategy.
    *   `on_task_phase`: Return a JSON action (move, do_task, kill, sabotage, etc.).
    *   `on_discussion`: Return a natural language message for meetings.
    *   `on_vote`: Return a player ID or "skip".
    *   `on_game_end`: Process results for learning or logging.

3.  **Test your agent**:
    ```bash
    python main.py play --agents path/to/your_agent.py random rulebased
    ```

## 🎮 Game Rules & Mechanics

*   **Map**: 10 rooms (Cafeteria, Medbay, Admin, Weapons, Upper Engine, Storage, Navigation, Reactor, Electrical, Shields).
*   **Tick-based**: Every round, all agents submit one action simultaneously.
*   **Roles**: 
    *   **Crewmates**: Do tasks to win. 8 tasks per player.
    *   **Impostors**: Kill crewmates to win. 6-round kill cooldown.
*   **Sabotages**: Impostors can trigger Reactor, O2 (critical), or Lights/Comms (disruptive).
*   **Resolution Order**: 1. Cooldowns -> 2. Movement -> 3. Kills -> 4. Tasks -> 5. Reports/Meetings.

## 🏆 Tournament Mode

Run a tournament between multiple agent files in a directory:
```bash
python main.py tournament --agents-dir ./my_agents --games 10
```
This will generate an Elo-based leaderboard and save all match logs to the `match_history/` folder.

## 📂 Repository Structure

- `main.py`: CLI entry point.
- `engine/`: Core simulation logic.
- `examples/`: Reference implementations.
    - `gemini_personality_agent.py`: High-quality LLM agent using Vertex AI.
    - `simple_rule_based_agent.py`: Non-LLM strategic bot using BFS pathfinding.
- `template_agent.py`: Your starting point for development.

## 💡 Reference Examples

Check the `examples/` directory for inspiration:
*   **Gemini Personality Agent**: Shows how to wrap a Vertex AI LLM, track tokens, and use "Personality" prompts to drive unique behavior.
*   **Simple Rule-Based Agent**: Demonstrates basic game logic (pathfinding, task prioritization) without an LLM.

Good luck, and may the best model win!
