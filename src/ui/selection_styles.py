#!/usr/bin/env python3
"""
通用選取狀態視覺系統
實現降彩度的選取效果，適用於任何顏色
"""

from PyQt5.QtGui import QColor, QPen, QBrush
from PyQt5.QtCore import Qt
from typing import Tuple, Optional


class SelectionStyleManager:
    """選取狀態樣式管理器"""
    
    @staticmethod
    def desaturate_color(color, desaturation_factor: float = 0.6) -> QColor:
        """
        降低顏色彩度，製造選取效果
        
        Args:
            color: 原始顏色 (QColor 或 Qt.GlobalColor)
            desaturation_factor: 降彩度係數 (0.0-1.0，越大越灰)
            
        Returns:
            降彩度後的顏色
        """
        # 確保是 QColor 對象
        if not isinstance(color, QColor):
            color = QColor(color)
            
        # 轉換為 HSV 色彩空間
        h = color.hue()
        s = color.saturation()
        v = color.value()
        a = color.alpha()
        
        # 降低彩度
        new_saturation = int(s * (1.0 - desaturation_factor))
        
        # 創建新顏色
        desaturated = QColor()
        desaturated.setHsv(h, new_saturation, v, a)
        return desaturated
    
    @staticmethod
    def brighten_color(color, brightness_factor: float = 0.3) -> QColor:
        """
        提高顏色亮度，製造懸停效果
        
        Args:
            color: 原始顏色 (QColor 或 Qt.GlobalColor)
            brightness_factor: 提亮係數 (0.0-1.0)
            
        Returns:
            提亮後的顏色
        """
        # 確保是 QColor 對象
        if not isinstance(color, QColor):
            color = QColor(color)
            
        # 轉換為 HSV 色彩空間
        h = color.hue()
        s = color.saturation()
        v = color.value()
        a = color.alpha()
        
        # 提高明度
        new_value = min(255, int(v + (255 - v) * brightness_factor))
        
        # 創建新顏色
        brightened = QColor()
        brightened.setHsv(h, s, new_value, a)
        return brightened
    
    @staticmethod
    def create_selection_pen(original_pen: QPen, selection_mode: str = "selected") -> QPen:
        """
        基於原始筆刷創建選取狀態的筆刷
        
        Args:
            original_pen: 原始筆刷
            selection_mode: "selected", "hovered", 或 "focused"
            
        Returns:
            選取狀態的筆刷
        """
        new_pen = QPen(original_pen)
        original_color = original_pen.color()
        
        if selection_mode == "selected":
            # 選取狀態：降彩度 + 加粗
            selected_color = SelectionStyleManager.desaturate_color(original_color, 0.5)
            new_pen.setColor(selected_color)
            new_pen.setWidth(original_pen.width() + 2)
            new_pen.setStyle(Qt.SolidLine)
            
        elif selection_mode == "hovered":
            # 懸停狀態：提亮 + 稍微加粗
            hovered_color = SelectionStyleManager.brighten_color(original_color, 0.2)
            new_pen.setColor(hovered_color)
            new_pen.setWidth(original_pen.width() + 1)
            
        elif selection_mode == "focused":
            # 聚焦狀態：保持原色 + 虛線邊框
            new_pen.setColor(original_color)
            new_pen.setWidth(original_pen.width() + 3)
            new_pen.setStyle(Qt.DashLine)
            
        return new_pen
    
    @staticmethod
    def create_selection_brush(original_brush: QBrush, selection_mode: str = "selected") -> QBrush:
        """
        基於原始筆刷創建選取狀態的筆刷
        
        Args:
            original_brush: 原始筆刷
            selection_mode: "selected", "hovered", 或 "focused"
            
        Returns:
            選取狀態的筆刷
        """
        new_brush = QBrush(original_brush)
        original_color = original_brush.color()
        
        if selection_mode == "selected":
            # 選取狀態：降彩度
            selected_color = SelectionStyleManager.desaturate_color(original_color, 0.4)
            new_brush.setColor(selected_color)
            
        elif selection_mode == "hovered":
            # 懸停狀態：提亮
            hovered_color = SelectionStyleManager.brighten_color(original_color, 0.15)
            new_brush.setColor(hovered_color)
            
        elif selection_mode == "focused":
            # 聚焦狀態：保持原色，稍微透明
            focused_color = QColor(original_color)
            focused_color.setAlpha(int(original_color.alpha() * 0.8))
            new_brush.setColor(focused_color)
            
        return new_brush


class MultiSelectionManager:
    """多重選取管理器"""
    
    def __init__(self):
        self.selected_items = set()
        self.last_selected = None
        
    def add_to_selection(self, item, exclusive: bool = False):
        """添加項目到選取集合"""
        if exclusive:
            self.clear_selection()
            
        self.selected_items.add(item)
        self.last_selected = item
        
        # 更新項目的視覺狀態
        if hasattr(item, 'setSelected'):
            item.setSelected(True)
            
    def remove_from_selection(self, item):
        """從選取集合中移除項目"""
        self.selected_items.discard(item)
        
        if self.last_selected == item:
            self.last_selected = list(self.selected_items)[-1] if self.selected_items else None
            
        # 更新項目的視覺狀態
        if hasattr(item, 'setSelected'):
            item.setSelected(False)
            
    def toggle_selection(self, item):
        """切換項目的選取狀態"""
        if item in self.selected_items:
            self.remove_from_selection(item)
        else:
            self.add_to_selection(item)
            
    def clear_selection(self):
        """清除所有選取"""
        for item in list(self.selected_items):
            if hasattr(item, 'setSelected'):
                item.setSelected(False)
        
        self.selected_items.clear()
        self.last_selected = None
        
    def is_selected(self, item) -> bool:
        """檢查項目是否被選取"""
        return item in self.selected_items
        
    def get_selected_items(self) -> set:
        """獲取所有選取的項目"""
        return self.selected_items.copy()
        
    def get_selection_count(self) -> int:
        """獲取選取項目數量"""
        return len(self.selected_items)


class SelectionVisualizer:
    """選取視覺化輔助工具"""
    
    @staticmethod
    def create_selection_overlay_pen() -> QPen:
        """創建選取覆蓋層的筆刷（用於多選框等）"""
        pen = QPen(QColor(0, 120, 215), 2, Qt.DashLine)  # Windows 風格藍色
        return pen
        
    @staticmethod
    def create_selection_overlay_brush() -> QBrush:
        """創建選取覆蓋層的筆刷（用於多選框等）"""
        color = QColor(0, 120, 215, 50)  # 半透明藍色
        brush = QBrush(color)
        return brush
        
    @staticmethod
    def get_focus_indicator_pen() -> QPen:
        """獲取聚焦指示器筆刷"""
        pen = QPen(QColor(255, 165, 0), 3, Qt.DotLine)  # 橘色虛線
        return pen


class EdgeSelectionHelper:
    """邊線選取輔助工具"""
    
    @staticmethod
    def create_thick_selection_area(original_pen: QPen, thickness_multiplier: float = 3.0) -> QPen:
        """
        為邊線創建較粗的透明選取區域
        
        Args:
            original_pen: 原始邊線筆刷
            thickness_multiplier: 厚度倍數
            
        Returns:
            選取區域筆刷
        """
        selection_pen = QPen(original_pen)
        selection_pen.setWidth(int(original_pen.width() * thickness_multiplier))
        
        # 設為透明，只用於碰撞檢測
        transparent_color = QColor(original_pen.color())
        transparent_color.setAlpha(0)
        selection_pen.setColor(transparent_color)
        
        return selection_pen
        
    @staticmethod
    def is_point_near_line(point, line_start, line_end, tolerance: float = 8.0) -> bool:
        """
        檢查點是否靠近線段
        
        Args:
            point: 檢查的點
            line_start: 線段起點
            line_end: 線段終點
            tolerance: 容差範圍
            
        Returns:
            是否靠近線段
        """
        from PyQt5.QtCore import QLineF
        
        line = QLineF(line_start, line_end)
        distance = line.distance(point)
        return distance <= tolerance