#!/usr/bin/env python3
"""
動畫布局系統 - 提供平滑的布局過渡效果
"""

from typing import Dict, List, Callable, Optional
from PyQt5.QtCore import QTimer, QPointF, QObject, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtWidgets import QGraphicsItem


class LayoutAnimator(QObject):
    """布局動畫控制器"""
    
    # 信號
    animationStarted = pyqtSignal()
    animationFinished = pyqtSignal()
    animationProgress = pyqtSignal(float)  # 0.0 到 1.0
    
    def __init__(self):
        super().__init__()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_animation)
        
        # 動畫參數
        self.duration = 500  # 毫秒
        self.fps = 60  # 每秒幀數
        self.easing_curve = QEasingCurve.InOutCubic
        
        # 動畫狀態
        self.is_animating = False
        self.current_time = 0
        self.animations: List[NodeAnimation] = []
        
    def animate_layout(self, nodes: Dict, target_positions: Dict, 
                       duration: Optional[int] = None,
                       on_complete: Optional[Callable] = None):
        """
        執行布局動畫
        
        Args:
            nodes: {node_id: node_object} 節點字典
            target_positions: {node_id: QPointF} 目標位置
            duration: 動畫時長（毫秒）
            on_complete: 完成回調
        """
        if self.is_animating:
            self.stop_animation()
        
        if duration is not None:
            self.duration = duration
        
        # 準備動畫
        self.animations.clear()
        for node_id, node in nodes.items():
            if node_id in target_positions:
                start_pos = node.pos()
                end_pos = target_positions[node_id]
                
                if start_pos != end_pos:
                    anim = NodeAnimation(node, start_pos, end_pos)
                    self.animations.append(anim)
        
        if not self.animations:
            # 沒有需要動畫的節點
            if on_complete:
                on_complete()
            return
        
        # 開始動畫
        self.is_animating = True
        self.current_time = 0
        self.on_complete_callback = on_complete
        
        # 計算定時器間隔
        interval = int(1000 / self.fps)
        self.timer.setInterval(interval)
        self.timer.start()
        
        self.animationStarted.emit()
    
    def _update_animation(self):
        """更新動畫幀"""
        # 更新時間
        self.current_time += self.timer.interval()
        
        # 計算進度（0.0 到 1.0）
        progress = min(1.0, self.current_time / self.duration)
        
        # 應用緩動曲線
        eased_progress = self._apply_easing(progress)
        
        # 更新所有節點位置
        for anim in self.animations:
            anim.update(eased_progress)
        
        # 發送進度信號
        self.animationProgress.emit(progress)
        
        # 檢查是否完成
        if progress >= 1.0:
            self.stop_animation()
            self.animationFinished.emit()
            
            if hasattr(self, 'on_complete_callback') and self.on_complete_callback:
                self.on_complete_callback()
    
    def _apply_easing(self, t: float) -> float:
        """應用緩動函數"""
        if self.easing_curve == QEasingCurve.Linear:
            return t
        elif self.easing_curve == QEasingCurve.InOutCubic:
            # Cubic ease in-out
            if t < 0.5:
                return 4 * t * t * t
            else:
                p = 2 * t - 2
                return 1 + p * p * p / 2
        elif self.easing_curve == QEasingCurve.OutElastic:
            # Elastic ease out
            if t == 0 or t == 1:
                return t
            p = 0.3
            s = p / 4
            return pow(2, -10 * t) * sin((t - s) * 2 * pi / p) + 1
        else:
            # 預設使用 Qt 的緩動曲線
            curve = QEasingCurve(self.easing_curve)
            return curve.valueForProgress(t)
    
    def stop_animation(self):
        """停止動畫"""
        self.timer.stop()
        self.is_animating = False
        self.animations.clear()
    
    def set_duration(self, duration: int):
        """設定動畫時長（毫秒）"""
        self.duration = max(100, duration)
    
    def set_easing_curve(self, curve: QEasingCurve):
        """設定緩動曲線"""
        self.easing_curve = curve
    
    def set_fps(self, fps: int):
        """設定幀率"""
        self.fps = max(10, min(120, fps))


class NodeAnimation:
    """單個節點的動畫"""
    
    def __init__(self, node: QGraphicsItem, start_pos: QPointF, end_pos: QPointF):
        self.node = node
        self.start_pos = start_pos
        self.end_pos = end_pos
        
        # 計算差值
        self.delta_x = end_pos.x() - start_pos.x()
        self.delta_y = end_pos.y() - start_pos.y()
        
        # 保存邊線引用以便更新
        self.edges = getattr(node, 'edges', [])
    
    def update(self, progress: float):
        """更新節點位置"""
        # 插值計算新位置
        x = self.start_pos.x() + self.delta_x * progress
        y = self.start_pos.y() + self.delta_y * progress
        
        # 設定位置
        self.node.setPos(x, y)
        
        # 更新相關邊線
        for edge in self.edges:
            if hasattr(edge, 'updatePath'):
                edge.updatePath()


class SpringLayoutAnimator(LayoutAnimator):
    """彈簧布局動畫器 - 模擬物理彈簧效果"""
    
    def __init__(self):
        super().__init__()
        
        # 物理參數
        self.spring_constant = 0.1  # 彈簧常數
        self.damping = 0.9  # 阻尼係數
        self.mass = 1.0  # 節點質量
        
        # 速度追蹤
        self.velocities: Dict = {}
    
    def animate_spring_layout(self, nodes: Dict, target_positions: Dict):
        """使用彈簧物理模擬執行布局動畫"""
        # 初始化速度
        for node_id in nodes:
            if node_id not in self.velocities:
                self.velocities[node_id] = QPointF(0, 0)
        
        # 準備動畫
        self.nodes = nodes
        self.target_positions = target_positions
        self.is_animating = True
        
        # 使用更高的幀率以獲得更平滑的物理模擬
        self.fps = 60
        interval = int(1000 / self.fps)
        self.timer.setInterval(interval)
        self.timer.start()
        
        self.animationStarted.emit()
    
    def _update_spring_animation(self):
        """更新彈簧動畫"""
        dt = 1.0 / self.fps  # 時間步長
        
        total_displacement = 0
        
        for node_id, node in self.nodes.items():
            if node_id in self.target_positions:
                current_pos = node.pos()
                target_pos = self.target_positions[node_id]
                
                # 計算彈簧力
                dx = target_pos.x() - current_pos.x()
                dy = target_pos.y() - current_pos.y()
                
                fx = self.spring_constant * dx
                fy = self.spring_constant * dy
                
                # 獲取當前速度
                velocity = self.velocities.get(node_id, QPointF(0, 0))
                
                # 應用阻尼
                vx = velocity.x() * self.damping + fx * dt / self.mass
                vy = velocity.y() * self.damping + fy * dt / self.mass
                
                # 更新速度
                self.velocities[node_id] = QPointF(vx, vy)
                
                # 更新位置
                new_x = current_pos.x() + vx * dt
                new_y = current_pos.y() + vy * dt
                
                node.setPos(new_x, new_y)
                
                # 計算總位移
                total_displacement += abs(dx) + abs(dy)
                
                # 更新邊線
                if hasattr(node, 'edges'):
                    for edge in node.edges:
                        if hasattr(edge, 'updatePath'):
                            edge.updatePath()
        
        # 檢查是否達到穩定狀態
        if total_displacement < 1.0:  # 閾值
            self.stop_animation()
            self.animationFinished.emit()


import math
sin = math.sin
pi = math.pi