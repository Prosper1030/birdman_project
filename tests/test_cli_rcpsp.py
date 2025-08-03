import subprocess
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "main.py"


def test_cli_rcpsp(tmp_path):
    """測試 CLI RCPSP 排程與甘特圖輸出"""
    dsm_path = tmp_path / "dsm.csv"
    wbs_path = tmp_path / "wbs.csv"
    res_path = tmp_path / "Resources.csv"

    dsm_data = "Task ID,A,B\nA,0,0\nB,0,0\n"
    dsm_path.write_text(dsm_data, encoding="utf-8")

    wbs_data = (
        "Task ID,TRF,Te_newbie,Category,ResourceDemand\n"
        "A,1,2,R1,1\n"
        "B,1,3,R1,1\n"
    )
    wbs_path.write_text(wbs_data, encoding="utf-8")

    res_data = "Group,Headcount_Cap\nR1,1\n"
    res_path.write_text(res_data, encoding="utf-8")

    gantt_path = tmp_path / "gantt.png"

    cmd = [
        sys.executable,
        str(MAIN),
        "--dsm",
        str(dsm_path),
        "--wbs",
        str(wbs_path),
        "--resources",
        str(res_path),
        "--config",
        str(ROOT / "config.json"),
        "--rcpsp-opt",
        "--export-rcpsp-gantt",
        str(gantt_path),
    ]
    subprocess.run(cmd, check=True, cwd=tmp_path)
    assert (tmp_path / "rcpsp_schedule.csv").exists()
    assert gantt_path.exists()
