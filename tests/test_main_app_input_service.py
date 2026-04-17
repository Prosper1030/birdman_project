import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ui.main_app.input_service import (  # noqa: E402
    FolderImportSelectionError,
    loadFolderImportBundle,
    loadOptionalDsmForEditor,
    loadResourcesPreview,
    loadWbsPreview,
)


def _write_sample_wbs(path: Path) -> None:
    pd.DataFrame(
        {
            "Task ID": ["A26-001", "A26-002"],
            "TRF": [1, 2],
            "Te_newbie": [2, 3],
        }
    ).to_csv(path, index=False, encoding="utf-8-sig")


def _write_sample_dsm(path: Path) -> None:
    pd.DataFrame(
        [[0, 0], [1, 0]],
        index=["A26-001", "A26-002"],
        columns=["A26-001", "A26-002"],
    ).to_csv(path, encoding="utf-8-sig")


def test_load_wbs_preview_returns_display_with_no_column(tmp_path):
    wbs_path = tmp_path / "WBS.csv"
    _write_sample_wbs(wbs_path)

    wbs, display = loadWbsPreview(str(wbs_path))

    assert list(wbs["Task ID"]) == ["A26-001", "A26-002"]
    assert display.columns[0] == "No."
    assert display["No."].tolist() == [1, 2]


def test_load_optional_dsm_for_editor_returns_none_for_empty_path():
    assert loadOptionalDsmForEditor("") is None


def test_load_resources_preview_reads_utf8_sig_csv(tmp_path):
    resource_path = tmp_path / "Resources.csv"
    pd.DataFrame({"Group": ["R1"], "Headcount_Cap": [2]}).to_csv(
        resource_path, index=False, encoding="utf-8-sig"
    )

    resources = loadResourcesPreview(str(resource_path))

    assert resources.to_dict("records") == [{"Group": "R1", "Headcount_Cap": 2}]


def test_load_folder_import_bundle_loads_optional_resources(tmp_path):
    _write_sample_wbs(tmp_path / "project_wbs.csv")
    _write_sample_dsm(tmp_path / "project_dsm.csv")
    pd.DataFrame({"Group": ["R1"], "Headcount_Cap": [2]}).to_csv(
        tmp_path / "project_resources.csv",
        index=False,
        encoding="utf-8-sig",
    )

    bundle = loadFolderImportBundle(str(tmp_path))

    assert bundle.wbsPath.endswith("project_wbs.csv")
    assert bundle.dsmPath.endswith("project_dsm.csv")
    assert bundle.resourcePath.endswith("project_resources.csv")
    assert list(bundle.wbs["Task ID"]) == ["A26-001", "A26-002"]
    assert bundle.dsm.shape == (2, 2)
    assert bundle.resources["Group"].tolist() == ["R1"]
    assert bundle.warnings == []


def test_load_folder_import_bundle_warns_when_resources_invalid(tmp_path):
    _write_sample_wbs(tmp_path / "project_wbs.csv")
    _write_sample_dsm(tmp_path / "project_dsm.csv")
    (tmp_path / "project_resources.csv").write_text('Group,"Headcount_Cap\nR1,2', encoding="utf-8")

    bundle = loadFolderImportBundle(str(tmp_path))

    assert bundle.resourcePath == ""
    assert bundle.resources.empty
    assert bundle.warnings == ["Resources 檔案格式不正確，將忽略。"]


def test_load_folder_import_bundle_requires_single_wbs_and_dsm(tmp_path):
    _write_sample_wbs(tmp_path / "project_wbs_a.csv")
    _write_sample_wbs(tmp_path / "project_wbs_b.csv")
    _write_sample_dsm(tmp_path / "project_dsm.csv")

    with pytest.raises(FolderImportSelectionError, match="剛好包含一份 WBS 和一份 DSM"):
        loadFolderImportBundle(str(tmp_path))
