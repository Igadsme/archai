from archai_generator.budget import (
    CONDITION_DIM,
    MAX_PARAMS_M,
    budget_bin,
    encode_condition,
    eval_condition,
)


def test_eval_budget_of_0_8m_lands_in_a_distinct_half_range_bin():
    condition = eval_condition(0.95, 0.8)
    assert len(condition) == CONDITION_DIM
    assert condition[0] == 0.95
    assert condition[1] == 0.8 / MAX_PARAMS_M
    assert condition[2:].count(1.0) == 1
    assert budget_bin(0.8 / MAX_PARAMS_M) == condition[2:].index(1.0)
    # A clearly smaller budget is a different bin.
    assert encode_condition(0.95, 0.2 / MAX_PARAMS_M)[2:] != condition[2:]
