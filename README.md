# 🚀 Among Us LLM Agent Simulation — Participant Kit

Welcome to the EightFold AmongUs research environment. This is a high-fidelity, discrete, tick-based simulation engine of "Among Us," specifically designed to benchmark Large Language Model (LLM) agents on strategic reasoning, deception detection, and collaborative planning.

---

## 🛠 Getting Started

### 1. Installation
This project uses `uv` for lightning-fast dependency management and reproducible environments.

```bash
# Install uv if you haven't already
curl -LsSf [https://astral.sh/uv/install.sh](https://astral.sh/uv/install.sh) | sh

# Clone and sync the environment
git clone [https://github.com/goelanmol124/EightFold_Amongus](https://github.com/goelanmol124/EightFold_Amongus)
cd EightFold_Amongus
uv sync
```

### 2. Configure Your "Brain" (LLM Setup)
To use LLM-based agents, you need an API key. We recommend OpenRouter for its diverse model access.

Copy the example environment file:
```bash
cp .env.example .env
```

### 3. Run a Local Game

Run a simulation with built-in rule-based and random bots. Use the `--verbose` flag to see real-time actions in the terminal:

```bash
python main.py play --agents random random rulebased rulebased --verbose
```

### 4. Visualize a Match

After running a game, a `game_log.json` is created. You have three visualization options:

#### Web Replay Theater (Recommended)

Open `visualiser/index.html` in any browser — no server or dependencies needed:

1. Click **Load Game Log** and select your `game_log.json`
2. Use the playback controls to step through rounds, or press **Space** to auto-play

**Keyboard Shortcuts:**
| Key | Action |
|-----|--------|
| `Space` | Play / Pause |
| `←` / `→` | Previous / Next round |
| `+` / `-` | Speed up / Slow down |
| `M` | Toggle meeting overlay |
| `Esc` | Close meeting overlay |

## Building Your Agent

To participate, implement a Python class that inherits from `BaseAgent`.

1.  **Template**: Use `template_agent.py` as your starting point.
2.  **Core Methods**:
    - `on_game_start(config)`: Initialize your model and strategy.
    - `on_task_phase(observation)`: Return a JSON action (move, do_task, kill, sabotage, etc.).
    - `on_discussion(observation)`: Return a conversational message for meetings.
    - `on_vote(observation)`: Return a player ID or "skip".
    - `on_game_end(result)`: Process final match results.

3.  **Local Testing**:
    ```bash
    python main.py play --agents path/to/your_agent.py random rulebased --verbose
    ```

## Game Mechanics

- **Map**: 14 connected rooms (matching the Skeld layout).
- **Roles**:
  - **Crewmates**: Complete 8 tasks each to win.
  - **Impostors**: Kill crewmates to reach majority. (6-round kill cooldown).
- **Sabotages**: Impostors can trigger Reactor, O2, Lights, or Comms.
- **Resolution Order**: 1. Cooldowns -> 2. Movement -> 3. Kills -> 4. Tasks -> 5. Reports/Meetings.

## Tournament Mode

Run a tournament between all agent files in a directory:

```bash
python main.py tournament --agents-dir ./my_agents --games 10
```

This computes Elo-based standings and saves logs to the `match_history/` folder.

## Repository Structure

- `main.py`: CLI entry point.
- `engine/`: Core simulation logic and Python visualizers.
- `visualiser/`: Web-based replay theater (HTML/CSS/JS).
- `examples/`: Reference implementations (LLM and Rule-based).
- `template_agent.py`: Starter template for development.

~~We have left a few bugs for you to figure out 😉~~