from enum import Enum


class EditorState(Enum):
    """編輯器狀態枚舉"""
    IDLE = "idle"
    CREATING_EDGE = "creating_edge"
    EDITING_TEXT = "editing_text"
    SELECTING = "selecting"
    RESIZING = "resizing"
    MOVING = "moving"


class LayoutAlgorithm(Enum):
    """佈局演算法枚舉"""
    HIERARCHICAL = "hierarchical"
    ORTHOGONAL = "orthogonal"
    FORCE_DIRECTED = "force_directed"