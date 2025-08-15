"""
Band-based TB V-H-V routing helpers (phase 1~3 skeleton)

This module provides minimal, testable building blocks for the advanced
two-band TB routing pipeline described in the project prompt. It focuses on:

1) Straight-line preprocessing (vertical lines only for now) with obstacle
   checks and conflict resolution.
2) Simple band lane assignment using interval partitioning (first-fit) with a
   stable ordering. This computes lane indices per edge; geometry is produced
   by the caller using a desired y_mid for V-H-V paths.
3) Main-rectangle fallback (currently equivalent to interval partitioning on
   remaining edges). This skeleton can be extended with height profiles and
   dual-band logic later.

All APIs are pure-Python and avoid PyQt types except for QPointF where
necessary to keep type hints friendly to the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Dict, Iterable, Optional

from PyQt5.QtCore import QPointF, QRectF


# ---------- Utilities ----------

def near(a: float, b: float, tol: float = 1.0) -> bool:
    return abs(a - b) <= tol


def _seg_overlaps(a1: float, a2: float, b1: float, b2: float, closed: bool = False) -> bool:
    """Check if 1D segments [a1,a2] and [b1,b2] overlap.
    If closed=False, touching at endpoints is considered non-overlap.
    """
    if a1 > a2:
        a1, a2 = a2, a1
    if b1 > b2:
        b1, b2 = b2, b1
    if closed:
        return not (a2 < b1 or b2 < a1)
    return not (a2 <= b1 or b2 <= a1)


def rect_intersects_vertical_segment(rect: QRectF, x: float, y1: float, y2: float, strict_inside: bool = True) -> bool:
    """Return True if a vertical segment at x from y1..y2 crosses rect interior.
    If strict_inside=True, ignores touching at edges.
    """
    rx1, rx2 = rect.left(), rect.right()
    ry1, ry2 = rect.top(), rect.bottom()
    # x within rect's x-span
    inside_x = (rx1 < x < rx2) if strict_inside else (rx1 <= x <= rx2)
    if not inside_x:
        return False
    return _seg_overlaps(y1, y2, ry1, ry2, closed=not strict_inside)


# ---------- Phase 1: Straight-line preprocessing ----------

@dataclass
class VerticalCandidate:
    edge_index: int                 # index in the provided list
    x: float                        # shared x column
    y_top: float                    # min(y_start, y_end)
    y_bot: float                    # max(y_start, y_end)


def filter_vertical_candidates(
    edges: List[Tuple[QPointF, QPointF]],
    tol: float = 1.0
) -> List[VerticalCandidate]:
    """Identify vertical straight candidates (same X within tolerance).

    Args:
        edges: list of (ps, pt)
        tol: pixel tolerance for x equality
    Returns:
        List of VerticalCandidate
    """
    out: List[VerticalCandidate] = []
    for i, (ps, pt) in enumerate(edges):
        if near(ps.x(), pt.x(), tol):
            x = 0.5 * (ps.x() + pt.x())
            y1, y2 = ps.y(), pt.y()
            y_top, y_bot = (y1, y2) if y1 <= y2 else (y2, y1)
            out.append(VerticalCandidate(i, x, y_top, y_bot))
    return out


def los_ok_vertical(
    cand: VerticalCandidate,
    obstacles: Iterable[QRectF],
    strict_inside: bool = True
) -> bool:
    """Line-of-sight check for a vertical segment against obstacles."""
    for rect in obstacles:
        if rect_intersects_vertical_segment(rect, cand.x, cand.y_top, cand.y_bot, strict_inside=strict_inside):
            return False
    return True


def select_non_overlapping_verticals(
    cands: List[VerticalCandidate]
) -> List[VerticalCandidate]:
    """Resolve conflicts among vertical candidates on the same X column using
    interval scheduling (sort by end then pick non-overlapping). Touching at
    endpoints is allowed (non-overlap).
    """
    # Group by rounded x to 1e-1 to make buckets stable
    buckets: Dict[int, List[VerticalCandidate]] = {}
    for c in cands:
        key = int(round(c.x * 10))  # 0.1 px bucket
        buckets.setdefault(key, []).append(c)

    chosen: List[VerticalCandidate] = []
    for _, arr in buckets.items():
        arr.sort(key=lambda c: (c.y_bot, c.y_top, c.edge_index))
        last_end = -1e18
        for c in arr:
            if c.y_top >= last_end:  # allow touch
                chosen.append(c)
                last_end = c.y_bot
    return chosen


def preprocess_straight_edges(
    edges: List[Tuple[QPointF, QPointF]],
    obstacles_by_edge: List[List[QRectF]],
    tol: float = 1.0,
) -> Tuple[Dict[int, List[QPointF]], List[int]]:
    """Pick lockable straight (vertical) edges.

    Args:
        edges: [(ps, pt), ...]
        obstacles_by_edge: obstacles per edge (exclude its endpoints)
        tol: tolerance for vertical alignment
    Returns:
        (locked_paths_by_index, remaining_indices)
    """
    vcands = filter_vertical_candidates(edges, tol)
    # Keep only line-of-sight OK
    vcands = [c for c in vcands if los_ok_vertical(c, obstacles_by_edge[c.edge_index])]
    # Resolve overlaps among themselves
    selected = select_non_overlapping_verticals(vcands)
    locked: Dict[int, List[QPointF]] = {c.edge_index: [edges[c.edge_index][0], edges[c.edge_index][1]] for c in selected}
    remaining = [i for i in range(len(edges)) if i not in locked]
    return locked, remaining


# ---------- Phase 2/3: Simple band assignment and main rectangle ----------

@dataclass
class IntervalItem:
    idx: int
    xL: float
    xR: float


def stable_order(items: List[IntervalItem]) -> List[IntervalItem]:
    return sorted(items, key=lambda it: (it.xL, it.xR, it.idx))


def interval_partition_first_fit(items: List[IntervalItem]) -> Dict[int, int]:
    """Assign items to lanes using first-fit with a stable order.
    Returns: mapping idx -> lane (1-based)
    """
    lanes_rightmost: List[float] = []
    assignment: Dict[int, int] = {}
    for it in stable_order(items):
        placed = False
        for j, right in enumerate(lanes_rightmost):
            if right <= it.xL:  # non-overlap in this lane
                lanes_rightmost[j] = it.xR
                assignment[it.idx] = j + 1
                placed = True
                break
        if not placed:
            lanes_rightmost.append(it.xR)
            assignment[it.idx] = len(lanes_rightmost)
    return assignment


def assign_main_rectangle(edges: List[Tuple[QPointF, QPointF]]) -> Dict[int, int]:
    """Main-rectangle fallback as classic interval partitioning on [minX,maxX].
    Returns: index -> lane (1-based)
    """
    items = [IntervalItem(i, min(ps.x(), pt.x()), max(ps.x(), pt.x())) for i, (ps, pt) in enumerate(edges)]
    return interval_partition_first_fit(items)


def assign_band_lanes_for_tb_vhv(
    edges: List[Tuple[QPointF, QPointF]],
    lane_spacing: float = 16.0,
) -> Tuple[Dict[int, int], float]:
    """Simplified band assignment: treat each edge's horizontal span [xL,xR]
    and assign lanes via first-fit. Returns (idx->lane, suggested_base_y_offset).

    The base_y_offset is a hint for the caller to place the middle H segment;
    actual geometry is produced by the caller (e.g., manager) using stubs and
    clamping between source/target clearance.
    """
    items = [IntervalItem(i, min(ps.x(), pt.x()), max(ps.x(), pt.x())) for i, (ps, pt) in enumerate(edges)]
    assignment = interval_partition_first_fit(items)

    # Suggest a neutral base ratio for y_mid (0.5 between ends)
    # Caller should snap/clamp.
    return assignment, lane_spacing


# Convenience to compute a y_mid per edge given an assigned lane and bounds

def compute_y_mid(
    s_out_y: float,
    t_in_y: float,
    lane: int,
    lane_spacing: float,
    min_clear: float = 12.0,
) -> float:
    y_low = s_out_y + min_clear
    y_high = t_in_y - min_clear
    # Base at midpoint, then push down by (lane-1)*spacing within [y_low,y_high]
    raw = 0.5 * (s_out_y + t_in_y) + (lane - 1) * lane_spacing
    if raw < y_low:
        return y_low
    if raw > y_high:
        return y_high
    return raw


# ---------- Vertical collision map + placement with checks ----------

def _x_bucket(x: float, grid: float = 1.0) -> int:
    return int(round(x / grid))


def vmap_can_add(vmap: Dict[int, List[Tuple[float, float]]], x: float, y1: float, y2: float, grid: float = 1.0) -> bool:
    """Check whether we can add a vertical segment [y1,y2] at column x without overlapping.
    Touching at endpoints is allowed.
    """
    if y1 > y2:
        y1, y2 = y2, y1
    b = _x_bucket(x, grid)
    spans = vmap.get(b, [])
    for a, bnd in spans:
        ay, by = a, bnd
        # overlap if not (y2 <= ay or by <= y1)
        if not (y2 <= ay or by <= y1):
            return False
    return True


def vmap_add(vmap: Dict[int, List[Tuple[float, float]]], x: float, y1: float, y2: float, grid: float = 1.0) -> None:
    if y1 > y2:
        y1, y2 = y2, y1
    b = _x_bucket(x, grid)
    arr = vmap.setdefault(b, [])
    # insert sorted by start
    i = 0
    while i < len(arr) and arr[i][0] < y1:
        i += 1
    arr.insert(i, (y1, y2))


def validate_vmap(vmap: Dict[int, List[Tuple[float, float]]]) -> bool:
    """Ensure no overlaps within each x bucket; assumes arr sorted by start."""
    for b, arr in vmap.items():
        for i in range(1, len(arr)):
            prev = arr[i - 1]
            cur = arr[i]
            if not (prev[1] <= cur[0]):  # allow touch only
                return False
    return True


def validate_lane_non_overlap(assignment: Dict[int, int], edges: List[Tuple[QPointF, QPointF]]) -> bool:
    """Ensure no horizontal overlap within each lane for provided assignment."""
    by_lane: Dict[int, List[Tuple[float, float]]] = {}
    for idx, lane in assignment.items():
        ps, pt = edges[idx]
        xL = min(ps.x(), pt.x())
        xR = max(ps.x(), pt.x())
        if xR <= xL:
            continue
        by_lane.setdefault(lane, []).append((xL, xR))
    # check lane by lane
    for lane, arr in by_lane.items():
        arr.sort(key=lambda t: (t[0], t[1]))
        last_r = -1e18
        for xL, xR in arr:
            if xL < last_r:  # overlap detected
                return False
            last_r = xR
    return True


def assign_band_with_vertical_checks(
    edges: List[Tuple[QPointF, QPointF]],
    stubs_y: List[Tuple[float, float]],
    lane_spacing: float,
    vertical_map: Dict[int, List[Tuple[float, float]]],
    vgrid: float = 1.0,
    low_lanes: Optional[List[int]] = None,
) -> Tuple[Dict[int, int], List[int]]:
    """Assign lanes with first-fit while checking vertical collisions at both ends.

    Args:
        edges: [(ps, pt)]
        stubs_y: [(s_out_y, t_in_y)] corresponding to edges
        lane_spacing: spacing between lanes (for y_mid computation)
        vertical_map: shared x-column map (will be mutated)
    Returns:
        (assignment idx->lane, failed_indices)
    """
    items = [IntervalItem(i, min(ps.x(), pt.x()), max(ps.x(), pt.x())) for i, (ps, pt) in enumerate(edges)]
    assignment: Dict[int, int] = {}
    lane_right: List[float] = []
    failed: List[int] = []

    for it in stable_order(items):
        ps, pt = edges[it.idx]
        s_out_y, t_in_y = stubs_y[it.idx]
        placed = False
        # try lanes
        start_lane = 1
        if low_lanes is not None:
            start_lane = max(1, low_lanes[it.idx])
        for j in range(start_lane - 1, len(lane_right) + 1):
            # horizontal availability
            if j < len(lane_right) and lane_right[j] > it.xL:
                continue
            lane = j + 1
            y_mid = compute_y_mid(s_out_y, t_in_y, lane, lane_spacing)
            # vertical segments to check
            ok1 = vmap_can_add(vertical_map, ps.x(), ps.y(), y_mid, grid=vgrid)
            ok2 = vmap_can_add(vertical_map, pt.x(), y_mid, pt.y(), grid=vgrid)
            if ok1 and ok2:
                # place
                if j == len(lane_right):
                    lane_right.append(it.xR)
                else:
                    lane_right[j] = it.xR
                assignment[it.idx] = lane
                vmap_add(vertical_map, ps.x(), ps.y(), y_mid, grid=vgrid)
                vmap_add(vertical_map, pt.x(), y_mid, pt.y(), grid=vgrid)
                placed = True
                break
        if not placed:
            failed.append(it.idx)
    return assignment, failed


# ---------- Height profile (sweep-based, compressed steps) ----------

def build_profile(fragments: List[Tuple[float, float, float]]) -> List[Tuple[float, float, float]]:
    """Build a compressed step profile from [xL,xR,need] fragments by sweep.
    Adjacent equal values are merged. Assumes need >= 0.
    """
    events: List[Tuple[float, float]] = []
    for xL, xR, need in fragments:
        if xR <= xL:
            continue
        events.append((xL, +need))
        events.append((xR, -need))
    events.sort(key=lambda e: e[0])

    prof: List[Tuple[float, float, float]] = []
    cur = 0.0
    prev_x: Optional[float] = None
    for x, delta in events:
        if prev_x is not None and x > prev_x and cur > 0:
            if prof and abs(prof[-1][2] - cur) < 1e-6 and abs(prof[-1][1] - prev_x) < 1e-6:
                # merge
                prof[-1] = (prof[-1][0], x, cur)
            else:
                prof.append((prev_x, x, cur))
        cur += delta
        prev_x = x
    return prof


def range_max(profile: List[Tuple[float, float, float]], xL: float, xR: float) -> float:
    """Return max need across [xL,xR] on the compressed profile (linear scan)."""
    if xR < xL:
        xL, xR = xR, xL
    m = 0.0
    for a, b, v in profile:
        if b <= xL or a >= xR:
            continue
        if v > m:
            m = v
    return m


def to_lane(need: float, lane_spacing: float) -> int:
    if lane_spacing <= 0:
        return 1
    from math import ceil
    return max(1, int(ceil(need / lane_spacing)))


def mark_low_lane(
    edges: List[Tuple[QPointF, QPointF]],
    profile: List[Tuple[float, float, float]],
    lane_spacing: float,
) -> List[int]:
    """Compute per-edge minimal lane index from profile over its [xL,xR] span."""
    lows: List[int] = []
    for ps, pt in edges:
        xL = min(ps.x(), pt.x())
        xR = max(ps.x(), pt.x())
        need = range_max(profile, xL, xR)
        lows.append(to_lane(need, lane_spacing))
    return lows
