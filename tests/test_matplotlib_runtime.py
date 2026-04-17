import os
import subprocess
import sys
from pathlib import Path


def test_gui_import_forces_qt_backend():
    """匯入 GUI 模組時應強制使用 Qt backend，而非 macosx。"""
    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "minimal"
    env.pop("MPLBACKEND", None)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import matplotlib; "
                "import src.gui_qt; "
                "print(matplotlib.get_backend())"
            ),
        ],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    backend_name = result.stdout.strip().lower()
    assert backend_name == "qt5agg"
