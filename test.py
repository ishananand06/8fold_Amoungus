import unittest
from config import GameConfig, MAP_ADJACENCY, ALL_ROOMS, TASK_POOL
from engine import Role, Phase, SabotageType, Player, Task, ActiveSabotage, ActionResult, GameState

class TestConfig(unittest.TestCase):
    def test_default_config_valid(self):
        config = GameConfig()
        config.validate()  # Should not raise exception

    def test_invalid_config_raises(self):
        config = GameConfig(num_players=4, num_impostors=2)
        with self.assertRaises(AssertionError):
            config.validate()

    def test_map_adjacency(self):
        self.assertEqual(len(ALL_ROOMS), 10)
        self.assertIn("Medbay", MAP_ADJACENCY["Cafeteria"])
        self.assertIn("Cafeteria", MAP_ADJACENCY["Medbay"])

    def test_task_pool(self):
        self.assertEqual(len(TASK_POOL), 16)
        visual_tasks = [t for t in TASK_POOL if t["visual"]]
        self.assertEqual(len(visual_tasks), 2)

class TestEngineModels(unittest.TestCase):
    def test_task_completion(self):
        task = Task(task_id="t1", name="Upload Data", location="Admin", required=2, progress=1)
        self.assertFalse(task.completed)
        task.progress += 1
        self.assertTrue(task.completed)

    def test_game_state_initialization(self):
        config = GameConfig()
        state = GameState(config=config)
        self.assertEqual(state.phase, Phase.TASK)
        self.assertEqual(state.round_number, 0)
        self.assertIsNone(state.winner)
        self.assertEqual(len(state.players), 0)
        self.assertEqual(len(state.tasks), 0)


class TestObservationGenerator(unittest.TestCase):
    def setUp(self):
        from engine import ObservationGenerator
        self.config = GameConfig()
        self.state = GameState(config=self.config)
        self.obs_gen = ObservationGenerator(self.state)

        # Setup players
        self.state.players["p1"] = Player(id="p1", role=Role.CREWMATE, location="Cafeteria")
        self.state.players["p2"] = Player(id="p2", role=Role.IMPOSTOR, location="Cafeteria")
        self.state.players["p3"] = Player(id="p3", role=Role.CREWMATE, location="Medbay")

        # Setup some tasks
        self.state.tasks["p1"] = [Task(task_id="t1", name="Upload Data", location="Admin", required=2)]
        self.state.tasks["p2"] = [Task(task_id="t2", name="Fake Task", location="Storage", required=2)]

    def test_task_observation_crewmate(self):
        obs = self.obs_gen.generate_task_observation("p1")
        self.assertEqual(obs["identity"]["your_id"], "p1")
        self.assertEqual(obs["identity"]["your_role"], "crewmate")
        
        # Room observation
        players_present = [p["id"] for p in obs["room_observations"]["players_present"]]
        self.assertIn("p2", players_present)
        self.assertNotIn("p3", players_present)

        # Impostor info should be none
        self.assertIsNone(obs["impostor_info"])

    def test_task_observation_impostor(self):
        obs = self.obs_gen.generate_task_observation("p2")
        self.assertEqual(obs["identity"]["your_id"], "p2")
        self.assertEqual(obs["identity"]["your_role"], "impostor")
        self.assertIsNotNone(obs["impostor_info"])
        self.assertEqual(obs["impostor_info"]["teammates"], [])

    def test_global_task_progress(self):
        # Progress starts at 0
        self.assertEqual(self.obs_gen._global_task_progress(), 0.0)
        # Advance p1's task
        self.state.tasks["p1"][0].progress = 1
        # p2 is impostor so their task shouldn't count towards total required
        self.assertEqual(self.obs_gen._global_task_progress(), 0.5)


class TestActionResolver(unittest.TestCase):
    def setUp(self):
        from engine import ActionResolver
        self.config = GameConfig()
        self.state = GameState(config=self.config)
        self.resolver = ActionResolver(self.state)

        self.state.players["p1"] = Player(id="p1", role=Role.CREWMATE, location="Cafeteria")
        self.state.players["p2"] = Player(id="p2", role=Role.IMPOSTOR, location="Cafeteria", kill_cooldown=0)
        self.state.players["p3"] = Player(id="p3", role=Role.CREWMATE, location="Admin")

    def test_movement_resolution(self):
        actions = {"p1": {"action": "move", "target": "Admin"}}
        self.resolver.resolve_round(actions)
        
        self.assertEqual(self.state.players["p1"].location, "Admin")
        self.assertEqual(self.state.players["p1"].last_action, "moving")
        # Check arrival event
        self.assertIn("p1 arrived from Cafeteria", self.state.events["p3"])

    def test_kill_resolution(self):
        actions = {"p2": {"action": "kill", "target": "p1"}}
        self.resolver.resolve_round(actions)
        
        self.assertFalse(self.state.players["p1"].alive)
        self.assertEqual(len(self.state.bodies), 1)
        self.assertEqual(self.state.players["p2"].kill_cooldown, self.config.kill_cooldown)

    def test_report_triggers_meeting(self):
        self.state.bodies.append({"player_id": "p99", "location": "Cafeteria"})
        actions = {"p1": {"action": "report"}}
        self.resolver.resolve_round(actions)
        
        self.assertEqual(self.state.phase, Phase.DISCUSSION)
        self.assertIsNotNone(self.state.meeting_context)
        self.assertEqual(self.state.meeting_context["trigger"], "body_report")


from engine import BaseAgent

class MockAgent(BaseAgent):
    def __init__(self): pass
    def on_game_start(self, config): pass
    def on_task_phase(self, obs): return {"action": "wait"}
    def on_discussion(self, obs): return "hello"
    def on_vote(self, obs): return "skip"
    def on_game_end(self, result): pass

class TestGameEngine(unittest.TestCase):
    def test_engine_initialization(self):
        from engine import GameEngine
        agents = {f"p{i}": MockAgent() for i in range(7)}
        engine = GameEngine(GameConfig(), agents)
        engine.setup_game()
        
        self.assertEqual(len(engine.state.players), 7)
        impostors = [p for p in engine.state.players.values() if p.role == Role.IMPOSTOR]
        crewmates = [p for p in engine.state.players.values() if p.role == Role.CREWMATE]
        self.assertEqual(len(impostors), engine.config.num_impostors)
        self.assertEqual(len(crewmates), engine.config.num_players - engine.config.num_impostors)
        
    def test_engine_run(self):
        from engine import GameEngine
        agents = {f"p{i}": MockAgent() for i in range(7)}
        engine = GameEngine(GameConfig(max_total_rounds=10), agents)
        result = engine.run()
        self.assertEqual(result["winner"], "crewmates")
        self.assertEqual(result["cause"], "timeout")
        self.assertEqual(result["final_round"], 10)



class TestAgents(unittest.TestCase):
    def test_parse_llm_json(self):
        from agents import parse_llm_json
        self.assertEqual(parse_llm_json('{"action": "move"}'), {"action": "move"})
        self.assertEqual(parse_llm_json('`json\n{"action": "kill"}\n`'), {"action": "kill"})
        self.assertEqual(parse_llm_json('Here is my move: {"action": "wait"}'), {"action": "wait"})

    def test_full_game_with_bots(self):
        from engine import GameEngine
        from agents import RuleBasedBot, RandomBot
        
        agents = {}
        for i in range(3): agents[f"p{i}"] = RuleBasedBot()
        for i in range(3, 7): agents[f"p{i}"] = RandomBot()
            
        # We run it with small limit to ensure it ends quickly if not won
        engine = GameEngine(GameConfig(max_total_rounds=10), agents)
        result = engine.run()
        self.assertIn(result["winner"], ["crewmates", "impostors"])

if __name__ == '__main__':
    unittest.main()
