# Among Us LLM Agent Simulation - Participant Kit

This repository contains a discrete, tick-based simulation engine of "Among Us," optimized for Large Language Model (LLM) agents.

## Getting Started

### 1. Installation
The simulation requires Python 3.9+ and has **zero** core dependencies.
To use the high-end **Replay Theater** visualizer, you need `pygame-ce`:
```bash
pip install pygame-ce
```

### 2. Run a Local Game
Run a simulation with built-in rule-based and random bots. Use the `--verbose` flag to see real-time actions in the terminal:
```bash
python main.py play --agents random random rulebased rulebased --verbose
```

### 3. Visualize a Match
After running a game, a `game_log.json` is created. View it in the cinematic **Replay Theater**:
```bash
python main.py theater game_log.json
```
*Note: Use `python main.py visualize game_log.json` for a basic tkinter view.*

## Building Your Agent

To participate, implement a Python class that inherits from `BaseAgent`. 

1.  **Template**: Use `template_agent.py` as your starting point.
2.  **Core Methods**:
    *   `on_game_start(config)`: Initialize your model and strategy.
    *   `on_task_phase(observation)`: Return a JSON action (move, do_task, kill, sabotage, etc.).
    *   `on_discussion(observation)`: Return a conversational message for meetings.
    *   `on_vote(observation)`: Return a player ID or "skip".
    *   `on_game_end(result)`: Process final match results.

3.  **Local Testing**:
    ```bash
    python main.py play --agents path/to/your_agent.py random rulebased --verbose
    ```

## Game Mechanics

*   **Map**: 10 connected rooms.
*   **Roles**: 
    *   **Crewmates**: Complete 8 tasks each to win.
    *   **Impostors**: Kill crewmates to reach majority. (6-round kill cooldown).
*   **Sabotages**: Impostors can trigger Reactor, O2, Lights, or Comms.
*   **Resolution Order**: 1. Cooldowns -> 2. Movement -> 3. Kills -> 4. Tasks -> 5. Reports/Meetings.

## Tournament Mode

Run a tournament between all agent files in a directory:
```bash
python main.py tournament --agents-dir ./my_agents --games 10
```
This computes Elo-based standings and saves logs to the `match_history/` folder.

## Repository Structure

- `main.py`: CLI entry point.
- `engine/`: Core simulation logic and visualizers.
- `examples/`: Reference implementations (LLM and Rule-based).
- `template_agent.py`: Starter template for development.
