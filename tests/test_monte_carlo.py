import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # noqa: E402
from src.cpm_processor import monteCarloSchedule  # noqa: E402
from tests.test_cpm_processor import build_sample_graph  # noqa: E402


def test_monte_carlo_schedule():
    G, durations = build_sample_graph()
    result = monteCarloSchedule(
        G,
        {k: 1 for k in durations},
        durations,
        {k: d * 2 for k, d in durations.items()},
        nIterations=10,
        confidence=0.9,
    )
    assert 'average' in result
    assert len(result['samples']) == 10
    assert result['min'] <= result['max']
