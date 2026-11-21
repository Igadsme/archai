from archai_core.schema import Architecture, Edge, Node, TensorSpec
from archai_search.learned import LearnedSearch


def candidate(channels):
    return Architecture(nodes=[Node(id="input", op="input", channels=3), Node(id="conv", op="conv3x3", channels=channels), Node(id="output", op="output", channels=channels)],
                        edges=[Edge(source="input", target="conv"), Edge(source="conv", target="output")],
                        input_spec=TensorSpec(channels=3, height=8, width=8), output_classes=10)


def test_learned_search_connects_prediction_and_evaluation():
    candidates = [candidate(4), candidate(8), candidate(16)]
    batches = iter([[candidates[0], candidates[1]], [candidates[2]]])
    search = LearnedSearch(lambda size: next(batches, []), lambda values: [(item.nodes[1].channels / 100, 0.01 if item.nodes[1].channels == 4 else 0.1) for item in values],
                           lambda item: {"score": item.nodes[1].channels / 100, "parameters": item.nodes[1].channels}, budget=2)
    observations = search.run(pool_size=3)
    assert len(observations) == 2
    assert search.status == "completed"
    assert len(search.pareto_frontier()) >= 1
