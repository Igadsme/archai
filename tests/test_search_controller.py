from archai_core.schema import Architecture, Edge, Node, TensorSpec
from archai_search.controller import SearchConfig, SearchController


def candidate(channels: int):
    return Architecture(
        nodes=[Node(id="input", op="input", channels=3), Node(id="conv", op="conv3x3", channels=channels), Node(id="output", op="output", channels=channels)],
        edges=[Edge(source="input", target="conv"), Edge(source="conv", target="output")],
        input_spec=TensorSpec(channels=3, height=8, width=8), output_classes=10,
    )


def test_controller_persists_budget_and_resumes(tmp_path):
    values = iter([candidate(4), candidate(8), candidate(16)])
    controller = SearchController(SearchConfig(max_evaluations=2), tmp_path / "state.json")
    result = controller.run(lambda: next(values), lambda item: {"score": item.nodes[1].channels / 100})
    assert result.status == "completed"
    assert result.evaluations == 2
    resumed = SearchController(SearchConfig(max_evaluations=3), tmp_path / "state.json")
    final = resumed.run(lambda: candidate(32), lambda item: {"score": 0.32})
    assert final.evaluations == 3
    assert len(final.seen) == 3


def test_controller_terminates_when_proposer_exhausts_candidates(tmp_path):
    controller = SearchController(SearchConfig(max_evaluations=4, max_duplicate_attempts=2),
                                  tmp_path / "state.json")
    result = controller.run(lambda: candidate(4), lambda item: {"score": 0.04})
    assert result.status == "exhausted"
    assert result.evaluations == 1
