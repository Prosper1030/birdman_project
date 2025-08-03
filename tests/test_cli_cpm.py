import subprocess
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / 'main.py'


def test_cli_cpm(tmp_path):
    dsm_path = tmp_path / 'dsm.csv'
    wbs_path = tmp_path / 'wbs.csv'

    dsm = "Task ID,A,B,C\nA,0,1,1\nB,0,0,0\nC,0,0,0\n"
    dsm_path.write_text(dsm, encoding='utf-8')

    wbs = "Task ID,TRF,Te_newbie\nA,1,1\nB,1,1\nC,1,1\n"
    wbs_path.write_text(wbs, encoding='utf-8')

    cmd = [
        sys.executable,
        str(MAIN),
        '--dsm', str(dsm_path),
        '--wbs', str(wbs_path),
        '--config', str(ROOT / 'config.json'),
        '--cpm'
    ]
    subprocess.run(cmd, check=True, cwd=tmp_path)
    assert (tmp_path / 'cmp_analysis.csv').exists()
    assert (tmp_path / 'sorted_wbs.csv').exists()
    assert (tmp_path / 'merged_wbs.csv').exists()
