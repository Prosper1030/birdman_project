from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import hashlib
import json

import networkx as nx
import pandas as pd

from ...app_paths import projectRoot
from ...dsm_processor import buildGraph, readDsm


AUTOSAVE_DIR_NAME = ".birdman_autosave"
AUTOSAVE_INTERVAL_MS = 30_000
AUTOSAVE_KEEP_COUNT = 10
SNAPSHOT_DSM_FILENAME = "dsm_snapshot.csv"
SNAPSHOT_WBS_FILENAME = "wbs_snapshot.csv"
SNAPSHOT_META_FILENAME = "session.json"


@dataclass
class SccGroupSummary:
    """循環依賴群組摘要。"""

    groupId: int
    taskIds: list[str]


@dataclass
class SessionSnapshotInfo:
    """工作階段快照資訊。"""

    snapshotDir: Path
    savedAt: str
    reason: str
    dirty: bool
    hasCycles: bool


@dataclass
class DsmEditorSession:
    """DSM 編輯器工作階段狀態。"""

    wbsDf: pd.DataFrame
    dsmDf: pd.DataFrame
    baselineDsmDf: pd.DataFrame
    wbsPath: str | None = None
    dsmPath: str | None = None
    autosaveRoot: Path = field(
        default_factory=lambda: projectRoot / AUTOSAVE_DIR_NAME
    )
    sessionId: str = ""
    dirty: bool = False
    lastAutosavePath: str | None = None
    lastAutosaveTime: str | None = None
    hasCycles: bool = False
    sccGroups: list[SccGroupSummary] = field(default_factory=list)

    def sourceSummary(self) -> str:
        """回傳目前工作階段的來源摘要。"""
        wbsName = Path(self.wbsPath).name if self.wbsPath else "未指定 WBS"
        dsmName = Path(self.dsmPath).name if self.dsmPath else "空白依賴圖"
        return f"WBS：{wbsName}｜DSM：{dsmName}"


def buildSessionId(
    wbsPath: str | None,
    dsmPath: str | None,
    taskIds: list[str],
) -> str:
    """根據來源檔與任務清單建立穩定的工作階段 ID。"""
    payload = {
        "wbs_path": str(Path(wbsPath).resolve()) if wbsPath else None,
        "dsm_path": str(Path(dsmPath).resolve()) if dsmPath else None,
        "task_ids": taskIds,
    }
    digest = hashlib.sha1(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return digest[:12]


def validateEditorInputs(
    wbsDf: pd.DataFrame,
    dsmDf: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """驗證編輯器載入所需的 WBS 與 DSM。"""
    if wbsDf is None or wbsDf.empty:
        raise ValueError("WBS 不可為空，請先提供有效的 WBS 檔案。")
    if "Task ID" not in wbsDf.columns:
        raise ValueError("WBS 缺少 Task ID 欄位，無法建立編輯器節點。")

    normalizedWbs = wbsDf.copy()
    normalizedWbs["Task ID"] = normalizedWbs["Task ID"].astype(str).str.strip()
    if (normalizedWbs["Task ID"] == "").any():
        raise ValueError("WBS 的 Task ID 不可為空白。")
    if not normalizedWbs["Task ID"].is_unique:
        duplicates = normalizedWbs[
            normalizedWbs["Task ID"].duplicated(keep=False)
        ]["Task ID"].tolist()
        duplicateText = "、".join(dict.fromkeys(duplicates))
        raise ValueError(f"WBS 存在重複的 Task ID：{duplicateText}")

    taskIds = normalizedWbs["Task ID"].tolist()
    if dsmDf is None:
        emptyDsm = pd.DataFrame(0, index=taskIds, columns=taskIds, dtype=int)
        return normalizedWbs, emptyDsm

    normalizedDsm = dsmDf.copy()
    normalizedDsm.index = normalizedDsm.index.astype(str).str.strip()
    normalizedDsm.columns = normalizedDsm.columns.astype(str).str.strip()

    if normalizedDsm.shape[0] != normalizedDsm.shape[1]:
        raise ValueError("DSM 必須為方陣，請檢查檔案內容。")
    if not normalizedDsm.index.is_unique:
        duplicates = normalizedDsm.index[normalizedDsm.index.duplicated()].tolist()
        duplicateText = "、".join(dict.fromkeys(duplicates))
        raise ValueError(f"DSM 列索引存在重複 Task ID：{duplicateText}")
    if not normalizedDsm.columns.is_unique:
        duplicates = normalizedDsm.columns[normalizedDsm.columns.duplicated()].tolist()
        duplicateText = "、".join(dict.fromkeys(duplicates))
        raise ValueError(f"DSM 欄位存在重複 Task ID：{duplicateText}")
    if set(normalizedDsm.index) != set(normalizedDsm.columns):
        raise ValueError("DSM 的列與欄 Task ID 不一致，請檢查檔案格式。")

    wbsTaskSet = set(taskIds)
    dsmTaskSet = set(normalizedDsm.index)
    missingInDsm = [taskId for taskId in taskIds if taskId not in dsmTaskSet]
    extraInDsm = [taskId for taskId in normalizedDsm.index if taskId not in wbsTaskSet]
    if missingInDsm:
        raise ValueError(
            "DSM 缺少以下 WBS 任務："
            + "、".join(missingInDsm)
        )
    if extraInDsm:
        raise ValueError(
            "DSM 包含 WBS 中不存在的任務："
            + "、".join(extraInDsm)
        )

    normalizedDsm = normalizedDsm.reindex(index=taskIds, columns=taskIds)
    numericValues = pd.to_numeric(normalizedDsm.stack(), errors="coerce")
    if numericValues.isna().any():
        raise ValueError("DSM 內容必須是 0 或 1，不可包含非數字資料。")
    illegalValues = sorted({int(value) for value in numericValues.tolist() if value not in (0, 1)})
    if illegalValues:
        illegalText = "、".join(str(value) for value in illegalValues)
        raise ValueError(f"DSM 僅允許 0 或 1，發現非法值：{illegalText}")

    normalizedDsm = normalizedDsm.astype(int)
    return normalizedWbs, normalizedDsm


def summarizeCyclicSccGroups(dsmDf: pd.DataFrame) -> tuple[nx.DiGraph, list[SccGroupSummary]]:
    """根據 DSM 計算圖形與成環 SCC 摘要。"""
    graph = buildGraph(dsmDf)
    groups: list[SccGroupSummary] = []
    for component in nx.strongly_connected_components(graph):
        taskIds = sorted(component)
        if len(taskIds) > 1:
            groups.append(SccGroupSummary(groupId=len(groups) + 1, taskIds=taskIds))
            continue

        onlyTask = taskIds[0]
        if graph.has_edge(onlyTask, onlyTask):
            groups.append(SccGroupSummary(groupId=len(groups) + 1, taskIds=taskIds))

    return graph, groups


def dsmEquals(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    """忽略順序差異，比較兩份 DSM 是否相同。"""
    leftIds = list(left.index.astype(str))
    rightIds = list(right.index.astype(str))
    if set(leftIds) != set(rightIds):
        return False
    normalizedLeft = left.reindex(index=rightIds, columns=rightIds)
    return normalizedLeft.equals(right)


def serializeSccGroups(groups: list[SccGroupSummary]) -> list[dict[str, Any]]:
    """將 SCC 摘要轉成可序列化資料。"""
    return [
        {
            "group_id": group.groupId,
            "task_ids": group.taskIds,
        }
        for group in groups
    ]


def getSessionSnapshotRoot(session: DsmEditorSession) -> Path:
    """回傳指定工作階段的快照根目錄。"""
    return session.autosaveRoot / session.sessionId


def writeSessionSnapshot(
    session: DsmEditorSession,
    reason: str = "autosave",
) -> SessionSnapshotInfo:
    """寫入工作階段快照並保留最近 10 份。"""
    now = datetime.now().astimezone()
    savedAt = now.isoformat(timespec="seconds")
    snapshotRoot = getSessionSnapshotRoot(session)
    snapshotRoot.mkdir(parents=True, exist_ok=True)

    snapshotDir = snapshotRoot / now.strftime("%Y%m%dT%H%M%S%f")
    snapshotDir.mkdir(parents=True, exist_ok=False)

    session.dsmDf.to_csv(
        snapshotDir / SNAPSHOT_DSM_FILENAME,
        encoding="utf-8-sig",
    )
    session.wbsDf.to_csv(
        snapshotDir / SNAPSHOT_WBS_FILENAME,
        index=False,
        encoding="utf-8-sig",
    )

    metadata = {
        "session_id": session.sessionId,
        "saved_at": savedAt,
        "reason": reason,
        "dirty": session.dirty,
        "has_cycles": session.hasCycles,
        "scc_groups": serializeSccGroups(session.sccGroups),
        "wbs_path": session.wbsPath,
        "dsm_path": session.dsmPath,
        "snapshot_dir": str(snapshotDir),
    }
    (snapshotDir / SNAPSHOT_META_FILENAME).write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    trimSessionSnapshots(snapshotRoot)
    session.lastAutosavePath = str(snapshotDir)
    session.lastAutosaveTime = savedAt

    return SessionSnapshotInfo(
        snapshotDir=snapshotDir,
        savedAt=savedAt,
        reason=reason,
        dirty=session.dirty,
        hasCycles=session.hasCycles,
    )


def listSessionSnapshots(session: DsmEditorSession) -> list[SessionSnapshotInfo]:
    """列出工作階段現有快照，依新到舊排序。"""
    snapshotRoot = getSessionSnapshotRoot(session)
    if not snapshotRoot.exists():
        return []

    snapshots: list[SessionSnapshotInfo] = []
    for candidate in snapshotRoot.iterdir():
        if not candidate.is_dir():
            continue
        metadataPath = candidate / SNAPSHOT_META_FILENAME
        if not metadataPath.exists():
            continue
        try:
            metadata = json.loads(metadataPath.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        snapshots.append(
            SessionSnapshotInfo(
                snapshotDir=candidate,
                savedAt=str(metadata.get("saved_at", candidate.name)),
                reason=str(metadata.get("reason", "autosave")),
                dirty=bool(metadata.get("dirty", False)),
                hasCycles=bool(metadata.get("has_cycles", False)),
            )
        )

    snapshots.sort(key=lambda item: item.snapshotDir.name, reverse=True)
    return snapshots


def trimSessionSnapshots(snapshotRoot: Path) -> None:
    """每個工作階段僅保留最近 10 份快照。"""
    if not snapshotRoot.exists():
        return

    snapshotDirs = sorted(
        [path for path in snapshotRoot.iterdir() if path.is_dir()],
        key=lambda path: path.name,
        reverse=True,
    )
    for staleDir in snapshotDirs[AUTOSAVE_KEEP_COUNT:]:
        for child in staleDir.iterdir():
            child.unlink(missing_ok=True)
        staleDir.rmdir()


def findLatestRestorableSnapshot(
    session: DsmEditorSession,
) -> SessionSnapshotInfo | None:
    """找出可提示恢復的最新快照。"""
    if not session.wbsPath and not session.dsmPath:
        return None

    snapshots = listSessionSnapshots(session)
    if not snapshots:
        return None

    latest = snapshots[0]
    if not latest.dirty:
        return None
    latestSourceMtime = getLatestSourceMtime(session)
    if latestSourceMtime is None:
        return latest

    if latest.snapshotDir.stat().st_mtime <= latestSourceMtime:
        return None
    return latest


def loadSnapshotData(
    snapshot: SessionSnapshotInfo,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """讀取快照內的 WBS、DSM 與 metadata。"""
    metadataPath = snapshot.snapshotDir / SNAPSHOT_META_FILENAME
    metadata = json.loads(metadataPath.read_text(encoding="utf-8"))
    wbsDf = pd.read_csv(
        snapshot.snapshotDir / SNAPSHOT_WBS_FILENAME,
        encoding="utf-8-sig",
    )
    dsmDf = readDsm(str(snapshot.snapshotDir / SNAPSHOT_DSM_FILENAME))
    validatedWbs, validatedDsm = validateEditorInputs(wbsDf, dsmDf)
    return validatedWbs, validatedDsm, metadata


def getLatestSourceMtime(session: DsmEditorSession) -> float | None:
    """回傳來源檔案的最新修改時間。"""
    mtimes = []
    for sourcePath in (session.wbsPath, session.dsmPath):
        if not sourcePath:
            continue
        path = Path(sourcePath)
        if path.exists():
            mtimes.append(path.stat().st_mtime)
    if not mtimes:
        return None
    return max(mtimes)
