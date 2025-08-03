import sys
from pathlib import Path
import random
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # noqa: E402
from src.cpm_processor import monteCarloSchedule, cpmForwardPass  # noqa: E402
from tests.test_cpm_processor import build_sample_graph  # noqa: E402


def test_monte_carlo_schedule():
    """比較 Beta-PERT 與三角分佈的模擬平均工期"""
    G, durations = build_sample_graph()

    # Beta-PERT 模擬
    random.seed(0)
    np.random.seed(0)
    betaResult = monteCarloSchedule(
        G,
        {k: 1 for k in durations},
        durations,
        {k: d * 2 for k, d in durations.items()},
        nIterations=1000,
        confidence=0.9,
    )

    # 三角分佈基準模擬
    random.seed(0)
    triSamples: list[float] = []
    for _ in range(1000):
        sampled: dict[str, float] = {}
        for task in G.nodes:
            o = 1
            m = durations[task]
            p = durations[task] * 2
            sampled[task] = random.triangular(o, p, m)
        forward = cpmForwardPass(G, sampled)
        projectEnd = max(v[1] for v in forward.values())
        triSamples.append(projectEnd)
    triAvg = sum(triSamples) / len(triSamples)

    assert "average" in betaResult
    assert len(betaResult["samples"]) == 1000
    assert betaResult["average"] < triAvg
    assert betaResult["min"] <= betaResult["max"]
