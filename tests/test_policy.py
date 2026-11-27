import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from gnmi_net.cli import main
from gnmi_net.diff import Change
from gnmi_net.policy import Policy, PolicyError, load_policy

DESIRED = {
    "interfaces": {
        "interface": [
            {"name": "ethernet1", "config": {"admin-state": "enable", "mtu": 9214}}
        ]
    }
}
ACTUAL = {
    "interfaces": {
        "interface": [
            {"name": "ethernet1", "config": {"admin-state": "enable", "mtu": 9216}}
        ]
    }
}
MTU = "/interfaces/interface[0]/config/mtu"


class PolicyTest(unittest.TestCase):
    def test_clean_plan_passes(self) -> None:
        self.assertEqual(Policy().violations([]), [])

    def test_change_budget_is_enforced(self) -> None:
        policy = Policy(max_changes=1)
        reasons = policy.violations([Change("add", "/a"), Change("add", "/b")])
        self.assertEqual(len(reasons), 1)
        self.assertIn("max_changes=1", reasons[0])

    def test_high_risk_budget_is_enforced(self) -> None:
        policy = Policy(max_high_risk=0)
        reasons = policy.violations([Change("change", MTU, 9216, 9214)])
        self.assertIn("high-risk", reasons[0])

    def test_protected_prefix_matches_only_on_boundary(self) -> None:
        policy = Policy(protected=("/interfaces/interface[0]/config",))
        reasons = policy.violations([Change("change", MTU, 9216, 9214)])
        self.assertEqual(reasons, [f"protected path touched: {MTU}"])
        adjacent = Change("add", "/interfaces/interface[0]/configurations/x")
        self.assertEqual(policy.violations([adjacent]), [])

    def test_load_rejects_bad_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            path.write_text(json.dumps({"max_changes": 0}))
            with self.assertRaises(PolicyError):
                load_policy(path)

    def test_load_accepts_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            path.write_text("{}")
            self.assertEqual(load_policy(path), Policy())


class CliPolicyTest(unittest.TestCase):
    def run_cli(self, *extra: str) -> int:
        with tempfile.TemporaryDirectory() as tmp:
            desired = Path(tmp) / "desired.json"
            actual = Path(tmp) / "actual.json"
            desired.write_text(json.dumps(DESIRED))
            actual.write_text(json.dumps(ACTUAL))
            with redirect_stderr(io.StringIO()):
                return main(
                    ["--desired", str(desired), "--actual", str(actual), *extra]
                )

    def test_blocked_plan_exits_4(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            policy = Path(tmp) / "policy.json"
            policy.write_text(json.dumps({"protected": ["/interfaces"]}))
            self.assertEqual(self.run_cli("--policy", str(policy)), 4)

    def test_force_overrides_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            policy = Path(tmp) / "policy.json"
            policy.write_text(json.dumps({"max_high_risk": 0}))
            self.assertEqual(self.run_cli("--policy", str(policy)), 4)
            self.assertEqual(self.run_cli("--policy", str(policy), "--force"), 2)

    def test_drift_without_policy_still_exits_2(self) -> None:
        self.assertEqual(self.run_cli(), 2)


if __name__ == "__main__":
    unittest.main()
