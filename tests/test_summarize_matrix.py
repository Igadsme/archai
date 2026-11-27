from scripts.summarize_matrix import front, validation_for


def test_front_keeps_only_non_dominated_points():
    points = [{"validation_accuracy": a, "params_m": p} for a, p in [(90, 1.0), (85, 0.2), (88, 0.5), (87, 0.6), (91, 1.4)]]
    assert [(item["validation_accuracy"], item["params_m"]) for item in front(points)] == [(85, 0.2), (88, 0.5), (90, 1.0), (91, 1.4)]


def test_validation_for_follows_the_adapter_trial_mapping():
    row = {"trials": [{"seed": 0, "trial_seed": 777, "validation_accuracy": 1.0},
                      {"seed": 1, "trial_seed": 888, "validation_accuracy": 2.0},
                      {"seed": 2, "trial_seed": 777, "validation_accuracy": 1.0}]}
    # two archive trials: seed s uses trial s % 2, exactly like NATSBenchAdapter._resolve_trial_seed
    assert [validation_for(row, seed) for seed in range(4)] == [1.0, 2.0, 1.0, 2.0]
