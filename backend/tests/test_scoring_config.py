from pathlib import Path

import yaml

SCORING_CONFIG = Path(__file__).resolve().parents[2] / "config" / "scoring" / "v1.yaml"


def test_scoring_profile_weights_are_non_negative_and_sum_to_one() -> None:
    config = yaml.safe_load(SCORING_CONFIG.read_text())
    assert config["version"] == 1
    expected_keys = {
        "infrastructure",
        "road_comfort",
        "speed",
        "traffic",
        "surface",
        "grade",
    }
    for profile_name, profile in config["profiles"].items():
        weights = profile["weights"]
        assert set(weights) == expected_keys, profile_name
        assert all(value >= 0 for value in weights.values()), profile_name
        assert abs(sum(weights.values()) - 1.0) < 1e-6, profile_name
