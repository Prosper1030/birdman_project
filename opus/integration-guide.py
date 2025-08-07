"""
整合改進到 dsm_editor.py 的完整代碼片段
"""

# 1. 替換 EdgeItem 類的 updatePath 方法
def updatePath(self) -> None:
    """更新路徑 - 使用精確的交點計算"""
    if not self.src or not self.dst:
        return

    # 獲取節點的場景邊界矩形
    srcRect = self.src.sceneBoundingRect()
    dstRect = self.dst.sceneBoundingRect()

    # 獲取中心點
    srcCenter = srcRect.center()
    dstCenter = dstRect.center()

    # 建立中心連線
    from PyQt5.QtCore import QLineF
    centerLine = QLineF(srcCenter, dstCenter)
    
    # 計算精確的交點
    srcPoint = self.getExactIntersectionPoint(srcRect, centerLine, True)
    dstPoint = self.getExactIntersectionPoint(dstRect, centerLine, False)

    # 如果交點計算失敗，使用備用方法
    if not srcPoint:
        srcPoint = self.getFallbackConnectionPoint(srcRect, srcCenter, dstCenter)
    if not dstPoint:
        dstPoint = self.getFallbackConnectionPoint(dstRect, dstCenter, srcCenter)

    # 建立路徑
    path = QPainterPath()
    path.moveTo(srcPoint)
    
    # 計算箭頭調整後的終點（避免箭頭穿透節點）
    adjustedDstPoint = self.calculateArrowAdjustedEndpoint(srcPoint, dstPoint)
    path.lineTo(adjustedDstPoint)
    
    self.setPath(path)

    # 更新箭頭，使其尖端精確指向節點邊緣
    self.updateArrowHead(srcPoint, dstPoint, adjustedDstPoint)


# 2. 修改 DsmScene 的 updateTempConnection 方法
def updateTempConnection(self, mousePos: QPointF) -> None:
    """更新臨時連線 - 使用精確計算"""
    if not self.tempEdge or not self.sourceNode:
        return

    # 獲取源節點矩形
    srcRect = self.sourceNode.sceneBoundingRect()
    srcCenter = srcRect.center()
    
    # 建立從源中心到滑鼠位置的線
    from PyQt5.QtCore import QLineF
    tempLine = QLineF(srcCenter, mousePos)
    
    # 計算源節點的精確出發點
    srcPoint = self.tempEdge.getExactIntersectionPoint(srcRect, tempLine, True)
    if not srcPoint:
        srcPoint = self.tempEdge.getFallbackConnectionPoint(srcRect, srcCenter, mousePos)
    
    # 檢查滑鼠是否懸停在目標節點上
    targetItem = self.itemAt(mousePos, self.views()[0].transform())
    
    if isinstance(targetItem, TaskNode) and targetItem != self.sourceNode:
        # 滑鼠在目標節點上，計算精確的目標點
        targetRect = targetItem.sceneBoundingRect()
        targetCenter = targetRect.center()
        
        # 從源點到目標中心的線
        targetLine = QLineF(srcPoint, targetCenter)
        
        # 計算精確的目標交點
        targetPoint = self.tempEdge.getExactIntersectionPoint(targetRect, targetLine, False)
        if not targetPoint:
            targetPoint = self.tempEdge.getFallbackConnectionPoint(targetRect, targetCenter, srcPoint)
        
        # 建立精確路徑
        path = QPainterPath()
        path.moveTo(srcPoint)
        path.lineTo(targetPoint)
        self.tempEdge.setPath(path)
        
        # 更新箭頭
        if hasattr(self.tempEdge, 'updateArrowHead'):
            adjustedTarget = self.tempEdge.calculateArrowAdjustedEndpoint(srcPoint, targetPoint)
            self.tempEdge.updateArrowHead(srcPoint, targetPoint, adjustedTarget)
        
        # 高亮目標節點
        if self.last_hovered_target != targetItem:
            if self.last_hovered_target:
                self.last_hovered_target.set_highlight(False)
            targetItem.set_highlight(True)
            self.last_hovered_target = targetItem
    else:
        # 滑鼠在空白處，連線到滑鼠位置
        path = QPainterPath()
        path.moveTo(srcPoint)
        path.lineTo(mousePos)
        self.tempEdge.setPath(path)
        
        # 更新箭頭
        if hasattr(self.tempEdge, 'updateArrowHead'):
            self.tempEdge.updateArrowHead(srcPoint, mousePos, mousePos)
        
        # 清除高亮
        if self.last_hovered_target:
            self.last_hovered_target.set_highlight(False)
            self.last_hovered_target = None


# 3. 完整的測試程式碼
def test_edge_precision():
    """測試連線精確度的函數"""
    import sys
    from PyQt5.QtWidgets import QApplication, QGraphicsView, QGraphicsScene
    from PyQt5.QtCore import QRectF
    
    app = QApplication(sys.argv)
    
    # 建立場景和視圖
    scene = QGraphicsScene()
    view = QGraphicsView(scene)
    
    # 建立測試節點
    node1 = TaskNode("1", "Node 1", QColor(255, 215, 0), None)
    node2 = TaskNode("2", "Node 2", QColor(255, 215, 0), None)
    
    node1.setPos(0, 0)
    node2.setPos(200, 100)
    
    scene.addItem(node1)
    scene.addItem(node2)
    
    # 建立精確連線
    edge = EdgeItem(node1, node2)
    scene.addItem(edge)
    
    # 測試不同角度的連線
    test_positions = [
        (200, 0),    # 水平
        (0, 200),    # 垂直
        (200, 200),  # 對角線
        (-200, 100), # 反向
    ]
    
    for x, y in test_positions:
        node2.setPos(x, y)
        edge.updatePath()
        
        # 驗證連線是否精確接觸
        path = edge.path()
        start_point = path.elementAt(0)
        end_point = path.elementAt(path.elementCount() - 1)
        
        print(f"Position ({x}, {y}):")
        print(f"  Start: ({start_point.x:.2f}, {start_point.y:.2f})")
        print(f"  End: ({end_point.x:.2f}, {end_point.y:.2f})")
    
    view.show()
    sys.exit(app.exec_())


# 4. 性能優化建議
class OptimizedEdgeItem(EdgeItem):
    """優化版本的 EdgeItem，包含快取機制"""
    
    def __init__(self, src, dst):
        super().__init__(src, dst)
        self._path_cache = {}
        self._last_src_rect = None
        self._last_dst_rect = None
    
    def updatePath(self):
        """使用快取優化的路徑更新"""
        if not self.src or not self.dst:
            return
        
        srcRect = self.src.sceneBoundingRect()
        dstRect = self.dst.sceneBoundingRect()
        
        # 檢查是否需要重新計算
        if (self._last_src_rect == srcRect and 
            self._last_dst_rect == dstRect):
            return  # 位置沒有變化，不需要更新
        
        # 清除快取並重新計算
        self._path_cache.clear()
        self._last_src_rect = QRectF(srcRect)
        self._last_dst_rect = QRectF(dstRect)
        
        # 調用父類的更新方法
        super().updatePath()


# 5. 處理特殊形狀節點的擴展
class ShapeAwareEdgeItem(EdgeItem):
    """支援不同形狀節點的連線"""
    
    def getNodeShapeIntersection(self, node, line):
        """根據節點形狀計算交點"""
        if hasattr(node, 'shape_type'):
            if node.shape_type == 'ellipse':
                return self.getEllipseIntersection(node, line)
            elif node.shape_type == 'rounded_rect':
                return self.getRoundedRectIntersection(node, line)
            elif node.shape_type == 'diamond':
                return self.getDiamondIntersection(node, line)
        
        # 預設為矩形
        return self.getExactIntersectionPoint(node.sceneBoundingRect(), line, True)
    
    def getEllipseIntersection(self, node, line):
        """計算線與橢圓的交點"""
        rect = node.sceneBoundingRect()
        center = rect.center()
        a = rect.width() / 2  # 半長軸
        b = rect.height() / 2  # 半短軸
        
        # 將線段轉換為參數方程
        p1 = line.p1()
        p2 = line.p2()
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        
        # 平移到橢圓中心為原點
        x0 = p1.x() - center.x()
        y0 = p1.y() - center.y()
        
        # 求解二次方程
        A = (dx * dx) / (a * a) + (dy * dy) / (b * b)
        B = 2 * ((x0 * dx) / (a * a) + (y0 * dy) / (b * b))
        C = (x0 * x0) / (a * a) + (y0 * y0) / (b * b) - 1
        
        discriminant = B * B - 4 * A * C
        if discriminant < 0:
            return None
        
        # 計算參數t
        sqrt_disc = math.sqrt(discriminant)
        t1 = (-B - sqrt_disc) / (2 * A)
        t2 = (-B + sqrt_disc) / (2 * A)
        
        # 選擇合適的t值
        t = t2 if t2 >= 0 and t2 <= 1 else t1
        
        if t < 0 or t > 1:
            return None
        
        # 計算交點
        x = p1.x() + t * dx
        y = p1.y() + t * dy
        
        return QPointF(x, y)