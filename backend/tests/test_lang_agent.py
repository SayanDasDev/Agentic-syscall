import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import app.lang_agent as la


class FakeGraph:
    def __init__(self, mapping):
        self.mapping = mapping

    def invoke(self, state):
        text = state.get("user_input", "")
        for k, v in self.mapping.items():
            if k(text):
                return {"result": v}
        return {"result": {"action": "once"}}


def mk_pred(substr):
    return lambda t: substr in t.lower()


class AgentTests(unittest.TestCase):
    def setUp(self):
        la._graph = None
        mapping = {
            mk_pred("every 5 seconds"): {"action": "stream", "interval": 5.0},
            mk_pred("every 2 minutes for 3 samples"): {"action": "stream", "interval": 120.0, "count": 3},
            mk_pred("stop"): {"action": "stop"},
            mk_pred("once"): {"action": "once"},
        }

        def fake_build_graph():
            return FakeGraph(mapping)

        self.orig_build = la.build_graph
        la.build_graph = fake_build_graph

    def tearDown(self):
        la.build_graph = self.orig_build
        la._graph = None

    def test_stream_seconds(self):
        out = la.run_agent("every 5 seconds")
        self.assertEqual(out["action"], "stream")
        self.assertEqual(out["interval"], 5.0)

    def test_stream_minutes_with_count(self):
        out = la.run_agent("every 2 minutes for 3 samples")
        self.assertEqual(out["action"], "stream")
        self.assertEqual(out["interval"], 120.0)
        self.assertEqual(out.get("count"), 3)

    def test_stop(self):
        out = la.run_agent("stop")
        self.assertEqual(out["action"], "stop")

    def test_default_once(self):
        out = la.run_agent("send once")
        self.assertEqual(out["action"], "once")


if __name__ == "__main__":
    unittest.main()

