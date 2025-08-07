# **適用於互動式圖形編輯器的進階正交與曲線邊線路由：針對 PyQt5 的 yEd 風格實現方案**

## **簡介**

在複雜系統的視覺化中，例如您正在開發的相依結構矩陣（DSM）編輯器，圖形的清晰度至關重要。一個佈局混亂、邊線肆意交叉的圖表會極大地增加使用者的認知負擔，使其難以辨識節點之間的關鍵依賴關係。業界公認的圖形視覺化工具 yEd Graph Editor 在這方面設立了標竿，其核心能力在於能夠生成具有高度可讀性與美學品質的圖表 。yEd 的成功關鍵之一，便是在自動佈局後應用的智慧邊線路由（Edge Routing）演算法。

本報告旨在提供一份完整且深入的技術指南，協助您在現有的 PyQt5 專案中，從理論到實踐，逐步構建一個媲美 yEd 的進階邊線路由系統。報告的核心目標是解決從簡單的直線連接，過渡到能夠智慧繞開節點與其他邊線，並能以正交或平滑曲線風格呈現的複雜路由問題。

本報告的結構將遵循一個從理論基礎到實踐細節的邏輯流程：

1. **第一部分：演算法基礎** 將深入剖析現代邊線路由技術背後的學術理論與核心演算法，為後續的工程實踐奠定堅實的理論基礎。

2. **第二部分：PyQt5 實踐指南** 將提供一個詳細的、可操作的實施藍圖，包括類別設計、關鍵演算法的 Python 虛擬碼，以及與您現有 PyQt5 架構的整合方案。

3. **第三部分：效能、可擴展性與進階主題** 將探討在處理大型圖形時確保系統即時互動性的關鍵策略，並討論系統的未來擴展方向。

透過本報告，您將獲得一套完整的工程文件，它不僅解釋了「為什麼」要這樣設計，更清晰地指明了「如何」在您的 DSM 編輯器中實現這一強大功能。

---

## **第一部分：進階邊線路由的演算法基礎**

高品質的邊線路由並非單一演算法的產物，而是一個精心設計的多階段處理管線。本部分將解構此管線，深入探討其背後的理論，為後續的實作提供清晰的指引。

### **第一節：現代邊線路由管線**

將 `QGraphicsScene` 中的視覺元素直接用於路徑規劃，計算成本極高且不切實際。現代路由引擎將此問題分解為一個標準化的處理流程 。這個架構性的模式是實現高效能與高彈性路由系統的基石。

1. **搜尋空間建構 (Search Space Construction)**：此階段的核心任務是將複雜的圖形場景（包含任意形狀的節點）抽象化為一個簡化的、適合路徑搜尋的資料結構。這是整個流程中最關鍵的抽象步驟。

2. **路徑尋找 (Pathfinding)**：在建構好的搜尋空間中，使用最佳化的圖搜尋演算法（如 A\*）來尋找一條從來源節點到目標節點的、成本最低且無碰撞的路徑。

3. **衝突解決與微調 (Collision Resolution & Nudging)**：當多條邊線競爭同一路徑時，A\* 演算法可能會為它們找到完全相同的路徑，導致視覺重疊。此階段負責解決這些衝突，將重疊的路徑彼此推開，以確保視覺上的分離。

4. **美學精煉 (Aesthetic Refinement)**：前幾個階段產生的路徑通常是由一系列直線段構成的多段線（Polyline）。此階段負責將這些帶有尖銳拐角的線條平滑化，轉換成視覺上更為流暢、美觀的曲線。

這種管線化的架構不僅使問題的每個子部分都更易於管理和優化，也提供了極大的彈性。例如，可以透過替換管線中的特定階段來支援不同的路由風格，而無需改動整個系統。



#### **路由風格：正交與有機**

根據您的需求，我們主要關注兩種路由風格：

- **正交路由 (Orthogonal Routing)**：邊線完全由水平和垂直線段組成。這種風格非常適合結構化的圖表，如您在階層式或正交佈局後使用的 DSM 。它的規則性和整潔性極大地提升了結構化資訊的可讀性。

- **有機/曲線路由 (Organic/Curved Routing)**：邊線由平滑的曲線或任意角度的直線段構成。這種風格更適用於力導向佈局等較為自由的佈局模式，能夠自然地繞開節點，呈現出流動的美感 。

本報告將首先詳細闡述更為複雜和結構化的正交路由引擎的設計與實現，然後說明如何調整此管線中的部分組件以支援曲線路由。



### **第二節：正交路由引擎：深度剖析**

正交路由是實現 yEd 風格佈局的核心技術之一。其背後的原理涉及將連續的 2D 空間離散化為一個圖，然後在該圖上解決經典的最短路徑問題。

#### **2\.1 正交可視性圖 (OVG)：搜尋空間的建構**



直接在充滿 `QGraphicsRectItem` 的場景中進行路徑搜尋是低效的。解決方案是預先處理場景，建構一個名為「正交可視性圖」（Orthogonal Visibility Graph, OVG）的輔助資料結構。OVG 是一個網格狀的圖，它代表了場景中所有可供邊線通行的「無障礙通道」。一旦 OVG 建立，複雜的幾何避障問題就轉化為一個標準的圖遍歷問題。

**OVG 的建構過程** 如下 ：

1. **識別「興趣點」(Interesting Points)**：收集場景中所有 `TaskNode` 物件的邊界框（Bounding Box）的四個角落座標。這些點定義了所有潛在的路由拐點。

2. **建立網格 (Grid Creation)**：從所有興趣點中提取所有唯一的 X 座標和 Y 座標。這些座標集合定義了一個覆蓋整個場景的虛擬網格。

3. **定義 OVG 頂點 (Vertices)**：網格的每個交叉點 `(x, y)` 都是 OVG 的一個潛在頂點。

4. **定義 OVG 邊 (Edges)**：在 OVG 中，只有相鄰的頂點之間（水平或垂直方向）才可能存在邊。一條連接相鄰頂點 `v1` 和 `v2` 的邊存在，若且唯若這條線段沒有與任何 `TaskNode` 的邊界框相交。

**增量更新 (Incremental Updates)**：在互動式應用中，使用者會頻繁拖動節點。每次節點移動後完全重建 OVG 的成本過高。因此，必須採用增量更新策略 。當一個

`TaskNode` 從舊位置移動到新位置時，我們無需重新計算整個 OVG。只需識別出該節點舊邊界框和新邊界框所影響的網格線，然後僅對這些局部區域的 OVG 邊進行重新驗證（即，重新進行碰撞檢測），即可高效地更新 OVG。這是實現即時互動回應的關鍵。

#### **2\.2 A\* 搜尋演算法：尋找最佳路徑**

有了 OVG 作為搜尋空間，下一步就是找到從邊線起點到終點的最佳路徑。在這個問題上，A\* 搜尋演算法是比 Dijkstra 演算法更優越的選擇 **10**。

為何選擇 A\*？

Dijkstra 演算法會以起點為中心，向所有方向均勻地探索，直到找到目標，這保證了路徑最短。然而，A\* 是一種「啟發式」或稱「知情」的搜尋演算法。它利用一個啟發函數（heuristic）來估計當前點到終點的距離，從而優先探索那些看起來更有希望的路徑。在 OVG 這種網格結構中，A\* 能夠在不犧牲路徑最優性的前提下，大幅減少需要探索的節點數量，從而顯著提升效能。

A\* 的核心：成本函數 f(n)=g(n)+h(n)

A\* 演算法的「智慧」完全體現在其成本函數的設計上。演算法在每一步都會選擇 f(n) 值最小的節點進行擴展。

- g(n)：從起點到目前節點 n 的實際成本

   這不是一個單一的值，而是一個加權和，用以平衡路徑長度和美學因素。一個典型的 g(n) 定義如下：

   g(n)=wlength​×length+wbends​×num_bends

   其中，length 是路徑的幾何長度，num_bends 是路徑的拐彎次數。權重 wlength​ 和 wbends​ 是可調參數，用於控制演算法對路徑長度和拐彎數量的偏好。例如，較高的 wbends​ 會使演算法傾向於生成拐彎更少的路徑，即使這會使路徑變長。

- h(n)：從目前節點 n 到終點的預估成本（啟發函數）

   啟發函數的設計至關重要。為了保證 A\* 找到最佳解，啟發函數必須是「可容許的」（admissible），即它永遠不能高估實際的剩餘成本。

   - **長度啟發 (hlength​)**：在正交網格中，曼哈頓距離（Manhattan distance）是計算兩點間最短正交路徑長度的完美啟發函數。hlength​(n)=∣n.x−goal.x∣+∣n.y−goal.y∣。

   - **拐彎啟發 (hbends​)**：可以設計一個簡單的啟發，例如，如果當前的前進方向與通往目標點的方向不一致，則預估至少還需要一次拐彎 。

A\* 的狀態表示

為了計算拐彎成本，僅僅追蹤節點位置是不夠的。A\* 演算法在其優先佇列（Priority Queue）中儲存的狀態，必須包含進入該節點時的方向 。一個典型的狀態元組（tuple）可以是：

`(priority, cost_so_far, position, entry_direction, parent_pointer)`。當從一個節點擴展到其鄰居時，如果前進方向發生改變，就在 `cost_so_far` 中增加一個拐彎的懲罰值。

下面的表格清晰地比較了 Dijkstra 和 A\* 演算法，並詳細分解了用於邊線路由的 A\* 成本函數。

**表 1: 路徑尋找演算法比較**

| 演算法 (Algorithm) | 原理 (Principle) | 最優性 (Optimality) | 效能 (Performance) | 關鍵特性 (Key Feature) | 適用場景 (Use Case) | 
|---|---|---|---|---|---|
| **Dijkstra** | 均勻探索，廣度優先的變體 | 保證找到最短路徑 | 較慢，探索節點多 | 僅考慮已走路徑的成本 | 尋找從單一起點到所有其他節點的最短路徑 | 
| **A\*** | 啟發式引導的知情搜尋 | 若啟發函數可容許，則保證最優 | 更快，探索節點少 | 結合已走成本和預估成本 | 高效尋找單一起點到單一目標的最短路徑 | 

**表 2: 用於邊線路由的 A\* 成本函數組成**

| 成本組成 (Component) | 描述 (Description) | 計算方法 (Calculation Method) | 虛擬碼片段 (Pseudocode Snippet) | 
|---|---|---|---|
| **路徑長度 (glength​)** | 從起點到當前節點的累積幾何長度。 | 累加每段 OVG 邊的長度。 | `new_g_len = parent.g_len + distance(parent, current)` | 
| **拐彎懲罰 (gbend​)** | 從起點到當前節點的累積拐彎次數。 | 如果當前移動方向與進入父節點的方向不同，則計為一次拐彎。 | `bend_cost = (current.dir!= parent.dir)? 1 : 0` | 
| **節點鄰近懲罰** | 為靠近其他節點的路徑增加微小成本，以產生更多留白。 | 計算路徑段到最近節點邊界的距離的倒數。 | `proximity_cost = 1 / min_dist_to_node(segment)` | 
| **啟發長度 (hlength​)** | 從當前節點到目標節點的最短可能正交距離。 | 曼哈頓距離。 | `h_len = abs(current.x - goal.x) + abs(current.y - goal.y)` | 
| **啟發拐彎 (hbend​)** | 從當前節點到目標節點的預估最少拐彎次數。 | 根據當前方向與目標方向的相對關係判斷（0, 1 或 2 次）。 | `h_bend = (current.dir!= direction_to_goal)? 1 : 0` | 

#### **2\.3 通道路由與邊線微調**

即使用了 A\* 演算法，一個新的問題很快就會出現：對於多條連接相同源和目標節點的邊線（例如您提到的雙向邊線），A\* 會為它們找到完全相同的最佳路徑，導致它們在視覺上完全重疊。

為了解決這個問題，我們需要引入源自 VLSI（超大規模積體電路）設計領域的「通道路由」（Channel Routing）概念 。在圖形佈局中，節點之間的空白區域可以被視為「通道」（Channels），而我們可以在這些通道內劃分出多條平行的「軌道」（Tracks）。目標是為每一條重疊的邊線分配一個獨一無二的軌道。

對於需要即時互動的應用程式，實現一個完整的、最優化的通道路由器過於複雜且耗時。因此，我們採用一種更為實用和高效的簡化版「微調」（Nudging）演算法 ：

1. **識別共享路段**：在所有邊線都透過 A\* 找到初始路徑後，遍歷這些路徑，識別出那些被多於一條邊線共享的 OVG 路段。

2. **確定邊線順序**：對於每一個共享路段，需要為共享該路段的所有邊線確定一個固定的、唯一的相對順序。這個順序可以簡單地基於每條邊線的唯一識別碼（ID）來決定，以保證每次重新佈局時結果的一致性。

3. **計算偏移量**：根據每條邊線在共享路段上的順序，為其計算一個垂直於路段方向的偏移量。例如，`offset = (order_index - total_edges / 2.0) * spacing`。其中 `spacing` 是一個預定義的間距值，`order_index` 是邊線的順序，`total_edges` 是共享該路段的總邊線數。

4. **應用偏移**：將計算出的偏移量應用於對應邊線路徑上的所有點，將其平移到新的軌道上。這就在視覺上產生了一組整齊排列的平行線。

這個簡化的微調演算法在效能和視覺效果之間取得了很好的平衡，足以滿足大多數互動式圖形編輯器的需求。

### **第三節：從多段線到平滑曲線**

經過 A\* 搜尋和微調後，我們得到的是一條由直角拐彎構成的多段線（Polyline）。雖然這在功能上是正確的，但為了達到 yEd 那種更為「有機」和流暢的視覺風格，我們需要最後一個美學精煉步驟：路徑平滑化。

#### **使用 Catmull-Rom 樣條進行路徑平滑**

在眾多曲線生成技術中，Catmull-Rom 樣條（Spline）特別適合此任務。

為何選擇 Catmull-Rom？

與常見的貝茲曲線（Bézier curves）不同，Catmull-Rom 樣條是一種「插值樣條」（interpolating spline）。這意味著生成的曲線會精確地穿過我們提供的所有控制點 21。這是一個至關重要的特性，因為我們希望平滑後的曲線能夠忠實地遵循由 A\* 演算法精心計算出的無碰撞路徑。如果使用貝茲曲線，其控制點通常位於曲線之外，這會使得曲線偏離原始安全路徑，可能導致新的碰撞。

向心 Catmull-Rom (Centripetal Catmull-Rom) 的優勢

Catmull-Rom 樣條有幾種變體，包括均勻（Uniform）、弦長（Chordal）和向心（Centripetal）。對於圖形路由，強烈推薦使用向心 Catmull-Rom 樣條。這是因為當控制點（即我們的路徑點）距離很近或轉角很尖銳時，均勻和弦長變體很容易產生自相交、尖點（cusps）或過衝（overshooting）等不美觀的瑕疵。而向心 Catmull-Rom 樣條在數學上被證明可以避免這些問題，生成更為穩定和緊湊的曲線 。

**表 3: Catmull-Rom 樣條變體比較**

| 變體 (Variant) | Alpha (α) 值 | 關鍵特性 (Key Characteristic) | 優點 (Pros) | 缺點 (Cons) | 推薦度 (Recommendation) | 
|---|---|---|---|---|---|
| **Uniform** | 0\.0 | 參數間距均勻，不考慮點間距離 | 計算最簡單 | 在急轉彎或點分佈不均時，易產生自相交和尖點 | 不推薦 | 
| **Chordal** | 1\.0 | 參數間距與點間弦長成正比 | 比 Uniform 穩定，減少過衝 | 仍可能產生不必要的曲線波動 | 可選，但非最優 | 
| **Centripetal** | 0\.5 | 參數間距與點間距離的平方根成正比 | **保證不產生自相交或尖點**，曲線最緊湊、最穩定 | 計算稍複雜 | **強烈推薦** | 

實現概念

實現 Catmull-Rom 樣條的過程如下：

1. 將 A\* 演算法找到的路徑點序列 `P1, P2,..., Pn` 作為樣條的控制點。

2. 要計算從點 `Pi` 到 `Pi+1` 之間的曲線段，公式需要前一個點 `Pi-1` 和後一個點 `Pi+2` 作為參考。

3. 對於路徑的第一段（`P1` 到 `P2`）和最後一段（`Pn-1` 到 `Pn`），需要特殊處理。一個簡單有效的方法是虛擬地複製起點和終點，即使用 `(P1, P1, P2, P3)` 來計算第一段，使用 `(Pn-2, Pn-1, Pn, Pn)` 來計算最後一段。

4. 將計算出的一系列平滑點連接起來，即可構成最終的曲線路徑。

透過這個四階段的管線，我們可以系統性地解決從簡單連線到複雜、美觀的 yEd 風格邊線路由的全部挑戰。下一部分將詳細闡述如何將這些理論轉化為具體的 PyQt5 程式碼。

---

## **第二部分：PyQt5 實踐指南**

本部分將理論轉化為可執行的藍圖，提供一個針對您現有 PyQt5 架構的詳細實現方案。我們將設計一套類別結構，並提供關鍵演算法的虛擬碼，指導您如何將進階路由功能無縫整合到您的 DSM 編輯器中。

### **第四節：系統架構與類別設計**

一個健壯的實現始於一個清晰的架構。我們將採用模組化的設計，將路由邏輯與現有的圖形介面元件分離，以提高可維護性和可擴展性。

#### **4\.1 `RoutingManager`：中央協調器**

這是整個路由系統的核心，作為一個中樞，協調所有路由相關的操作。

- **職責**：

   - 持有一個對 `QGraphicsScene` 的引用，以便存取場景中的所有圖元。

   - 管理底層的空間索引結構（`QuadTree`）和搜尋圖（`OrthogonalVisibilityGraph`）。

   - 對外提供高階 API，如 `routeAllEdges()` 和 `updateRoutingForMovedNode(node)`。

   - 根據當前的佈局風格（例如，正交或有機），選擇並執行對應的路由策略。

- **介面設計 (Python)**：

   **Python**

   ```python
   class RoutingManager:
       def __init__(self, scene: QGraphicsScene):
           self.scene = scene
           self.quadtree = QuadTree(scene.sceneRect())
           self.ovg = OrthogonalVisibilityGraph()
           self.edges_to_route = {} # Dict[EdgeItem, List[QPointF]]
   
       def build_spatial_index(self):
           # 遍歷 scene 中的 TaskNode，建立 Quadtree 和 OVG
           pass
   
       def route_all_edges(self):
           # 為場景中所有邊線計算路徑
           pass
   
       def update_routing_for_moved_node(self, node: TaskNode):
           # 增量更新受影響的邊線
           pass
   
       def get_path_for_edge(self, edge: EdgeItem) -> QPainterPath:
           # 根據計算結果生成最終的 QPainterPath
           pass
   
   ```



#### **4\.2 核心資料結構**

- OrthogonalVisibilityGraph 類別：

   這個類別封裝了 OVG 的資料和操作。內部可以使用一個簡單的字典來表示鄰接表，例如 self.graph = {QPointF: \[QPointF\]}。它應該提供新增/移除頂點和邊的方法，以及查詢鄰居的方法。為了效能，可以直接使用 networkx 庫，它提供了成熟的圖資料結構和演算法，但為了避免引入額外依賴，一個簡單的自訂類別也完全足夠。

- QuadTree 類別：

   四元樹是實現高效能空間查詢的關鍵。它將 2D 空間遞迴地劃分為四個象限，從而可以快速地找到位於特定區域內的所有物體。這對於加速 OVG 建構和增量更新至關重要 27。

   - **儲存內容**：樹的每個節點儲存其所代表的矩形區域 (`QRectF`) 以及落入該區域內的 `QGraphicsItem` 物件（或其邊界框）。

   - **關鍵方法**：

      - `insert(item: QGraphicsItem)`: 將一個圖元插入到樹中。

      - `remove(item: QGraphicsItem)`: 從樹中移除一個圖元。

      - `query(rect: QRectF) -> list[QGraphicsItem]`: 查詢與給定矩形區域相交的所有圖元。這是效能優化的核心。



#### **4\.3 與現有程式碼的整合**

將新的路由系統整合到您現有的 `DsmEditor`、`TaskNode` 和 `EdgeItem` 類別中，需要進行以下修改：

- **`DsmEditor` 的職責**：

   - 在初始化時，實例化一個 `RoutingManager`，並將 `self.scene` 傳遞給它。

   - 在執行自動佈局演算法（如階層式佈局）之後，呼叫 `routing_`[`manager.build`](manager.build)`_spatial_index()` 和 `routing_manager.route_all_edges()` 來觸發全局的智慧路由。

- TaskNode 的修改：利用 itemChange 掛鉤

   Qt 的 QGraphicsItem.itemChange() 方法提供了一個完美的機制來監聽圖元的變化，特別是位置變化。這是實現即時互動更新的理想切入點。

   **Python**

   ```python
   class TaskNode(QGraphicsRectItem):
       #... existing code...
       def __init__(self,..., routing_manager: RoutingManager):
           super().__init__(...)
           self.routing_manager = routing_manager
           self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
   
       def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
           if change == QGraphicsItem.ItemPositionChange and self.scene():
               # 'value' is the new position.
               # This is the hook for real-time updates.
               # A simple implementation for drag-and-drop end:
               # The scene event filter can detect mouse release.
               # A more advanced approach involves tracking mouse state.
               # For now, we assume the update is triggered on drop.
               # The DsmEditor will call routing_manager.update_...
               pass
   
           # A more robust pattern is to handle this in the mouseReleaseEvent
           # of the node or a scene event filter.
           return super().itemChange(change, value)
   
       def mouseReleaseEvent(self, event):
           # This is a reliable place to trigger the final update
           super().mouseReleaseEvent(event)
           if self.routing_manager:
               self.routing_manager.update_routing_for_moved_node(self)
   
   
   ```

   當節點被拖動並釋放後，`mouseReleaseEvent` 會被觸發，此時它會通知 `RoutingManager` 該節點的位置已更新，從而啟動增量路由計算。

- EdgeItem 的簡化：

   您的 EdgeItem 將不再需要自己計算路徑。它的職責被簡化為接收一個由 RoutingManager 計算好的 QPainterPath 並將其設定為自己的路徑。

   **Python**

   ```python
   class EdgeItem(QGraphicsPathItem):
       #... existing code...
   
       def update_path(self, path: QPainterPath):
           """
           This method is called by the RoutingManager to set the new,
           intelligently routed path.
           """
           self.setPath(path)
   
       # The old _buildPath method is no longer needed for complex routing.
       # It can be kept for a "simple mode" or fallback.
       def _build_simple_path(self, srcPoint: QPointF, dstPoint: QPointF):
           #... your original straight-line logic...
           path = QPainterPath(srcPoint)
           path.lineTo(dstPoint)
           self.setPath(path)
   
   ```



### **第五節：Python 演算法實現**

本節提供核心演算法的虛擬碼和 Python 實現思路，重點關注與 PyQt5 的結合。

#### **5\.1 建構路由網格 (OVG 與 Quadtree)**

此步驟的目標是將 `QGraphicsScene` 轉換為 OVG。

**Python**

```
# In RoutingManager class

def build_spatial_index(self):
    self.quadtree = QuadTree(self.scene.sceneRect())
    nodes =

    # 1. Populate the Quadtree
    for node in nodes:
        self.quadtree.insert(node)

    # 2. Build the Orthogonal Visibility Graph (OVG)
    self.ovg.clear()
    interesting_points_x = set()
    interesting_points_y = set()

    for node in nodes:
        rect = node.sceneBoundingRect()
        interesting_points_x.add(rect.left())
        interesting_points_x.add(rect.right())
        interesting_points_y.add(rect.top())
        interesting_points_y.add(rect.bottom())

    sorted_x = sorted(list(interesting_points_x))
    sorted_y = sorted(list(interesting_points_y))

    # Create OVG nodes
    grid_points = {QPointF(x, y) for x in sorted_x for y in sorted_y}
    self.ovg.add_nodes_from(grid_points)

    # 3. Create OVG edges by checking for collisions
    for i in range(len(sorted_x)):
        for j in range(len(sorted_y)):
            p1 = QPointF(sorted_x[i], sorted_y[j])

            # Horizontal edge check
            if i + 1 < len(sorted_x):
                p2 = QPointF(sorted_x[i+1], sorted_y[j])
                segment_rect = QRectF(p1, p2).normalized()
                # Use Quadtree to quickly find potential colliders
                potential_colliders = self.quadtree.query(segment_rect)
                is_obstructed = False
                for node in potential_colliders:
                    if node.sceneBoundingRect().intersects(segment_rect):
                        is_obstructed = True
                        break
                if not is_obstructed:
                    self.ovg.add_edge(p1, p2)

            # Vertical edge check (similar logic)
            if j + 1 < len(sorted_y):
                p2 = QPointF(sorted_x[i], sorted_y[j+1])
                segment_rect = QRectF(p1, p2).normalized()
                potential_colliders = self.quadtree.query(segment_rect)
                is_obstructed = False
                for node in potential_colliders:
                    if node.sceneBoundingRect().intersects(segment_rect):
                        is_obstructed = True
                        break
                if not is_obstructed:
                    self.ovg.add_edge(p1, p2)

```

#### **5\.2 A\* 路徑尋找模組**

使用 Python 的 `heapq` 模組可以高效地實現 A\* 所需的優先佇列。

**Python**

```python
import heapq

def find_path_astar(ovg, start_pos, end_pos, cost_function):
    # Find the nearest OVG nodes to the actual start/end points
    start_node = ovg.get_nearest_node(start_pos)
    end_node = ovg.get_nearest_node(end_pos)

    # Priority queue: (f_cost, g_cost, current_node, entry_direction, path_list)
    open_set = [(0, 0, start_node, None, [start_node])]
    closed_set = set()

    while open_set:
        f_cost, g_cost, current_node, entry_dir, path = heapq.heappop(open_set)

        if current_node == end_node:
            return path # Path found

        if (current_node, entry_dir) in closed_set:
            continue
        closed_set.add((current_node, entry_dir))

        for neighbor in ovg.get_neighbors(current_node):
            move_dir = get_direction(current_node, neighbor)
            new_g_cost = g_cost + cost_function(current_node, neighbor, entry_dir, move_dir)
            heuristic_cost = manhattan_distance(neighbor, end_node)
            new_f_cost = new_g_cost + heuristic_cost

            new_path = path + [neighbor]
            heapq.heappush(open_set, (new_f_cost, new_g_cost, neighbor, move_dir, new_path))

    return None # No path found

```

`cost_function` 將封裝在第一部分中討論的加權成本計算邏輯，包括路徑長度和拐彎懲罰。



#### **5\.3 碰撞檢測與微調實現**

- **線段-矩形碰撞檢測**：在 OVG 建構期間，需要一個高效的碰撞檢測函數。一個簡單且有效的方法是使用 `QRectF.intersects()`，因為我們的 OVG 邊是軸對齊的 。對於更通用的線段，可以使用 Liang-Barsky 演算法 。

- **微調虛擬碼**：

   **Python**

   ```python
   def nudge_paths(edge_path_map: dict[EdgeItem, list[QPointF]], spacing: float):
       segment_usage = {} # Key: (p1, p2) tuple, Value: list of EdgeItems
   
       # 1. Find shared segments
       for edge, path in edge_path_map.items():
           for i in range(len(path) - 1):
               p1, p2 = sorted_tuple(path[i], path[i+1]) # Ensure consistent key
               if (p1, p2) not in segment_usage:
                   segment_usage[(p1, p2)] =
               segment_usage[(p1, p2)].append(edge)
   
       nudged_paths = {}
       # 2. Calculate and apply offsets
       for edge, path in edge_path_map.items():
           new_path = [path]
           for i in range(len(path) - 1):
               p1_orig, p2_orig = path[i], path[i+1]
               p1_key, p2_key = sorted_tuple(p1_orig, p2_orig)
   
               shared_edges = segment_usage.get((p1_key, p2_key),)
               if len(shared_edges) > 1:
                   # Sort edges by a unique, stable ID to get a consistent order
                   shared_edges.sort(key=lambda e: id(e))
                   order_index = shared_edges.index(edge)
                   total_edges = len(shared_edges)
   
                   offset_dist = (order_index - (total_edges - 1) / 2.0) * spacing
   
                   # Calculate perpendicular vector for offset
                   dx = p2_orig.x() - p1_orig.x()
                   dy = p2_orig.y() - p1_orig.y()
                   perp_vec = QPointF(-dy, dx)
                   norm = (perp_vec.x()**2 + perp_vec.y()**2)**0.5
                   if norm > 0:
                       unit_perp = perp_vec / norm
                       offset_vec = unit_perp * offset_dist
   
                       # Apply offset to the next point in the path
                       new_p2 = p2_orig + offset_vec
                       # The start point of the segment is the end point of the previous one
                       new_path[-1] = p1_orig + offset_vec
                       new_path.append(new_p2)
               else:
                   new_path.append(p2_orig)
   
           nudged_paths[edge] = new_path
       return nudged_paths
   
   ```

#### **5\.4 路徑平滑化與 `QPainterPath` 生成**

最後一步是將微調後的多段線路徑轉換為平滑的 `QPainterPath`。

- **Centripetal Catmull-Rom Python 實現**：

   **Python**

   ```python
   def get_catmull_rom_point(p0, p1, p2, p3, t, alpha=0.5):
       """
       Computes a point on a Centripetal Catmull-Rom spline.
       alpha = 0.0 for uniform, 0.5 for centripetal, 1.0 for chordal.
       """
       def get_knot(t, p_i, p_j, alpha):
           #... implementation based on...[25, 26]
           dist_sq = (p_i.x()-p_j.x())**2 + (p_i.y()-p_j.y())**2
           return pow(dist_sq, alpha/2.0) + t
   
       t0 = 0.0
       t1 = get_knot(t0, p0, p1, alpha)
       t2 = get_knot(t1, p1, p2, alpha)
       t3 = get_knot(t2, p2, p3, alpha)
   
       t_interp = t1 + (t2 - t1) * t
   
       A1 = (t1 - t_interp) / (t1 - t0) * p0 + (t_interp - t0) / (t1 - t0) * p1
       A2 = (t2 - t_interp) / (t2 - t1) * p1 + (t_interp - t1) / (t2 - t1) * p2
       A3 = (t3 - t_interp) / (t3 - t2) * p2 + (t_interp - t2) / (t3 - t2) * p3
   
       B1 = (t2 - t_interp) / (t2 - t0) * A1 + (t_interp - t0) / (t2 - t0) * A2
       B2 = (t3 - t_interp) / (t3 - t1) * A2 + (t_interp - t1) / (t3 - t1) * A3
   
       C = (t2 - t_interp) / (t2 - t1) * B1 + (t_interp - t1) / (t2 - t1) * B2
       return C
   
   def smooth_path_catmull_rom(points: list[QPointF], num_segments=10) -> QPainterPath:
       if len(points) < 2:
           return QPainterPath()
   
       path = QPainterPath(points)
       if len(points) < 4: # Cannot form a full spline, use line
           for p in points[1:]:
               path.lineTo(p)
           return path
   
       # Pad the points list for start and end segments
       padded_points = [points] + points + [points[-1]]
   
       for i in range(1, len(padded_points) - 2):
           p0, p1, p2, p3 = padded_points[i-1], padded_points[i], padded_points[i+1], padded_points[i+2]
   
           # Generate intermediate points for the segment
           for t_step in range(1, num_segments + 1):
               t = float(t_step) / num_segments
               point_on_curve = get_catmull_rom_point(p0, p1, p2, p3, t)
               path.lineTo(point_on_curve)
   
       return path
   
   ```

   這個 `smooth_path_catmull_rom` 函數的輸出可以直接用於 `EdgeItem.setPath()`，從而完成從抽象演算法到具體視覺呈現的閉環。

---

## **第三部分：效能、可擴展性與進階主題**

一個功能強大的路由系統如果不能在大型圖上保持流暢的互動性，其價值將大打折扣。本部分將專注於效能工程，確保您的 DSM 編輯器即使在處理超過 100 個節點和 200 條邊線的複雜圖時，依然能提供即時的回應。

### **第六節：實現即時互動性**

實現即時互動的秘訣不在於單一的演算法優化，而在於一個整體的架構策略，它結合了高效的資料結構和智慧的更新模式。

#### **6\.1 四元樹在動態場景中的核心作用**

四元樹不僅僅是一個理論上的優化，它是在動態場景中實現高效能的基石。它的作用體現在路由管線的每一個需要空間查詢的環節。

- **加速 OVG 建構**：在建構 OVG 時，我們需要為網格上的每一條潛在邊線進行碰撞檢測。若採用暴力法，需要將該線段與場景中所有的 N 個節點進行比較，總複雜度極高。而利用四元樹，我們可以快速查詢到僅與該線段的邊界框重疊的節點子集，將單次查詢的複雜度從 O(N) 降至 O(logN)，從而大幅提升 OVG 的初始建構速度。

- **加速增量更新**：當一個節點被拖動後，我們需要更新 OVG。四元樹可以迅速定位節點舊位置和新位置周邊的區域。這使得我們能夠精確地只更新受影響的局部網格，而不是整個 OVG。同樣，我們還需要找出路徑穿過了節點新位置的所有邊線，並對它們進行重路由。四元樹的 `query` 功能同樣能高效地完成此任務，將全域問題局部化，這是實現互動效能的關鍵 。

#### **6\.2 「拖動時簡化，釋放時計算」的增量更新策略**

即時在每一次滑鼠移動事件中都重新計算數十條複雜路徑，即使有四元樹和增量更新，也幾乎是不可能的，會導致明顯的延遲 。使用者體驗的關鍵在於提供即時的視覺回饋。因此，我們採用一種在業界廣泛使用的效能模式：「拖動時簡化，釋放時計算」。

1. **節點拖動開始時 (On Node Drag Start)**：無需執行任何路由計算。

2. **節點拖動過程中 (During Node Drag)**：為了提供最流暢的視覺回饋，此時應暫時放棄智慧路由。僅將與被拖動節點直接相連的邊線，動態地重繪為簡單的直線。直線的計算成本極低，可以確保畫面更新毫無延遲。

3. 節點拖動結束時 (On Node Drag End / Mouse Release)：這是觸發完整但增量的路由管線的時刻。

   a. TaskNode 的 mouseReleaseEvent 通知 RoutingManager。

   b. RoutingManager 從四元樹和 OVG 中移除該節點的舊資訊。

   c. 將節點以新位置重新插入四元樹，並更新 OVG 的局部區域。

   d. 識別所有需要重路由的邊線。這包括：

   i. 所有直接連接到被移動節點的邊線。

   ii. 所有其原始路徑與被移動節點的舊或新邊界框相交的邊線（透過四元樹快速查詢）。

   e. 僅僅為這些受影響的邊線執行 A\* 路徑尋找演算法。

   f. 對找到的新路徑執行微調（Nudging）和美學精煉（Smoothing）。

   g. 更新這些受影響的 EdgeItem 的 QPainterPath。

這種兩階段的更新策略，透過在互動過程中提供一個「廉價」的視覺代理（直線），並將「昂貴」的計算推遲到互動結束的單一時間點，完美地平衡了效能與功能，為使用者創造了即時回應的假象。

**表 4: 效能優化技術及其影響**

| 技術 (Technique) | 描述 (Description) | 關鍵操作複雜度 (Key Operation Complexity) | 對互動性的影響 (Impact on Interactivity) | 
|---|---|---|---|
| **暴力法 (Brute Force)** | 每次碰撞檢測都遍歷所有 N 個節點。 | 尋找相交物體：O(N) | 在節點數 > 20 時幾乎無法使用，嚴重卡頓。 | 
| **四元樹空間索引** | 使用四元樹進行空間查詢，將搜尋範圍縮小。 | 尋找相交物體：O(logN) | 顯著提升效能，可支援 > 200 節點的場景。 | 
| **拖動時全局重算** | 在滑鼠釋放後，重新計算所有邊線的路徑。 | 路由計算：O(E⋅A-Star) | 在邊線數量多時，拖動後會有可感知的延遲。 | 
| **拖動時增量更新** | 在滑鼠釋放後，僅重新計算受影響的邊線。 | 路由計算：O(Eaffected​⋅A-Star) | 最佳方案，拖動後的回應近乎即時。 | 



#### **6\.3 複雜度分析**

- **時間複雜度**：

   - **OVG 建構 (帶四元樹)**：主要開銷在於遍歷網格線並查詢碰撞。網格大小最壞情況下與節點數 N 的平方成正比，但實際上更稀疏。每次查詢為 O(logN)，總體建構時間約為 O(NlogN) 到 O(N2) 之間，取決於節點分佈的密集程度。

   - **A\* 搜尋**：在 OVG 上的搜尋複雜度為 O(∣Eovg​∣+∣Vovg​∣log∣Vovg​∣)。由於 OVG 的頂點數 ∣Vovg​∣ 最壞可達 O(N2)，因此單次搜尋的複雜度可能很高 。但增量更新策略極大地限制了需要執行 A\* 的次數。

   - **微調 (Nudging)**：複雜度約為 O(Erouted​×Lavg​)，其中 Erouted​ 是被路由的邊線數，Lavg​ 是平均路徑長度。

- **空間複雜度**：

   - **OVG**：最主要的空間開銷。在最壞的棋盤格佈局下，其頂點和邊的數量可以是 O(N2) 。

   - **四元樹**：空間複雜度為 O(N)，因為每個節點只被儲存一次。

   - **路徑資料**：儲存每條邊線的路徑點，空間複雜度為 O(E×Lavg​)。

### **第七節：未來擴展與進階考量**

一個優秀的系統設計應當為未來的需求預留擴展空間。

#### **7\.1 替代視覺化方案：邊線捆綁**

對於連接極其密集的圖（例如，全連接的子圖），即使是最好的正交路由也可能因為線條過多而顯得雜亂。在這種情況下，「邊線捆綁」（Edge Bundling）提供了一種完全不同的視覺化範式。

- **概念**：它將走向大致相同的邊線「捆綁」在一起，形成更粗的「線纜」，從而突出宏觀的連接趨勢，而不是單個的連接細節。

- **適用場景**：更適合用於資料探索和概覽，而非 DSM 所需的精確依賴關係追蹤。

- **Python 實現**：可以探索如 `datashader`  或

   `netgraph` 等 Python 庫，它們提供了諸如「Hammer Bundling」等邊線捆綁演算法的實現。這可以作為您編輯器未來的一個高階視覺化模式。



#### **7\.2 處理多重邊線與雙向邊線**

您的需求中明確提到了雙向邊線。我們在 2.3 節中提出的「微調/通道路由」方法是解決這個問題的直接方案。當兩條或多條邊線共享同一對源/目標節點時，A\* 會為它們找到相同的幾何路徑。微調演算法透過為每條邊線分配一個唯一的、穩定的順序（基於其 `id()` 或其他唯一屬性），並據此計算偏移量，從而將它們整齊地並排佈置，完美地解決了多重邊線和雙向邊線的視覺重疊問題。

#### **7\.3 面向擴展的 API 設計**

為了讓系統更具彈性，建議在 `RoutingManager` 的設計中採用「策略模式」（Strategy Pattern）。您可以定義一個抽象的 `RoutingStrategy` 基礎類別，然後實現 `OrthogonalRoutingStrategy` 和 `OrganicRoutingStrategy` 等具體策略。

**Python**

```python
from abc import ABC, abstractmethod

class RoutingStrategy(ABC):
    @abstractmethod
    def route_edges(self, manager: RoutingManager, edges: list[EdgeItem]):
        pass

class OrthogonalRoutingStrategy(RoutingStrategy):
    def route_edges(self, manager: RoutingManager, edges: list[EdgeItem]):
        #... 實現基於 OVG 和 A* 的正交路由邏輯...
        pass

class RoutingManager:
    def __init__(self, scene: QGraphicsScene):
        #...
        self.current_strategy = OrthogonalRoutingStrategy()

    def set_strategy(self, strategy: RoutingStrategy):
        self.current_strategy = strategy

    def route_all_edges(self):
        edges = [item for item in self.scene.items() if isinstance(item, EdgeItem)]
        self.current_strategy.route_edges(self, edges)

```

這種設計使得未來新增一種全新的路由風格（例如，邊線捆綁策略）變得非常簡單，只需實現一個新的策略類別並將其設定到 `RoutingManager` 中，而無需修改任何核心的整合或更新邏輯。

## **結論與建議**

本報告提供了一套全面且可行的方案，旨在為您的 PyQt5 DSM 編輯器實現一個功能強大且具備高度美學品質的 yEd 風格邊線路由系統。我們從底層的圖論演算法出發，逐步過渡到具體的系統架構設計、Python 程式碼實現，並最終探討了確保即時互動效能的關鍵工程策略。

**核心建議總結如下：**

1. **採用管線式架構**：將路由過程分解為**搜尋空間建構**、**A\* 路徑尋找**、**衝突解決與微調**、**美學精煉**四個獨立階段。這種模組化設計是實現複雜功能和未來擴展性的基礎。

2. **以 OVG 和 A\* 為正交路由核心**：利用**正交可視性圖（OVG）** 將幾何避障問題轉化為圖搜尋問題。採用**A\* 演算法**，並設計一個同時考慮**路徑長度**和**拐彎數量**的成本函數，來尋找兼具效率與美觀的最佳路徑。

3. **利用四元樹加速空間查詢**：整合一個健壯的**四元樹**資料結構，用於加速 OVG 的建構和增量更新過程中的所有空間查詢操作。這是滿足大型圖（>100 節點）效能目標的關鍵。

4. **實施「拖動時簡化，釋放時計算」的互動策略**：為了保證使用者拖動節點時的流暢體驗，應在拖動過程中將邊線繪製為簡單直線，僅在滑鼠釋放時觸發基於四元樹和 OVG 的**增量式重路由**。

5. **透過向心 Catmull-Rom 樣條實現路徑平滑**：對於需要曲線風格的場景，使用**向心 Catmull-Rom 樣條**對 A\* 產生的多段線路徑進行平滑處理。該方法能有效避免自相交和尖點，生成視覺上最為理想的平滑曲線。

6. **將路由邏輯與 Qt 圖元緊密但低耦合地整合**：設計一個中央 `RoutingManager` 類別來處理所有路由邏輯。利用 `TaskNode` 的 `mouseReleaseEvent` 或 `itemChange` 作為觸發增量更新的掛鉤，並讓 `EdgeItem` 的職責簡化為僅接收和顯示由 `RoutingManager` 生成的 `QPainterPath`。

遵循本報告提供的設計藍圖和實現指南，您將能夠在現有專案的基礎上，成功構建一個不僅功能強大，而且在效能和視覺效果上都能達到專業水準的進階邊線路由系統，從而極大地提升您 DSM 編輯器的可用性和專業性。