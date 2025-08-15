# -*- coding: utf-8 -*-
"""
座標對齊與量化工具
幾何對齊功能，支援網格量化、容差對齊、座標規格化
"""

import math
from typing import List, Tuple, Union

# 全域常數
ALIGN_EPS = 0.5      # 對齊容差，小於此值視為相等
GRID = 1.0          # 網格間距，用於座標量化
MIN_SPACING = 2.0   # 最小間距，防止元素過度靠近


def snap_to_grid(value: float, grid_size: float = GRID) -> float:
    """
    將數值量化到最近的網格點
    
    Args:
        value: 原始數值
        grid_size: 網格間距
        
    Returns:
        量化後的數值
    """
    if grid_size <= 0:
        return value
    return round(value / grid_size) * grid_size


def align_within_tolerance(value: float, target: float, tolerance: float = ALIGN_EPS) -> float:
    """
    在容差範圍內對齊到目標值
    
    Args:
        value: 原始值
        target: 目標值
        tolerance: 容差範圍
        
    Returns:
        對齊後的值，若超出容差則返回原值
    """
    if abs(value - target) <= tolerance:
        return target
    return value


def quantize_coordinate(x: float, y: float, 
                       grid_size: float = GRID, 
                       tolerance: float = ALIGN_EPS) -> Tuple[float, float]:
    """
    量化座標點到網格，並應用容差對齊
    
    Args:
        x, y: 原始座標
        grid_size: 網格間距
        tolerance: 對齊容差
        
    Returns:
        量化後的座標 (x, y)
    """
    # 先量化到網格
    qx = snap_to_grid(x, grid_size)
    qy = snap_to_grid(y, grid_size)
    
    # 再檢查是否需要容差對齊
    qx = align_within_tolerance(qx, x, tolerance)
    qy = align_within_tolerance(qy, y, tolerance)
    
    return qx, qy


def quantize_path(path_points: List[Tuple[float, float]], 
                 grid_size: float = GRID, 
                 tolerance: float = ALIGN_EPS) -> List[Tuple[float, float]]:
    """
    量化整條路徑的所有點
    
    Args:
        path_points: 路徑點列表 [(x1,y1), (x2,y2), ...]
        grid_size: 網格間距
        tolerance: 對齊容差
        
    Returns:
        量化後的路徑點列表
    """
    return [quantize_coordinate(x, y, grid_size, tolerance) 
            for x, y in path_points]


def is_aligned(value1: float, value2: float, tolerance: float = ALIGN_EPS) -> bool:
    """
    檢查兩個數值是否在容差範圍內對齊
    
    Args:
        value1, value2: 待比較的數值
        tolerance: 容差範圍
        
    Returns:
        True 如果對齊，False 否則
    """
    return abs(value1 - value2) <= tolerance


def align_to_reference_points(value: float, 
                            reference_points: List[float], 
                            tolerance: float = ALIGN_EPS) -> float:
    """
    將數值對齊到最近的參考點
    
    Args:
        value: 待對齊的數值
        reference_points: 參考點列表
        tolerance: 對齊容差
        
    Returns:
        對齊後的數值，若沒有在容差內的參考點則返回原值
    """
    for ref_point in reference_points:
        if abs(value - ref_point) <= tolerance:
            return ref_point
    return value


def enforce_minimum_spacing(coordinates: List[float], 
                          min_spacing: float = MIN_SPACING) -> List[float]:
    """
    強制執行最小間距，調整過近的座標
    
    Args:
        coordinates: 座標列表（已排序）
        min_spacing: 最小允許間距
        
    Returns:
        調整後的座標列表
    """
    if len(coordinates) <= 1:
        return coordinates[:]
    
    result = [coordinates[0]]  # 第一個座標不變
    
    for coord in coordinates[1:]:
        last_coord = result[-1]
        if coord - last_coord < min_spacing:
            # 調整到最小間距
            adjusted_coord = last_coord + min_spacing
            result.append(adjusted_coord)
        else:
            result.append(coord)
    
    return result


def detect_alignment_clusters(values: List[float], 
                            tolerance: float = ALIGN_EPS) -> List[List[int]]:
    """
    偵測數值群集，將接近的數值歸類為同一群
    
    Args:
        values: 數值列表
        tolerance: 群集容差
        
    Returns:
        群集索引列表，每個群集包含原數值在 values 中的索引
    """
    if not values:
        return []
    
    # 按值排序，保留原始索引
    indexed_values = [(val, i) for i, val in enumerate(values)]
    indexed_values.sort()
    
    clusters = []
    current_cluster = [indexed_values[0][1]]  # 存放原始索引
    current_value = indexed_values[0][0]
    
    for val, orig_idx in indexed_values[1:]:
        if abs(val - current_value) <= tolerance:
            # 屬於同一群集
            current_cluster.append(orig_idx)
        else:
            # 開始新群集
            clusters.append(current_cluster)
            current_cluster = [orig_idx]
            current_value = val
    
    # 添加最後一個群集
    if current_cluster:
        clusters.append(current_cluster)
    
    return clusters


def consolidate_clusters(values: List[float], 
                       tolerance: float = ALIGN_EPS,
                       method: str = 'mean') -> List[float]:
    """
    合併接近的數值群集為代表值
    
    Args:
        values: 原始數值列表
        tolerance: 群集容差
        method: 合併方法 ('mean', 'median', 'min', 'max')
        
    Returns:
        合併後的數值列表
    """
    if not values:
        return []
    
    clusters = detect_alignment_clusters(values, tolerance)
    result = [0.0] * len(values)
    
    for cluster_indices in clusters:
        # 獲取群集中的數值
        cluster_values = [values[i] for i in cluster_indices]
        
        # 計算代表值
        if method == 'mean':
            representative = sum(cluster_values) / len(cluster_values)
        elif method == 'median':
            sorted_vals = sorted(cluster_values)
            n = len(sorted_vals)
            representative = sorted_vals[n // 2] if n % 2 == 1 else (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
        elif method == 'min':
            representative = min(cluster_values)
        elif method == 'max':
            representative = max(cluster_values)
        else:
            representative = cluster_values[0]  # 預設使用第一個
        
        # 將代表值指派給群集中的所有索引
        for idx in cluster_indices:
            result[idx] = representative
    
    return result