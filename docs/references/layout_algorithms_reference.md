# **從理論到應用：Python 中階層式與正交圖形視覺化權威指南**

## **導論**

在數據科學、軟體工程和系統分析領域，將複雜的網路、流程和依賴關係轉化為清晰、可理解的視覺化敘事是一項至關重要的能力。一個未經組織的圖形，節點雜亂無章，邊線縱橫交錯，往往會掩蓋而非揭示資訊。相比之下，一個經過精心佈局的圖表，能夠立即突顯其內在結構，引導觀者洞察數據背後的模式。自動化佈局演算法正是實現這種轉化的核心技術。

然而，從理解這些強大演算法的理論原理，到在一個具體的應用程式（例如使用 Python 和 PyQt5 框架開發的客製化工具）中成功實現它們，這條路徑充滿了挑戰。開發者不僅需要掌握演算法本身，還必須應對一系列在理論文獻中鮮少提及的實際工程問題。

本報告旨在彌合理論與實踐之間的鴻溝，為開發者提供一份關於兩種基本圖形佈局範式——階層式佈局（Hierarchical Layout）與正交邊線路由（Orthogonal Edge Routing）——的權威指南。我們將深入解構驅動這些技術的核心演算法，即杉山方法（Sugiyama Method）和 A\* 搜尋演算法，並提供一份詳盡的、步驟化的實作藍圖。這份藍圖將指導您如何整合 Python 生態系中的強大工具，如 `NetworkX`、`Graphviz` 和 `PyQt5`，來建構一個功能完善的圖形視覺化應用。本報告將特別關注那些關鍵但常被忽略的技術細節，例如坐標系轉換的複雜性以及為實現美學目標而客製化成本函數的必要性，從而賦予您將抽象理論轉化為高效能、高可讀性視覺化應用的能力。

---

## **第一部分：流程的架構 - 深入剖析階層式佈局**

階層式佈局是圖形視覺化領域中最重要和最廣泛使用的技術之一。它的核心價值在於將具有內在方向性的數據，轉化為一種符合人類直覺的、有序的視覺呈現。本部分將深入探討其基本原則、核心演算法框架，並提供一個基於 Python 的完整實作方案。

### **1\.1 階層式視覺化的基礎原則**

階層式佈局並非適用於所有類型的圖形。它的設計初衷是為有向圖（Directed Graphs）服務，特別是那些能夠表達流程、依賴、層級或因果關係的圖 。其主要目標是將圖形中的節點排列在不同的層級上，使得絕大多數的邊線都朝向一個統一的方向（例如，從上到下或從左到右），從而清晰地揭示數據中的流動性 。常見的應用場景包括工作流程圖、組織結構圖、UML 活動圖和函數呼叫圖 。

一個「好」的階層式佈局並非主觀判斷，而是基於一系列公認的美學準則。這些準則構成了演算法的優化目標，旨在最大化圖形的可讀性和清晰度 。

- **最小化邊線交叉 (Minimizing Edge Crossings)**：這是最重要的美學準則。邊線的交叉會嚴重干擾使用者對圖形關係的理解，是造成認知摩擦和視覺混亂的主要原因。因此，幾乎所有階層式佈局演算法的核心都在於尋找一種節點排列方式，以最大限度地減少邊線交叉的數量 。

- **清晰的方向流 (Clear Directional Flow)**：佈局應當直觀地體現出圖形的整體流向。演算法會盡力使絕大多數邊線都指向同一個方向，例如從上層指向下層，這有助於使用者一眼看懂整個流程的順序和依賴關係 。

- **緊湊性與平衡性 (Compactness and Balance)**：在滿足前兩個主要目標的前提下，演算法會試圖使佈局盡可能緊湊，以節省顯示空間。同時，它會力求節點在各層級中分佈均勻，避免某些區域過於擁擠而其他區域過於稀疏，並保持相連節點間的邊長相對一致，以創造視覺上的和諧感 。

### **1\.2 杉山方法解構：一個四階段框架**

杉山方法（Sugiyama Framework）是產生高品質階層式佈局的經典演算法框架，被廣泛應用於如 yEd/yFiles 這樣的專業圖表工具中。它並非單一演算法，而是一個由四個連續階段組成的處理流程，每個階段專注於解決一個特定的子問題。這種模組化的設計使得複雜的佈局問題變得可管理 。

**第一階段：移除循環 (Cycle Removal)**

- **目標**：將任意有向圖轉換為一個有向無環圖（Directed Acyclic Graph, DAG）。

- **必要性**：在一個真正的階層結構中，不應存在循環（例如 A→B→C→A）。「層級」或「排名」的概念在存在循環的圖中是沒有意義的，因為節點之間沒有明確的先後順序。因此，移除循環是進行後續分層處理的絕對前提。

- **機制**：演算法首先會偵測圖中是否存在循環。一旦發現，它會採用策略（如深度優先搜尋）找到構成循環的邊，並暫時「反轉」其中一條或多條邊的方向，從而打破循環。這些被反轉的邊會被標記，以便在最終繪圖時仍能以正確的方向顯示 。

**第二階段：分層 (Layer Assignment / Ranking)**

- **目標**：為 DAG 中的每一個節點分配一個離散的層級（或稱為「秩」，Rank）。

- **機制**：此階段的目標是將節點放置到不同的水平或垂直層上，使得所有邊都從較低層級的節點指向較高層級的節點（或反之）。有多種演算法可以實現分層，其中一種常見的方法是「最長路徑法」：首先找到圖中所有的源節點（沒有入邊的節點），將它們分配到第 0 層；然後，對於任何其他節點 `v`，其層級被定義為從任意源節點到 `v` 的最長路徑的長度 。

- **虛擬節點的關鍵作用**：當一條邊連接的兩個節點不處於相鄰層級時（例如，從第 1 層直接連接到第 4 層），這條邊被稱為「長邊」。為了簡化後續處理，演算法會在這條長邊上插入一系列「虛擬節點」（dummy nodes）。例如，對於從 L1 到 L4 的邊，會在 L2 和 L3 分別插入一個虛擬節點，將原來的長邊分解為三段連接相鄰層的短邊。這一步驟不僅僅是為了視覺上的方便，它在演算法上具有根本性的重要意義。後續的交叉減少和座標分配階段，其演算法複雜度被大大降低，因為它們可以建立在一個簡化的假設之上：圖中所有邊都只連接相鄰的層級。虛擬節點是確保這個假設成立的數據結構轉換，是整個框架能夠高效運作的基石。

**第三階段：減少交叉 (Crossing Reduction / Ordering)**

- **目標**：在保持分層不變的前提下，調整每一層內部節點的排列順序，以最小化相鄰層之間邊線的交叉數量。

- **NP-Hard 挑戰**：找到一個能使交叉數量絕對最小化的節點排序，是一個著名的 NP-Hard 問題 。這意味著對於中等規模以上的圖，透過暴力搜尋找到最優解在計算上是不可行的。

- **啟發式演算法的務實選擇**：正因為最優解難以求得，所有實用系統都採用了高效的啟發式演算法（Heuristics）來尋找一個「足夠好」的近似解。yEd 等工具中常用的方法包括重心法（Barycenter）和中位數法（Median）。這些方法通常是逐層迭代處理的：固定一層的節點順序，然後根據這一層的節點位置來調整下一層的節點順序。例如，重心法會嘗試將一個節點放置在其所有父節點（或子節點）的水平位置的「重心」或平均位置的正對面。透過多次迭代（例如，從上到下再從下到上反覆調整），可以快速收斂到一個交叉數量很少的穩定狀態。對於開發者而言，這意味著最明智的實作策略是利用現有的、經過數十年優化的佈局引擎（如 Graphviz），而不是嘗試從頭實現這個極其複雜的階段。

**第四階段：座標分配 (Coordinate Assignment / Positioning)**

- **目標**：為所有節點（包括真實節點和虛擬節點）分配最終的 X 和 Y 座標。

- **機制**：在此階段，節點的層級和順序都已確定。Y 座標通常直接由節點所在的層級決定。X 座標的分配則更為複雜，其目標是：

   1. 保持第三階段確定的節點順序。

   2. 盡可能拉直邊線，減少彎曲。

   3. 使父節點在視覺上居中於其子節點的上方。

   4. 確保節點之間有足夠的間距，避免重疊。

   5. 使整個佈局盡可能緊湊。

- **最終繪製**：在分配完所有座標後，虛擬節點的使命便已完成。它們的位置被用來確定原始長邊的路徑點。最後，這些虛擬節點被移除，長邊被繪製成穿過這些計算點的樣式，例如平滑的樣條曲線（spline）或由直線段構成的折線（polyline）。

The following table:

| 階段 (Phase) | 目標 (Goal) | 關鍵操作 (Key Operations) | 結果 (Result) | 
|---|---|---|---|
| **1\. 移除循環** | 將圖轉換為有向無環圖 (DAG) | 偵測循環，並暫時反轉某些邊的方向以打破循環 。 | 一個無循環的圖，為分層奠定基礎。 | 
| **2\. 分層** | 為每個節點分配一個離散的層級（秩） | 根據邊的方向將節點分配到不同層。為跨越多個層的長邊插入虛擬節點。 | 一個「適當」分層的圖，其中所有邊都連接相鄰層。 | 
| **3\. 減少交叉** | 最小化相鄰層之間的邊線交叉數量 | 在每個層級內對節點重新排序。通常使用啟發式演算法（如重心法）來找到近似最優解 。 | 一個節點順序確定的圖，具有良好的可讀性。 | 
| **4\. 座標分配** | 為每個節點和邊線路徑分配最終的幾何座標 | 根據層級和順序計算 X/Y 座標，以拉直邊線、對齊節點並確保佈局緊湊。 | 一個可以被渲染的、具有具體位置資訊的圖。 | 

### **1\.3 Python 與 PyQt5 的階層式佈局實作**

從頭開始完整實現杉山方法的四個階段是一項艱鉅的任務，特別是計算密集型的第三階段。一個更為明智和高效的工程實踐是利用現有的、高度優化的專業工具來完成佈局計算，然後將結果整合到我們的應用程式中進行渲染。

**架構策略**

我們將採用一個模組化的三層架構：

1. **圖形數據模型 (Graph Data Model)**：使用 `networkx` 函式庫。它是 Python 中處理圖形數據結構的事實標準，提供了豐富的 API 來創建、操作和分析圖形 。

2. **佈局引擎 (Layout Engine)**：使用 `Graphviz`。這是一個開源的圖形視覺化軟體包，其 `dot` 佈局引擎正是杉山方法的一個強大實現，經過了數十年的學術研究和工程優化 。我們將透過

   `pygraphviz` 這個 Python 綁定來呼叫它。

3. **渲染畫布 (Rendering Canvas)**：使用 PyQt5 的原生 `QGraphicsScene` / `QGraphicsView` 框架。與嵌入 Matplotlib 畫布相比，`QGraphicsScene` 提供了更優越的性能、更豐富的交互能力以及與 Qt 生態系統的無縫整合 。

**步驟 1：環境設定**

首先，確保安裝所有必要的套件。`Graphviz` 本身是一個需要單獨安裝的系統級工具，而 `pygraphviz` 是其 Python 介面。

**Bash**

```python
# 安裝 Python 函式庫
pip install pyqt5 networkx pygraphviz

# 在 Ubuntu/Debian 上安裝 Graphviz
sudo apt-get install graphviz graphviz-dev

# 在 macOS 上使用 Homebrew 安裝
brew install graphviz

# 在 Windows 上，建議從官方網站下載安裝程式
# https://graphviz.org/download/
# 並確保將 Graphviz 的 bin 目錄添加到系統的 PATH 環境變數中。

```

注意：`pygraphviz` 在 Windows 上的安裝有時會比較複雜，可能需要手動設定函式庫和標頭檔的路徑 。

**步驟 2：在 NetworkX 中建立圖形**

使用 `networkx` 創建一個有向圖 (`DiGraph`) 作為我們的數據源。

**Python**

```python
import networkx as nx

# 建立一個有向圖
G = nx.DiGraph()

# 添加節點和邊
G.add_edges_from()

# 為了演示循環移除，可以添加一條反向邊
# G.add_edge('D', 'A')

```

**步驟 3：使用 PyGraphviz 計算節點位置**

接下來，我們將 `networkx` 圖形轉換為 `pygraphviz` 圖形，並呼叫 `dot` 引擎來計算佈局。

**Python**

```python
import networkx as nx
from networkx.drawing.nx_agraph import to_agraph

#... (接續步驟 2 的 G)

# 將 networkx 圖轉換為 pygraphviz AGraph
A = to_agraph(G)

# 設定佈局屬性（可選），例如從左到右佈局
A.graph_attr['rankdir'] = 'LR'

# 執行佈局計算，使用 'dot' 引擎
A.layout(prog='dot')

# 提取計算出的節點位置
# pos 是一個字典，格式為 {node_id: 'x,y'}
pos = {}
for n in A.nodes():
    pos[n.name] = tuple(map(float, n.attr['pos'].split(',')))

# pos 現在看起來像這樣（範例值）:
# {'A': (37.0, 79.0), 'B': (114.0, 125.0),...}

```

`A.layout(prog='dot')` 是整個佈局過程的核心。它在幕後執行了完整的杉山方法，並將計算出的 `(x, y)` 坐標作為 `pos` 屬性附加到每個節點上 。

**步驟 4：關鍵挑戰 - 坐標系轉換**

直接將 `pygraphviz` 輸出的坐標用於 `QGraphicsScene` 會導致圖形顯示異常。這是因為兩個系統在三個關鍵方面存在差異：**單位**、**Y 軸方向**和**原點**。解決這個轉換問題是成功實現的關鍵。

1. **單位 (Units)**：`Graphviz` 的 `pos` 屬性單位是**點 (points)**，其中 1 英寸 = 72 點。而

   `QGraphicsScene` 使用的是**像素 (pixels)**。如果直接使用，圖形會非常小。我們需要一個縮放因子。

2. **Y 軸方向 (Y-Axis Direction)**：`Graphviz` 的 `dot` 引擎使用傳統的數學坐標系，原點在**左下角**，Y 值**向上**增加。而

   `QGraphicsScene` 遵循電腦圖學的慣例，原點在**左上角**，Y 值**向下**增加 。這意味著我們必須對 Y 坐標進行翻轉。

3. **原點 (Origin)**：`Graphviz` 輸出的坐標是相對於其自身計算出的圖形邊界框（bounding box）的。我們需要將這些坐標平移，以確保圖形在我們的 `QGraphicsView` 視口中正確顯示。

以下是實現坐標轉換的完整邏輯：

**Python**

```python
def transform_coords(pos, view_width, view_height, padding=20):
    """將 Graphviz 點坐標轉換為 PyQt 像素坐標"""
    if not pos:
        return {}

    # 1. 找到 Graphviz 佈局的邊界框（以點為單位）
    x_coords = [p for p in pos.values()]
    y_coords = [p for p in pos.values()]
    min_x, max_x = min(x_coords), max(x_coords)
    min_y, max_y = min(y_coords), max(y_coords)
    
    graph_width = max_x - min_x
    graph_height = max_y - min_y

    # 處理圖形為空或只有一個節點的情況
    if graph_width == 0 or graph_height == 0:
        return {k: (view_width / 2, view_height / 2) for k in pos}

    # 2. 計算縮放因子，以適應視圖大小並保持長寬比
    scale_x = (view_width - 2 * padding) / graph_width
    scale_y = (view_height - 2 * padding) / graph_height
    scale = min(scale_x, scale_y)

    # 3. 轉換每個節點的坐標
    qt_pos = {}
    for node, (x, y) in pos.items():
        # 平移到原點 (0,0)
        x_translated = x - min_x
        y_translated = y - min_y

        # 縮放
        x_scaled = x_translated * scale
        y_scaled = y_translated * scale

        # 翻轉 Y 軸並應用邊距
        qt_x = x_scaled + padding
        qt_y = (graph_height * scale) - y_scaled + padding
        
        qt_pos[node] = (qt_x, qt_y)
        
    return qt_pos

```

**步驟 5：在 QGraphicsScene 中渲染圖形**

最後，我們建立一個 PyQt5 應用程式，使用轉換後的坐標在 `QGraphicsScene` 上繪製節點和邊。

**Python**

```python
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QGraphicsView, 
                             QGraphicsScene, QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsTextItem)
from PyQt5.QtGui import QPen, QBrush, QColor, QFont
from PyQt5.QtCore import Qt, QPointF

class GraphViewer(QMainWindow):
    def __init__(self, graph, positions):
        super().__init__()
        self.setWindowTitle("Hierarchical Layout Viewer")
        self.setGeometry(100, 100, 800, 600)

        self.graph = graph
        self.positions = positions

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene, self)
        self.setCentralWidget(self.view)
        
        self.draw_graph()

    def draw_graph(self):
        node_items = {}
        node_radius = 20
        
        # 定義畫筆和畫刷
        node_pen = QPen(QColor("black"), 2)
        node_brush = QBrush(QColor("#ADD8E6")) # Light Blue
        edge_pen = QPen(QColor("gray"), 1.5)

        # 1. 繪製節點和標籤
        for node_id, pos in self.positions.items():
            x, y = pos
            
            # 繪製節點（橢圓）
            ellipse = QGraphicsEllipseItem(x - node_radius, y - node_radius, 
                                           node_radius * 2, node_radius * 2)
            ellipse.setPen(node_pen)
            ellipse.setBrush(node_brush)
            self.scene.addItem(ellipse)
            node_items[node_id] = ellipse

            # 繪製節點標籤
            text = QGraphicsTextItem(node_id)
            text.setDefaultTextColor(QColor("black"))
            text.setFont(QFont("Arial", 10))
            # 將標籤置於橢圓中心
            text_rect = text.boundingRect()
            text.setPos(x - text_rect.width() / 2, y - text_rect.height() / 2)
            self.scene.addItem(text)

        # 2. 繪製邊
        for u, v in self.graph.edges():
            pos_u = self.positions[u]
            pos_v = self.positions[v]
            
            line = QGraphicsLineItem(pos_u, pos_u, pos_v, pos_v)
            line.setPen(edge_pen)
            # 將邊置於節點下方
            line.setZValue(-1)
            self.scene.addItem(line)

if __name__ == '__main__':
    #... (接續步驟 2 和 3 的代碼來產生 G 和 pos)
    # G =...
    # A = to_agraph(G)...
    # pos =...

    app = QApplication(sys.argv)
    
    # 假設視圖大小為 800x600
    view_width, view_height = 800, 600
    qt_positions = transform_coords(pos, view_width, view_height)
    
    viewer = GraphViewer(G, qt_positions)
    viewer.show()
    sys.exit(app.exec_())

```

這個完整的流程展示了如何將一個複雜的理論框架（杉山方法）透過結合多個專業工具，轉化為一個功能性的桌面應用程式。關鍵在於理解每個工具的職責，並解決它們之間介面的不匹配問題，特別是坐標系的轉換。

---

## **第二部分：連接的幾何學 - 精通正交邊線路由**

當圖形佈局完成後，使用者可能需要手動調整某些節點的位置以滿足特定需求。然而，這種手動調整往往會導致邊線變得混亂、重疊，破壞了圖形的整潔性。正交邊線路由（Orthogonal Edge Routing）正是為了解決這個問題而生的一種強大技術。它能在保持節點位置不變的情況下，重新規劃邊線的路徑，使其僅由水平和垂直線段構成，從而恢復圖形的清晰度和專業外觀。

### **2\.1 高清晰度邊線路由的原則**

首先，必須釐清一個關鍵區別：**佈局 (Layout)** 與 **路由 (Routing)**。一個完整的佈局演算法會重新計算並設定**所有節點和邊線**的位置 。而一個邊線路由演算法則是在**節點位置固定**的前提下，僅重新繪製連接它們的線路 。

正交路由的目標是產生在技術圖表中廣泛接受的美學標準，這些標準旨在最大化路徑的可讀性：

- **正交性 (Orthogonality)**：所有邊線都必須由水平和垂直線段組成，所有轉角均為 90 度。這種風格為圖表帶來一種結構化的、工程上的嚴謹感 。

- **障礙物規避 (Obstacle Avoidance)**：這是路由演算法的核心功能。邊線路徑必須繞開所有節點的邊界框，絕不能穿過任何節點，以避免視覺上的混淆 。

- **最小化彎折 (Minimizing Bends)**：一條邊上的轉彎次數越少，視覺上就越簡潔，使用者追蹤路徑的認知負擔就越低。因此，在所有可能的正交路徑中，演算法會優先選擇轉彎最少的路徑 。

- **最小化交叉 (Minimizing Crossings)**：雖然在節點固定的情況下完全消除交叉通常是不可能的，但一個好的路由演算法會盡力尋找能減少邊線之間交叉點的路徑。

### **2\.2 A\* 演算法作為路徑尋找引擎**

為了找到滿足上述所有條件的最佳路徑，邊線路由演算法通常將問題建模為一個在網格上的路徑尋找問題，而 A\*（A-Star）搜尋演算法是解決此類問題最流行和最高效的工具之一 。

**迷宮類比**

我們可以將路由過程想像成在一個迷宮中尋找出路。

- **迷宮地圖**：整個 `QGraphicsScene` 畫布被視為一個精細的網格。

- **牆壁/障礙物**：畫布上所有已存在的節點都被視為不可穿越的「牆壁」。為了留出視覺間隙，通常還會在節點周圍設定一個不可見的「邊距」區域，同樣視為障礙物 。

- **起點和終點**：路由的起點是源節點的某個連接埠，終點是目標節點的連接埠。

- **任務**：找到一條從起點到終點的路徑，該路徑只能水平或垂直移動，且不能穿過任何「牆壁」。

**A\* 演算法解構**

A\* 演算法透過一個巧妙的評估函數來指導其搜尋方向，從而高效地找到最佳路徑。對於搜尋網格中的每一個點 `n`，它會計算一個代價函數 `f(n)` ：

f(n)=g(n)+h(n)

- g(n)：**已付出代價 (Past Cost)**。這是從**起點**走到當前節點 `n` 的**實際路徑成本**。在最簡單的情況下，這就是路徑的長度。

- h(n)：**啟發式估計代價 (Heuristic Cost)**。這是一個「猜測值」，估計從當前節點 `n` 走到**終點**所需的**最小成本**。對於只能水平和垂直移動的網格，**曼哈頓距離**（Manhattan Distance）是一個完美的啟發式函數，因為它永遠不會高估實際距離，保證了 A\* 演算法的最優性 **1**。曼哈頓距離計算公式為：

   ∣xn​−xgoal​∣+∣yn​−ygoal​∣。

- f(n)：**總估計代價**。這是經過節點 `n` 的路徑的總體評估值。A\* 演算法在每一步都會優先探索 `open_set`（一個待探索節點的優先級佇列）中 `f(n)` 值最低的節點。

**實現美學的關鍵：轉彎代價 (Turn Penalty)**

標準的 A\* 演算法只關心路徑長度，但這不足以產生美觀的正交路徑。一條短路徑可能包含大量不必要的 zigzag 轉彎。為了生成更平滑、更簡潔的線條，我們必須在 A\* 的成本計算中引入「轉彎代價」。

然而，這帶來了一個核心的實作挑戰。一個「轉彎」是路徑的屬性，而不是單個點的屬性。要知道在移動到 `(x, y)` 時是否發生了轉彎，我們必須知道是從哪個方向到達前一個節點的。標準的 A\* 狀態表示 `(x, y)` 無法提供此資訊 。

為了解決這個問題，我們必須擴展 A\* 演算法中的「狀態」定義。我們不再是在一個簡單的位置網格上搜尋，而是在一個更複雜的狀態空間圖上搜尋，其中每個「節點」不僅包含位置，還包含到達該位置時的方向。

- **標準 A\* 狀態**：一個元組 `(x, y)`。

- **擴展後 A\* 狀態**：一個元組 `(x, y, arrival_direction)`，其中 `arrival_direction` 可以是 `(dx, dy)`，例如 `(1, 0)` 代表從左邊到達。

這種狀態擴展徹底改變了成本計算的方式。`g_score` 不再是簡單地映射 `position -> cost`，而是 `state -> cost`。這意味著同一個網格單元 `(x, y)` 可能會因為從不同方向到達而以不同的成本多次出現在 `open_set` 中。這種方法雖然增加了狀態空間的複雜性，但卻是準確建模轉彎代價的根本途徑。一些文獻中提出的為每個方向建立一個獨立圖層的方案，本質上也是這種狀態擴展思想的體現，但直接使用狀態元組在實作上更為直接和高效 。

The following table:

| 特性 (Feature) | 標準 A\* 演算法 (Standard A\*) | 帶轉彎代價的 A\* 演算法 (A\* with Turn Penalty) | 
|---|---|---|
| **狀態表示** | `(x, y)` | `(x, y, arrival_direction)` | 
| **`g_score` 字典鍵** | `g_score[(x, y)]` | `g_score[(x, y, direction)]` | 
| **成本計算** | `g_score[neighbor] = g_score[current] + move_cost` | `g_score[neighbor] = g_score[current] + move_cost + turn_penalty` | 
| **核心限制/優勢** | 無法建模依賴路徑的成本，如轉彎。 | 能夠準確地為路徑轉彎施加懲罰，從而引導演算法找到更平滑、更美觀的路徑。 | 

### **2\.3 從零開始在 PyQt5 中實作正交路由器**

雖然存在一些通用的路徑尋找函式庫 ，但它們通常是為遊戲開發等場景設計的，可能難以直接整合到

`QGraphicsScene` 的坐標系中，並且客製化成本函數（如轉彎代價）可能不夠靈活。從頭開始構建我們自己的 A\* 路由器，可以讓我們對路由邏輯擁有完全的控制權。

**步驟 1：網格表示**

首先，我們需要將 `QGraphicsScene` 的狀態抽象成一個 A\* 演算法可以理解的網格。

**Python**

```python
import numpy as np

def create_grid_from_scene(scene, node_items, grid_resolution=10):
    """從 QGraphicsScene 創建一個用於路徑尋找的網格"""
    scene_rect = scene.sceneRect()
    width = int(scene_rect.width() / grid_resolution)
    height = int(scene_rect.height() / grid_resolution)
    
    # 0 代表可通行，1 代表障礙物
    grid = np.zeros((height, width), dtype=int)
    
    # 將節點標記為障礙物
    for item in node_items:
        rect = item.sceneBoundingRect()
        # 在節點周圍增加一些填充，以避免邊線緊貼節點
        padded_rect = rect.adjusted(-grid_resolution, -grid_resolution, 
                                    grid_resolution, grid_resolution)

        x_start = int(padded_rect.left() / grid_resolution)
        y_start = int(padded_rect.top() / grid_resolution)
        x_end = int(padded_rect.right() / grid_resolution)
        y_end = int(padded_rect.bottom() / grid_resolution)

        # 確保索引在網格範圍內
        x_start = max(0, x_start)
        y_start = max(0, y_start)
        x_end = min(width, x_end)
        y_end = min(height, y_end)

        grid[y_start:y_end, x_start:x_end] = 1 # 標記為障礙物
        
    return grid

```

**步驟 2：A\* 核心邏輯與自訂成本函數**

接下來是 A\* 路由器的核心類別。這裡將實作帶有轉彎代價的擴展狀態 A\* 演算法。

**Python**

```python
import heapq

class OrthogonalRouter:
    def __init__(self, grid, turn_penalty=5):
        self.grid = grid
        self.height, self.width = grid.shape
        self.turn_penalty = turn_penalty

    def _heuristic(self, a, b):
        # 曼哈頓距離
        return abs(a - b) + abs(a - b)

    def find_path(self, start_pos, end_pos):
        # 狀態: (f_score, g_score, (x, y), parent_direction)
        # parent_direction 是 (dx, dy) 元組, (0,0) 代表起點
        open_set = [(self._heuristic(start_pos, end_pos), 0, start_pos, (0, 0))]
        
        # came_from 記錄路徑: {(x, y, dir): (px, py, p_dir)}
        came_from = {}
        
        # g_score 記錄成本: {(x, y, dir): cost}
        g_score = {}
        g_score[(start_pos, (0, 0))] = 0

        while open_set:
            _, current_g, current_pos, parent_dir = heapq.heappop(open_set)
            
            if current_pos == end_pos:
                return self._reconstruct_path(came_from, (current_pos, parent_dir))

            # 探索鄰居
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                neighbor_pos = (current_pos + dx, current_pos + dy)
                
                # 檢查邊界和障礙物
                nx, ny = neighbor_pos
                if not (0 <= nx < self.width and 0 <= ny < self.height and self.grid[ny][nx] == 0):
                    continue

                move_dir = (dx, dy)
                
                # 計算成本
                cost = 1 # 移動成本
                if parent_dir!= (0, 0) and move_dir!= parent_dir:
                    cost += self.turn_penalty # 施加轉彎懲罰
                
                new_g_score = current_g + cost
                
                neighbor_state = (neighbor_pos, move_dir)
                if neighbor_state not in g_score or new_g_score < g_score[neighbor_state]:
                    g_score[neighbor_state] = new_g_score
                    f_score = new_g_score + self._heuristic(neighbor_pos, end_pos)
                    heapq.heappush(open_set, (f_score, new_g_score, neighbor_pos, move_dir))
                    came_from[neighbor_state] = (current_pos, parent_dir)
        
        return None # 未找到路徑

    def _reconstruct_path(self, came_from, current_state):
        path = [current_state]
        while current_state in came_from:
            current_state = came_from[current_state]
            path.append(current_state)
        return path[::-1]

```

**步驟 3：路徑重建與渲染**

找到路徑後，它是一系列網格坐標。我們需要將其轉換回 `QGraphicsScene` 的像素坐標，並使用 `QPainterPath` 進行高效渲染。

**Python**

```python
from PyQt5.QtGui import QPainterPath, QPen
from PyQt5.QtWidgets import QGraphicsPathItem
from PyQt5.QtCore import QPointF

def draw_routed_edge(scene, grid_path, grid_resolution, pen):
    """在場景中繪製路由後的邊"""
    if not grid_path:
        return

    # 將網格路徑轉換為像素坐標
    pixel_path = [QPointF(x * grid_resolution + grid_resolution / 2, 
                          y * grid_resolution + grid_resolution / 2) 
                  for x, y in grid_path]
    
    # 創建 QPainterPath
    painter_path = QPainterPath(pixel_path)
    for point in pixel_path[1:]:
        painter_path.lineTo(point)

    # 創建 QGraphicsPathItem 並添加到場景
    path_item = QGraphicsPathItem(painter_path)
    path_item.setPen(pen)
    scene.addItem(path_item)

```

在主應用程式中，當需要重新路由邊線時（例如，在手動移動節點後），可以呼叫以上函數：

1. 從場景中獲取所有節點項，並使用 `create_grid_from_scene` 創建最新的障礙物網格。

2. 實例化 `OrthogonalRouter`。

3. 對於需要重新路由的每條邊，確定其在網格坐標系中的起點和終點。

4. 呼叫 `router.find_path()` 來計算路徑。

5. 使用 `draw_routed_edge()` 將計算出的路徑渲染到場景上。

這個從零開始的實作方法，雖然代碼量稍多，但賦予了開發者對路由行為的完全控制，能夠精確實作轉彎代價等複雜的美學規則，最終產生高度專業和清晰的技術圖表。

---

## **結論與未來展望**

本報告深入探討了階層式佈局和正交邊線路由這兩種核心的圖形視覺化技術，並提供了一套基於 Python 生態系統的完整實作方案。我們不僅僅停留在理論層面，而是深入到實作的每一個關鍵環節，揭示了那些在標準文檔中往往被忽略的、卻對成功至關重要的工程挑戰。

**綜合要點**

- **專業工具的槓桿作用**：對於像階層式佈局中計算密集且理論複雜的階段（如交叉最小化），最明智的策略是利用現有的、經過長期優化和驗證的專業引擎，如 `Graphviz` 的 `dot`。這體現了「不重新發明輪子」的工程智慧，讓開發者能專注於應用邏輯本身。

- **介面問題是核心挑戰**：成功的實作往往取決於能否解決不同系統之間的「介面」問題。本報告中，最關鍵的技術突破點在於**坐標系轉換**。準確地處理 `Graphviz`（點單位，Y 軸向上）和 `PyQt5`（像素單位，Y 軸向下）之間的單位、方向和原點差異，是將佈局計算結果正確渲染到畫布上的前提。

- **演算法狀態的擴展**：對於需要考慮路徑歷史的複雜成本函數（如正交路由中的轉彎代價），標準的 A\* 演算法狀態表示是不足的。透過將狀態從簡單的 `(x, y)` 位置擴展到包含上下文資訊的 `(x, y, arrival_direction)`，我們能夠在演算法層面直接建模和優化更高級的美學準則，這是實現高品質路由的根本。

- **三層架構的優勢**：本報告所倡導的架構——`NetworkX` (數據模型) + `Graphviz` (佈局引擎) + `PyQt5` (渲染框架)——展示了一種強大而靈活的模式。它將數據處理、複雜計算和使用者介面呈現清晰地分離開來，使得系統的每一部分都可以獨立替換或升級，具有良好的可維護性和擴展性。

**未來探索方向**

掌握了本報告中的基礎後，開發者可以向更廣闊的領域探索：

- **性能優化**：對於包含數千甚至數萬個節點的超大型圖形，本報告中的方法可能會遇到性能瓶頸。屆時，可以研究更高級的技術，例如用於力導向佈局的 Barnes-Hut 模擬或多層次佈局技術，以及用於 A\* 搜尋的 Jump Point Search 等優化演算法。

- **複雜節點與連接埠**：在實際應用中，節點可能不是簡單的橢圓，而是具有特定輸入/輸出連接埠的複雜形狀。正交路由器需要被擴展，以支持從特定的連接埠開始和結束路由，而不僅僅是節點的中心。

- **其他路由風格**：除了正交路由，還可以探索實現其他風格的邊線路由器。例如，有機邊線路由器（Organic Edge Router）會生成平滑的曲線路徑，這通常需要基於物理模擬或樣條插值等不同的路徑尋找方法。

總而言之，自動化圖形佈-局是一個深度融合了演算法理論、美學原則和軟體工程實踐的迷人領域。透過理解其背後的原理，並掌握解決關鍵實作挑戰的方法，開發者可以將原始、混亂的數據，轉化為富有洞察力、清晰且專業的視覺化作品。