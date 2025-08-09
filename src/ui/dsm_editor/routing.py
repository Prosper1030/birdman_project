"""
DSM Editor 內建路由功能

整合了原本分散的路由功能，提供給 DSM Editor 使用的邊線路由能力。
如果未來需要高級路由功能，可以從 src/edge_routing.py 導入。
"""

from typing import List, Dict, Tuple
from PyQt5.QtCore import QPointF


class SimpleEdgeRouter:
    """
    簡單的邊線路由器
    
    提供基本的直線連接功能，未來可擴展為智能路由。
    """
    
    def __init__(self):
        """初始化路由器"""
        self.edges: List[Tuple[str, str]] = []
    
    def route_edge(self, start: QPointF, end: QPointF) -> List[QPointF]:
        """
        路由單條邊線
        
        Args:
            start: 起始點
            end: 終點
            
        Returns:
            路徑點列表
        """
        # 目前使用直線連接，未來可擴展為複雜路由
        return [start, end]
    
    def route_multiple_edges(self, edge_specs: List[Tuple[QPointF, QPointF]]) -> Dict[int, List[QPointF]]:
        """
        批量路由多條邊線
        
        Args:
            edge_specs: [(start_point, end_point), ...]
            
        Returns:
            {index: [path_points]}
        """
        result = {}
        for i, (start, end) in enumerate(edge_specs):
            result[i] = self.route_edge(start, end)
        return result
    
    def add_obstacles(self, obstacles: List[QPointF]):
        """
        添加障礙物 (未來功能)
        
        Args:
            obstacles: 障礙物位置列表
        """
        # TODO: 實現障礙物迴避
        pass