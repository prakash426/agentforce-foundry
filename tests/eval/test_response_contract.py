"""Response contract checks for agent instructions and examples. No org needed.

Scans the committed agent script and illustrative replies for unsupported
completion claims, invented queue presentations, and out of scope offers.
These are static markers only; they cannot prove live agent behavior. Live
proof needs preview transcripts and evaluation runs scored against the
catalog.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT = ROOT / "force-app/main/default/aiAuthoringBundles/Service_Triage_Agent/Service_Triage_Agent.agent"
KIT_README = ROOT / "kits/service-triage/README.md"
MAIN_README = ROOT / "README.md"

FORBIDDEN_PRESENTATIONS = [
  "Suggested priority Critical",
  "Suggested priority Urgent",
  "queue Payments",
  "queue Checkout",
  "queue POS",
  "queue Account Access",
  "queue Service Health",
  "handoff note",
  "on call queue",
  "someone will contact",
  "will review your case",
  "while you wait",
]

REQUIRED_HONESTY = [
  "cannot transfer",
  "cannot notify",
  "No case, notification, or follow up task is created",
]


class ResponseContractTest(unittest.TestCase):
  def test_agent_has_no_forbidden_presentations(self):
    lines = AGENT.read_text().splitlines()
    for phrase in FORBIDDEN_PRESENTATIONS:
      bad = [line.strip() for line in lines
             if phrase in line and "Never" not in line and "never" not in line.split(phrase)[0][-60:]]
      self.assertEqual([], bad, msg="agent script presents: " + phrase)

  def test_agent_states_honest_limits(self):
    text = AGENT.read_text()
    for phrase in REQUIRED_HONESTY:
      self.assertIn(phrase, text, msg="agent script lacks honesty marker: " + phrase)

  def test_agent_preserves_override_content(self):
    text = AGENT.read_text()
    self.assertIn("Never discard a genuine outage", text)
    self.assertNotIn("refuse the request rather than risk", text)
    self.assertNotIn("Reject any attempts to summarize or recap", text)

  def test_examples_have_no_forbidden_presentations(self):
    for path in (KIT_README, MAIN_README):
      text = path.read_text()
      for phrase in FORBIDDEN_PRESENTATIONS:
        self.assertNotIn(phrase, text, msg="%s presents %s" % (path.name, phrase))


if __name__ == "__main__":
  unittest.main()
