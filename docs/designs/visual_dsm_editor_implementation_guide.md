# **使用 PyQt5 打造互動式依賴關係編輯器之開發者指南**

## **導論：運用 QGraphicsScene 框架建構互動性架構**

PyQt5 的 `QGraphicsScene`/`QGraphicsView` 框架為開發 2D 向量圖形應用程式提供了強大而高效的基礎 。然而，要從一個基本的畫布轉變為一個如 yEd 般精緻、互動流暢的圖形編輯器，需要一套深思熟慮的架構設計。本指南旨在提供一份開發者導向的實作藍圖，其核心理念是將

`QGraphicsScene` 不僅僅視為一個顯示容器，而是作為管理跨項目（item）複雜互動的中央控制器 。

本報告將詳細闡述建構一個視覺化依賴關係編輯器的三個核心技術環節。我們將逐步建構以下幾個關鍵的自訂類別：

- `TaskNode`：繼承自 `QGraphicsObject`，代表圖中的一個可操作節點。

- `DependencyEdge`：繼承自 `QGraphicsLineItem`，代表節點之間的依賴關係連線。

- `EditorScene`：繼承自 `QGraphicsScene`，負責處理整體的互動邏輯、狀態管理以及與外部資料模型的通訊。

本指南所遵循的核心架構原則是「將互動與資料解耦」。視覺呈現與使用者互動（View/Controller）的邏輯將與底層的圖形資料結構（Model，例如一個 NetworkX 圖物件）嚴格分離。這種受模型-視圖-控制器（MVC）思想啟發的模式，是確保應用程式可維護性與擴展性的基石 。

## **第一部分：節點選取、拖曳與視覺回饋的實作**

本部分將聚焦於 `TaskNode` 類別的實作，使其具備選取、移動能力，並提供清晰的視覺回饋，同時確保與其相連的邊能夠即時、準確地更新。

### **1\.1 `TaskNode` 類別：基礎設定**

一個穩固的節點類別是所有互動的基礎。

#### **1\.1.1 繼承類別的選擇：`QGraphicsObject`**

開發的第一步是選擇正確的基底類別。雖然 `QGraphicsItem` 更為輕量，但此處建議繼承自 `QGraphicsObject`。`QGraphicsObject` 繼承自 `QObject`，使其原生支援 Qt 的信號與槽（signals and slots）機制。儘管在本架構中，主要的通訊將透過場景（Scene）進行，但採用 `QGraphicsObject` 是一個更具前瞻性的決策。它為未來可能需要節點自身發出信號的複雜功能（例如，節點內部按鈕的點擊事件）提供了內建的擴展性，而不會在當前應用場景中引入顯著的效能開銷 。

`QGraphicsItem` 無法直接發射信號是一個已知的限制，雖然可以透過場景代理發射信號來繞過，但從一開始就採用 `QGraphicsObject` 是更清晰、更優雅的架構選擇 。

#### **1\.1.2 設定必要的旗標 (Flags)**

在 `TaskNode` 的建構函式中，必須設定幾個關鍵的旗標以啟用框架的內建功能：

- `QGraphicsItem.ItemIsMovable`：允許使用者透過滑鼠拖曳來移動節點。

- `QGraphicsItem.ItemIsSelectable`：允許節點被選取。

- `QGraphicsItem.ItemSendsGeometryChanges`：這是至關重要的旗標。它確保每當節點的位置、變換或尺寸發生改變時，`itemChange` 方法會被呼叫。這是實現邊緣即時更新的核心機制 。

#### **1\.1.3 資料關聯**

每個 `TaskNode` 實例都必須儲存一個唯一識別碼（例如，來自 NetworkX 資料模型的節點名稱或 UUID）。這個識別碼是連結視覺物件與後端資料模型的橋樑，對於後續實現雙向資料同步至關重要。

**Python**

```python
from PyQt5.QtWidgets import QGraphicsObject, QGraphicsItem, QStyleOptionGraphicsItem, QStyle
from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor

class TaskNode(QGraphicsObject):
    def __init__(self, node_id: str, title: str, parent=None):
        super().__init__(parent)
        self.node_id = node_id
        self.title = title
        self._edges =
        self._is_highlighted = False

        # 設定旗標以啟用移動、選取和幾何變更通知
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        
        # 啟用懸停事件以進行目標高亮
        self.setAcceptHoverEvents(True)

    def boundingRect(self) -> QRectF:
        # 定義節點的邊界矩形
        return QRectF(0, 0, 120, 60)

    def add_edge(self, edge):
        """註冊一條與此節點相連的邊"""
        if edge not in self._edges:
            self._edges.append(edge)

    def remove_edge(self, edge):
        """移除一條與此節點相連的邊"""
        if edge in self._edges:
            self._edges.remove(edge)

    # 後續章節將實作 paint, mousePressEvent, itemChange 等方法

```



### **1\.2 精通選取：深入解析 `mousePressEvent`**

要實現類似 yEd 的多選邏輯（使用 SHIFT 或 CTRL），直接覆寫 `mousePressEvent` 是一個常見的陷阱。一個天真的覆寫會輕易地破壞 `QGraphicsItem` 內建的拖曳啟動機制 。

正確的模式不是從頭重新實作選取邏輯，而是引導並利用框架自身已經過最佳化的預設行為。核心策略是「事件修飾」，即在將事件傳遞給基底類別處理之前，根據需要修改事件的修飾鍵狀態。

- **單選**：當使用者點擊一個未選取的節點時，框架的預設行為會自動清除先前的選取並選取當前節點。

- **使用 CTRL/CMD 鍵多選**：這是框架的預設多選行為。按住 CTRL 鍵點擊會將節點加入或移出目前的選取集合。

- **使用 SHIFT 鍵多選**：為了模擬 yEd 的行為（SHIFT 也用於加入選取），我們需要在 `mousePressEvent` 中攔截此事件。如果偵測到 `Qt.ShiftModifier`，我們就以程式化的方式為事件物件添加 `Qt.ControlModifier` 旗標。這樣一來，當我們呼叫 `super().mousePressEvent(event)` 時，基底類別的實作會認為使用者按下了 CTRL 鍵，從而執行「加入選取」的邏輯 。

至關重要的是，無論進行何種判斷，最終都必須呼叫 `super().mousePressEvent(event)`，以確保選取狀態被正確更新，並且拖曳操作能夠被場景正確地初始化。

**Python**

```python
# 在 TaskNode 類別中
def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
    """處理滑鼠點擊事件，實現 SHIFT 鍵多選"""
    # 如果按下了 SHIFT 鍵，我們將其行為模擬為 CTRL 鍵，以觸發框架的「加入選取」邏輯
    if event.modifiers() & Qt.ShiftModifier:
        event.setModifiers(event.modifiers() | Qt.ControlModifier)
    
    super().mousePressEvent(event)

```

### **1\.3 自訂外觀：覆寫 `paint` 方法**

預設的選取指示器是一個通用的虛線矩形，這對於一個專業的編輯器來說是不夠的。我們需要一個自訂的視覺回饋，例如一個更粗、不同顏色的邊框。

要實現這一點，最優雅的技術是利用傳遞給 `paint` 方法的 `QStyleOptionGraphicsItem` 物件，而不是在 `paint` 方法中編寫複雜的 `if/else` 邏輯來重新繪製整個物件。這種方法具備非破壞性且易於維護的優點 。

其步驟如下 ：

1. 在 `paint` 方法內部，首先建立 `option` 參數的一個副本：`opt = QStyleOptionGraphicsItem(option)`。

2. 檢查物件是否被選取，可以透過 `self.isSelected()` 或 `(option.state & QStyle.State_Selected)` 來判斷。

3. 如果物件被選取，則執行自訂的繪圖操作（例如，繪製一個藍色的高亮邊框）。

4. **最關鍵的一步**：從副本 `opt` 中移除選取狀態：`opt.state &= ~QStyle.State_Selected`。

5. 最後，使用修改後的 `opt` 副本呼叫基底類別的 `paint` 方法：`super().paint(painter, opt, widget)`。

這個技巧巧妙地阻止了基底類別繪製其預設的虛線矩形，同時又讓我們能夠完全控制選取時的外觀，而無需複製物件本身所有的繪圖邏輯。

**Python**

```python
# 在 TaskNode 類別中
def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None):
    """繪製節點，並根據選取和高亮狀態提供視覺回饋"""
    # 建立 option 的副本以進行修改，避免影響原始狀態
    opt = QStyleOptionGraphicsItem(option)
    
    # 如果節點被選取，則不繪製預設的虛線框
    if opt.state & QStyle.State_Selected:
        opt.state &= ~QStyle.State_Selected

    # 基礎繪製
    painter.setBrush(QBrush(QColor("#E0E0E0")))
    painter.setPen(QPen(Qt.black, 1))
    painter.drawRoundedRect(self.boundingRect(), 5, 5)
    
    # 繪製標題
    painter.drawText(self.boundingRect(), Qt.AlignCenter, self.title)

    # 繪製選取時的高亮邊框
    if option.state & QStyle.State_Selected:
        pen = QPen(QColor("#0078D7"), 2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(self.boundingRect().adjusted(1, 1, -1, -1), 5, 5)

    # 繪製作為連線目標時的高亮效果
    if self._is_highlighted:
        pen = QPen(QColor("#2ECC71"), 2, Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(self.boundingRect(), 5, 5)

def set_highlight(self, highlighted: bool):
    """設定節點是否作為有效目標高亮"""
    if self._is_highlighted!= highlighted:
        self._is_highlighted = highlighted
        self.update() # 觸發重繪

```



### **1\.4 透過 `itemChange` 實現邊的即時同步**

當節點被拖曳時，與之相連的邊必須即時更新。實現此功能的最佳機制是覆寫 `QGraphicsItem.itemChange` 方法。這個方法是框架提供的、用於回應項目狀態變更的標準掛鉤，遠比輪詢或在 `mouseMoveEvent` 中處理更高效、更準確。

實作流程如下：

1. 在 `TaskNode` 中覆寫 `itemChange(self, change, value)` 方法。

2. 在方法內，檢查 `change` 參數是否等於 `QGraphicsItem.ItemPositionHasChanged`。這個事件在節點的位置因拖曳而實際改變後觸發 。

3. 如果條件成立，則遍歷節點內部維護的邊緣列表（`self._edges`），並在每個 `DependencyEdge` 物件上呼叫其 `adjust()` 方法。這個模式是 Qt 官方 "Elastic Nodes" 範例以及其他多個健壯實作中所採用的標準實踐 。

4. `DependencyEdge` 類別需要實作 `adjust()` 方法。此方法負責從其源節點和目標節點獲取最新的中心點位置，然後使用 `setLine()` 更新自身的線段幾何。在更新幾何之前，必須呼叫 `prepareGeometryChange()`，以通知場景其幾何形狀即將改變，從而確保場景索引能夠正確更新，避免繪圖錯誤 。

**Python**

```python
# 在 TaskNode 類別中
def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
    """
    覆寫 itemChange 以在節點移動時更新相連的邊。
    這是處理此類更新的官方推薦方式。
    """
    if change == QGraphicsItem.ItemPositionHasChanged:
        for edge in self._edges:
            edge.adjust() # 通知每條邊進行自我調整
    
    return super().itemChange(change, value)

# DependencyEdge 類別的實作
class DependencyEdge(QGraphicsLineItem):
    def __init__(self, source_node: TaskNode, dest_node: TaskNode, parent=None):
        super().__init__(parent)
        self.source = source_node
        self.dest = dest_node
        self.source.add_edge(self)
        self.dest.add_edge(self)

        self.setPen(QPen(Qt.black, 2))
        self.setZValue(-1) # 確保邊在節點下方繪製
        self.adjust()

    def adjust(self):
        """根據源和目標節點的位置更新邊的線段"""
        if not self.source or not self.dest:
            return
        
        # 獲取源和目標節點的中心點
        source_point = self.mapFromItem(self.source, self.source.boundingRect().center())
        dest_point = self.mapFromItem(self.dest, self.dest.boundingRect().center())
        
        # 準備幾何變更並設定新的線段
        self.prepareGeometryChange()
        self.setLine(QLineF(source_point, dest_point))

    def remove(self):
        """從節點中移除此邊的引用"""
        self.source.remove_edge(self)
        self.dest.remove_edge(self)

```



## **第二部分：依賴關係邊的創建狀態機**

本部分將焦點轉移到 `EditorScene` 類別，它將負責管理從點擊源節點到釋放滑鼠以建立新連線的整個複雜互動過程。這個過程最好透過一個明確定義的狀態機來管理。

### **2\.1 邊創建的狀態與轉換**

為了精確複製 yEd 的互動體驗，我們需要一個狀態機來管理邊的創建流程。`EditorScene` 將使用一個內部屬性（例如 `self.mode`）來追蹤目前的狀態。

**狀態定義**：

- `IDLE`：預設狀態。場景處於閒置，等待使用者操作。

- `START_CONNECTION`：使用者在一個有效的源節點上按下了滑鼠左鍵，準備開始拖曳一條新的邊。

- `DRAGGING_EDGE`：使用者正按住滑鼠左鍵並移動，一條預覽線（rubber band line）跟隨滑鼠游標。

- `VALID_TARGET_HOVER`：在 `DRAGGING_EDGE` 狀態下，滑鼠游標正懸停在一個有效的目標節點上。

狀態轉換邏輯：

這個狀態機的邏輯主要在 EditorScene 的滑鼠事件處理函式中實現。

| 目前狀態 | 觸發事件 | 條件 | 執行動作 | 下一狀態 | 
|---|---|---|---|---|
| `IDLE` | `mousePressEvent` | 點擊發生在 `TaskNode` 上 | 1\. 儲存源節點。 2. 建立預覽線物件。 3. 記錄起始點位置。 | `START_CONNECTION` | 
| `START_CONNECTION` | `mouseMoveEvent` | 滑鼠移動距離超過一個微小閾值 | 1\. 顯示預覽線。 2. 更新預覽線終點。 | `DRAGGING_EDGE` | 
| `DRAGGING_EDGE` | `mouseMoveEvent` | 滑鼠游標進入一個有效的目標節點 | 1\. 高亮目標節點。 2. 更新預覽線終點。 | `VALID_TARGET_HOVER` | 
| `DRAGGING_EDGE` | `mouseMoveEvent` | 滑鼠游標在空白區域移動 | 1\. 更新預覽線終點。 | `DRAGGING_EDGE` | 
| `VALID_TARGET_HOVER` | `mouseMoveEvent` | 滑鼠游標離開目標節點，進入空白區域 | 1\. 取消目標節點高亮。 2. 更新預覽線終點。 | `DRAGGING_EDGE` | 
| `VALID_TARGET_HOVER` | `mouseReleaseEvent` | \- | 1\. 儲存目標節點。 2. 發射 `edge_created` 信號。 3. 移除預覽線。 4. 取消目標節點高亮。 | `IDLE` | 
| `DRAGGING_EDGE` | `mouseReleaseEvent` | \- | 1\. 移除預覽線。 | `IDLE` | 
| `START_CONNECTION` | `mouseReleaseEvent` | \- | 1\. 移除預覽線。 | `IDLE` | 

### **2\.2 視覺回饋的實作**

提供即時的視覺回饋是提升使用者體驗的關鍵。

#### **2\.2.1 預覽線（Rubber Band Line）的實作**

在 `DRAGGING_EDGE` 狀態下，跟隨滑鼠移動的預覽線是必不可少的。對於此功能，最高效的實作方式是 **建立一個臨時的 `QGraphicsLineItem` 並在 `mouseMoveEvent` 中不斷更新它**。這種方法遠優於在每次滑鼠移動時都重新建立和銷毀圖形物件，因為後者會頻繁地觸發場景索引的更新，導致效能下降。

實作步驟如下：

1. 在 `EditorScene` 的 `mousePressEvent` 中（當轉換到 `START_CONNECTION` 狀態時），建立一個 `QGraphicsLineItem` 實例（例如 `self.preview_edge`），並將其加入場景。可以為它設定一個虛線畫筆（`Qt.DashLine`）以區別於正式的邊。

2. 在 `mouseMoveEvent` 中，只需更新該線條的終點即可：`self.preview_edge.setLine(start_pos, event.scenePos())`。

3. 在 `mouseReleaseEvent` 中，無論連線是否成功建立，都從場景中移除這個預覽線物件（`self.scene().removeItem(self.preview_edge)`）並將其參考設為 `None`。

#### **2\.2.2 目標高亮的實作**

當預覽線的末端進入一個有效的目標節點時，該節點應高亮顯示。這裡存在一個重要的框架限制：當一個拖曳操作（如拖動節點或我們的預覽線）正在進行時，其他 `QGraphicsItem` 的標準懸停事件（`hoverEnterEvent`, `hoverLeaveEvent`）預設是不會被觸發的。

因此，解決方案必須在場景層級手動實作：

- **在 `EditorScene` 的 `mouseMoveEvent` 中處理高亮**：這是唯一可靠的方法。在 `mouseMoveEvent` 中，我們需要：

   1. 維護一個 `self.last_hovered_target` 變數來記錄上一個被高亮的節點。

   2. 使用 `self.itemAt(event.scenePos(), QTransform())` 獲取當前游標下的物件。

   3. 檢查該物件是否是一個有效的 `TaskNode`，並且不是源節點。

   4. 將當前偵測到的物件與 `self.last_hovered_target` 進行比較。

      - 如果兩者不同，則對舊的目標（如果存在）呼叫 `set_highlight(False)`，並對新的目標（如果有效）呼叫 `set_highlight(True)`。

      - 更新 `self.last_hovered_target` 為當前物件。

      - 根據是否懸停在有效目標上，更新場景的狀態為 `VALID_TARGET_HOVER` 或 `DRAGGING_EDGE`。

這個邏輯在 `TaskNode` 類別中需要一個 `set_highlight(self, highlighted: bool)` 方法來配合，該方法會設定一個內部旗標並呼叫 `self.update()` 來觸發重繪。`paint` 方法則會根據這個旗標繪製出高亮效果（如前一節所示）。

**Python**

```python
# 在 EditorScene 類別中
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsLineItem
from PyQt5.QtCore import Qt, QPointF, pyqtSignal
from PyQt5.QtGui import QPen, QColor

class EditorScene(QGraphicsScene):
    # 定義信號，用於與 Controller 通訊
    edge_created = pyqtSignal(str, str)
    node_moved = pyqtSignal(str, QPointF)

    # 定義狀態
    MODE_IDLE = 0
    MODE_DRAGGING_EDGE = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mode = self.MODE_IDLE
        self.preview_edge = None
        self.source_node = None
        self.last_hovered_target = None

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        item = self.itemAt(event.scenePos(), self.views().transform())
        if event.button() == Qt.LeftButton and isinstance(item, TaskNode):
            self.mode = self.MODE_DRAGGING_EDGE
            self.source_node = item
            self.preview_edge = QGraphicsLineItem()
            pen = QPen(Qt.black, 2, Qt.DashLine)
            self.preview_edge.setPen(pen)
            self.addItem(self.preview_edge)
            
            start_pos = self.source_node.pos() + self.source_node.boundingRect().center()
            self.preview_edge.setLine(start_pos.x(), start_pos.y(), 
                                      event.scenePos().x(), event.scenePos().y())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self.mode == self.MODE_DRAGGING_EDGE:
            # 更新預覽線
            line = self.preview_edge.line()
            line.setP2(event.scenePos())
            self.preview_edge.setLine(line)

            # 手動處理目標高亮
            target_item = self.itemAt(event.scenePos(), self.views().transform())
            
            # 清除上一個高亮的目標
            if self.last_hovered_target and self.last_hovered_target is not target_item:
                self.last_hovered_target.set_highlight(False)
                self.last_hovered_target = None

            # 如果懸停在一個有效的目標上
            if isinstance(target_item, TaskNode) and target_item is not self.source_node:
                target_item.set_highlight(True)
                self.last_hovered_target = target_item
            
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if self.mode == self.MODE_DRAGGING_EDGE:
            # 檢查是否在一個有效的目標上釋放
            target_item = self.itemAt(event.scenePos(), self.views().transform())
            if isinstance(target_item, TaskNode) and target_item is not self.source_node:
                # 成功建立連線，發射信號
                self.edge_created.emit(self.source_node.node_id, target_item.node_id)
            
            # 清理
            if self.last_hovered_target:
                self.last_hovered_target.set_highlight(False)
                self.last_hovered_target = None

            if self.preview_edge:
                self.removeItem(self.preview_edge)
                self.preview_edge = None
            
            self.mode = self.MODE_IDLE
            self.source_node = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)

```

## **第三部分：MVC 架構下的資料同步**

一個健壯的編輯器必須確保視覺層（View）的變更能夠可靠地更新資料層（Model），反之亦然。採用 MVC 或其變體（如 Qt 的 Model/View）是實現此目標的標準架構模式 。

### **3\.1 在圖形應用中應用 MVC 原則**

在我們的依賴關係編輯器中，各元件的角色可以明確劃分：

- **Model (模型)**：一個純 Python 物件，例如一個封裝了 `networkx.DiGraph` 的類別。它負責儲存節點和邊的依賴關係資料，以及相關的屬性。模型不應包含任何與 Qt 或圖形介面相關的程式碼 。

- **View (視圖)**：由 `QGraphicsView`、`EditorScene` 以及所有的 `TaskNode` 和 `DependencyEdge` 物件組成。其職責是渲染模型資料，並捕捉原始的使用者輸入事件（如滑鼠點擊和移動）。

- **Controller (控制器)**：一個中央應用程式物件（例如主視窗 `QMainWindow`）。它負責實例化模型和視圖，並透過信號與槽機制將它們連接起來。控制器包含了將使用者在視圖中的操作轉換為對模型進行修改的業務邏輯。

這種關注點分離的架構，使得系統的各個部分可以獨立開發和測試，極大地提高了程式碼的可維護性 。

### **3\.2 視圖到模型 (View-to-Model) 的資料流**

當使用者在視圖中完成一個操作（例如成功建立一條邊）時，這個變更需要被通知給控制器，再由控制器去更新模型。

**通訊管道**：如前所述，`QGraphicsItem` 本身不適合發射信號。因此，最佳實踐是在 `EditorScene` 子類別中定義自訂信號 。

`EditorScene` 在這裡扮演了視圖與控制器之間的中介角色。

**實作流程** ：

1. 在 `EditorScene` 類別中，定義描述使用者操作的信號，例如 `edge_created = pyqtSignal(str, str)`，其中參數為源節點和目標節點的 ID。

2. 在 `EditorScene` 的 `mouseReleaseEvent` 方法中，當確認一條邊被成功建立時，發射此信號：`self.edge_created.emit(source_`[`node.id`](node.id)`, target_`[`node.id`](node.id)`)`。

3. 在控制器中，將場景的信號連接到控制器的槽函式（處理函式）：`self.scene.edge_created.connect(self.handle_edge_creation)`。

4. 控制器的槽函式 `handle_edge_creation(source_id, dest_id)` 接收到信號後，呼叫模型的方法來更新資料：`self.model.add_dependency(source_id, dest_id)`。

### **3\.3 模型到視圖 (Model-to-View) 的資料流**

當模型因為程式邏輯（例如從檔案載入、或由另一個 UI 元件修改）而發生變更時，`EditorScene` 必須高效地反映這些變更。

**挑戰**：天真的做法是每次模型變更時都清空並重新繪製整個場景。對於大型圖形來說，這會導致嚴重的效能問題和視覺閃爍。

**高效的解決方案：雙向資料綁定**

1. **讓 Model 可發射信號**：將模型類別設計為繼承自 `QObject`，並為其定義信號，例如 `node_added = pyqtSignal(str, dict)`、`edge_removed = pyqtSignal(str, str)`、`model_reloaded = pyqtSignal()`。

2. **建立 ID 與 Item 的對應關係**：`EditorScene` 內部應維護一個字典（例如 `self.item_map`），用於儲存從模型節點 ID 到對應的 `TaskNode` 物件的映射。這個技巧對於實現高效的目標式更新至關重要，也是 Qt 官方 NetworkX 範例中採用的方法 。

3. **連接 Model 與 Scene**：在控制器中，將模型的信號連接到 `EditorScene` 中對應的槽函式。例如：`self.model.node_added.connect(self.scene.add_node_item)`。

4. **實作目標式更新的槽函式**：

   - `add_node_item(self, node_id, node_data)`：這個槽函式會建立一個新的 `TaskNode`，將其加入場景，並將 `(node_id, node_instance)` 的對應關係存入 `self.item_map`。

   - `remove_node_item(self, node_id)`：這個槽函式會從 `self.item_map` 中查找對應的 `TaskNode` 物件，將其從場景中移除（`self.removeItem()`），然後從字典中刪除。

   - `model_reloaded(self)`：這個槽函式會清空整個場景和 `item_map`，然後遍歷新模型中的所有節點和邊，重新建立整個視圖。

這種基於信號與槽的目標式更新機制，避免了不必要的全場景重繪，確保了即使在處理大規模資料時，UI 也能保持流暢和響應迅速 。

| 資料流方向 | 來源元件 | 信號 | 目標元件 | 槽函式 | 目的與動作 | 
|---|---|---|---|---|---|
| **View → Model** | `EditorScene` | `edge_created(str, str)` | `Controller` | `on_edge_created(src_id, dst_id)` | 使用者在圖形介面成功建立連線。控制器呼叫 `model.add_edge(src_id, dst_id)`。 | 
| **View → Model** | `EditorScene` | `node_moved(str, QPointF)` | `Controller` | `on_node_moved(node_id, pos)` | 使用者拖曳節點到新位置。控制器呼叫 `model.set_node_position(node_id, pos)`。 | 
| **View → Model** | `EditorScene` | `items_deleted(list)` | `Controller` | `on_items_deleted(item_ids)` | 使用者刪除了一個或多個節點/邊。控制器呼叫 `model.remove_items(item_ids)`。 | 
| **Model → View** | `Model` | `node_added(str, dict)` | `EditorScene` | `add_node_item(node_id, data)` | 程式邏輯向模型新增節點。場景建立一個新的 `TaskNode` 並加入 `item_map`。 | 
| **Model → View** | `Model` | `edge_added(str, str)` | `EditorScene` | `add_edge_item(src_id, dst_id)` | 程式邏輯向模型新增邊。場景從 `item_map` 查找源/目標節點並建立 `DependencyEdge`。 | 
| **Model → View** | `Model` | `node_removed(str)` | `EditorScene` | `remove_node_item(node_id)` | 程式邏輯從模型移除節點。場景從 `item_map` 查找並移除對應的 `TaskNode`。 | 
| **Model → View** | `Model` | `model_reloaded()` | `EditorScene` | `rebuild_scene()` | 模型被完全替換（如載入新檔案）。場景清空所有項目並根據新模型完全重建。 | 



## **結論：最佳實踐與未來展望**



本指南詳細闡述了使用 PyQt5 的 `QGraphicsScene` 框架來建構一個功能豐富、互動流暢的依賴關係編輯器的核心技術。透過遵循本報告中提出的架構和實作模式，開發團隊可以建立一個穩固且可擴展的基礎。

**關鍵實作模式總結**：

- **事件修飾與委派**：對於選取操作，應修改事件的修飾鍵狀態後，再將其傳遞給基底類別處理，而非完全重新實作。

- **非破壞性繪圖**：利用 `QStyleOptionGraphicsItem` 的副本來控制選取狀態，以自訂視覺回饋，同時避免重寫整個 `paint` 邏輯。

- **`itemChange` 機制**：這是處理節點移動後，同步更新相連邊緣位置的標準且最高效的方法。

- **場景級手動高亮**：在拖曳操作期間，必須在 `QGraphicsScene` 的 `mouseMoveEvent` 中手動管理目標物件的懸停高亮，因為 `QGraphicsItem` 的標準懸停事件會被抑制。

- **場景中心化的信號/槽架構**：透過在場景中定義信號，並在模型中也實現信號機制，可以建立一個清晰、解耦且高效的雙向資料同步流程。

**效能建議**：

- 對於包含大量複雜圖元的節點，考慮設定 `QGraphicsItem.CacheMode` 為 `ItemCoordinateCache` 或 `DeviceCoordinateCache`，以最佳化重繪效能 。

- 在處理大型場景時，務必為 `QGraphicsScene` 設定一個明確的 `sceneRect`。這可以避免場景為了計算所有物件的邊界（`itemsBoundingRect()`）而進行的耗時操作 。

未來擴展方向：

基於本指南建立的穩固架構，可以輕鬆地進行後續功能擴展：

- **復原/重做 (Undo/Redo) 框架**：許多成熟的節點編輯器都具備此功能。可以透過實作命令模式（Command Pattern），將每次對模型的修改（新增/刪除節點、移動節點等）封裝成命令物件，並由一個命令堆疊來管理，從而實現復原與重做 。

- **進階樣式與節點內容**：可以擴展 `TaskNode`，使其內部可以容納更複雜的 `QWidget`（透過 `QGraphicsProxyWidget`），或實現更豐富的樣式系統。

- **整合圖形佈局演算法**：利用 NetworkX 內建的佈局演算法（如 spring layout, circular layout），可以為使用者提供自動整理圖形的功能。控制器可以呼叫這些演算法計算節點位置，然後透過模型到視圖的同步機制來更新畫面 。