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

if __name__ == '__main__':
    unittest.main()
