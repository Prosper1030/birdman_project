"""階層佈局設定對話框 - 仿 yEd 風格"""

from typing import Dict, Any
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QDoubleSpinBox, QComboBox,
    QPushButton, QTabWidget, QWidget, QCheckBox,
    QSpinBox
)


class HierarchicalLayoutDialog(QDialog):
    """階層佈局設定對話框 - 仿 yEd 的 Hierarchic Layout 設定面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("階層佈局設定")
        self.setModal(True)
        self.setFixedSize(450, 650)

        # 從父視窗獲取當前設定，如果沒有則使用預設值
        self.current_settings = self._load_current_settings()

        self.setupUI()
        self.loadSettings()

    def _load_current_settings(self) -> Dict[str, Any]:
        """從父視窗載入當前設定"""
        if hasattr(self.parent(), 'layout_direction'):
            return {
                'orientation': self.parent().layout_direction,
                'layer_spacing': getattr(self.parent(), 'layer_spacing', 200),
                'node_spacing': getattr(self.parent(), 'node_spacing', 150),
                'isolated_spacing': getattr(self.parent(), 'isolated_spacing', 100),

                # 最小距離設定（從 hierarchical.py 的預設值）
                'min_node_node': 30.0,
                'min_node_edge': 15.0,
                'min_edge_edge': 15.0,
                'min_layer_layer': 10.0,

                # 節點和邊的設定
                'node_width': 120,
                'node_height': 60,
                'node_margin': 8,
                'min_gap': 16,

                # 高級設定
                'layout_components_separately': False,
                'use_drawing_as_sketch': False,
                
                # 路由設定
                'routing_style': 'normal'  # 'normal' 或 'orthogonal'
            }
        else:
            return {
                'orientation': 'TB',
                'layer_spacing': 200,
                'node_spacing': 150,
                'isolated_spacing': 100,
                'min_node_node': 30.0,
                'min_node_edge': 15.0,
                'min_edge_edge': 15.0,
                'min_layer_layer': 10.0,
                'node_width': 120,
                'node_height': 60,
                'node_margin': 8,
                'min_gap': 16,
                'layout_components_separately': False,
                'use_drawing_as_sketch': False,
                'routing_style': 'normal'
            }

    def setupUI(self):
        """設定使用者介面"""
        layout = QVBoxLayout(self)

        # 建立分頁介面
        tab_widget = QTabWidget()

        # 一般設定頁面
        general_tab = self.create_general_tab()
        tab_widget.addTab(general_tab, "一般")

        # 最小距離頁面
        distances_tab = self.create_distances_tab()
        tab_widget.addTab(distances_tab, "最小距離")

        # 高級設定頁面
        advanced_tab = self.create_advanced_tab()
        tab_widget.addTab(advanced_tab, "高級")

        layout.addWidget(tab_widget)

        # 按鈕區
        button_layout = QHBoxLayout()

        self.ok_button = QPushButton("確定")
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setDefault(True)

        self.reset_button = QPushButton("重設")
        self.reset_button.clicked.connect(self.reset_to_defaults)

        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)

        self.dock_button = QPushButton("停駐")
        self.dock_button.setEnabled(False)  # 暫不支援

        self.help_button = QPushButton("說明")
        self.help_button.clicked.connect(self.show_help)

        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.reset_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.dock_button)
        button_layout.addWidget(self.help_button)

        layout.addLayout(button_layout)

    def create_general_tab(self) -> QWidget:
        """建立一般設定頁面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 互動設定群組
        interactive_group = QGroupBox("互動設定")
        interactive_layout = QFormLayout(interactive_group)

        self.incrementally_checkbox = QCheckBox()
        self.incrementally_checkbox.setChecked(False)
        interactive_layout.addRow("選取元素增量:", self.incrementally_checkbox)

        self.sketch_checkbox = QCheckBox()
        self.sketch_checkbox.setChecked(False)
        interactive_layout.addRow("使用圖形作為草圖:", self.sketch_checkbox)

        layout.addWidget(interactive_group)

        # 方向設定群組
        orientation_group = QGroupBox("方向")
        orientation_layout = QFormLayout(orientation_group)

        self.orientation_combo = QComboBox()
        self.orientation_combo.addItems(["上到下", "左到右"])
        orientation_layout.addRow("", self.orientation_combo)

        layout.addWidget(orientation_group)

        # 佈局設定群組
        layout_group = QGroupBox("佈局設定")
        layout_layout = QFormLayout(layout_group)

        self.components_separately_checkbox = QCheckBox()
        self.components_separately_checkbox.setChecked(False)
        layout_layout.addRow("分別佈局元件:", self.components_separately_checkbox)

        layout.addWidget(layout_group)

        # 路由樣式群組
        routing_group = QGroupBox("路由樣式")
        routing_layout = QFormLayout(routing_group)
        
        self.routing_combo = QComboBox()
        self.routing_combo.addItems(["正設", "正射"])  # 正設=正常預設, 正射=正交
        self.routing_combo.setCurrentIndex(0)  # 預設選擇正設
        routing_layout.addRow("", self.routing_combo)
        
        layout.addWidget(routing_group)

        # 間距設定群組
        spacing_group = QGroupBox("間距設定")
        spacing_layout = QFormLayout(spacing_group)

        # 層間距離
        self.layer_spacing_spin = QSpinBox()
        self.layer_spacing_spin.setRange(50, 1000)
        self.layer_spacing_spin.setSuffix(" px")
        self.layer_spacing_spin.setValue(200)
        spacing_layout.addRow("層間距離:", self.layer_spacing_spin)

        # 節點間距離
        self.node_spacing_spin = QSpinBox()
        self.node_spacing_spin.setRange(50, 500)
        self.node_spacing_spin.setSuffix(" px")
        self.node_spacing_spin.setValue(150)
        spacing_layout.addRow("節點間距離:", self.node_spacing_spin)

        # 孤立節點間距
        self.isolated_spacing_spin = QSpinBox()
        self.isolated_spacing_spin.setRange(20, 300)
        self.isolated_spacing_spin.setSuffix(" px")
        self.isolated_spacing_spin.setValue(100)
        spacing_layout.addRow("孤立節點間距:", self.isolated_spacing_spin)

        layout.addWidget(spacing_group)

        layout.addStretch()
        return widget

    def create_distances_tab(self) -> QWidget:
        """建立最小距離設定頁面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 最小距離群組
        distances_group = QGroupBox("最小距離")
        distances_layout = QFormLayout(distances_group)

        # 節點到節點距離
        self.node_node_spin = QDoubleSpinBox()
        self.node_node_spin.setRange(10.0, 200.0)
        self.node_node_spin.setSingleStep(5.0)
        self.node_node_spin.setSuffix(" px")
        self.node_node_spin.setValue(30.0)
        distances_layout.addRow("節點到節點距離:", self.node_node_spin)

        # 節點到邊距離
        self.node_edge_spin = QDoubleSpinBox()
        self.node_edge_spin.setRange(5.0, 100.0)
        self.node_edge_spin.setSingleStep(2.5)
        self.node_edge_spin.setSuffix(" px")
        self.node_edge_spin.setValue(15.0)
        distances_layout.addRow("節點到邊距離:", self.node_edge_spin)

        # 邊到邊距離
        self.edge_edge_spin = QDoubleSpinBox()
        self.edge_edge_spin.setRange(5.0, 100.0)
        self.edge_edge_spin.setSingleStep(2.5)
        self.edge_edge_spin.setSuffix(" px")
        self.edge_edge_spin.setValue(15.0)
        distances_layout.addRow("邊到邊距離:", self.edge_edge_spin)

        # 層到層距離
        self.layer_layer_spin = QDoubleSpinBox()
        self.layer_layer_spin.setRange(5.0, 50.0)
        self.layer_layer_spin.setSingleStep(2.5)
        self.layer_layer_spin.setSuffix(" px")
        self.layer_layer_spin.setValue(10.0)
        distances_layout.addRow("層到層距離:", self.layer_layer_spin)

        layout.addWidget(distances_group)

        # 節點尺寸群組
        node_group = QGroupBox("節點尺寸")
        node_layout = QFormLayout(node_group)

        # 節點寬度
        self.node_width_spin = QSpinBox()
        self.node_width_spin.setRange(60, 300)
        self.node_width_spin.setSuffix(" px")
        self.node_width_spin.setValue(120)
        node_layout.addRow("節點寬度:", self.node_width_spin)

        # 節點高度
        self.node_height_spin = QSpinBox()
        self.node_height_spin.setRange(30, 150)
        self.node_height_spin.setSuffix(" px")
        self.node_height_spin.setValue(60)
        node_layout.addRow("節點高度:", self.node_height_spin)

        # 節點邊距
        self.node_margin_spin = QSpinBox()
        self.node_margin_spin.setRange(2, 50)
        self.node_margin_spin.setSuffix(" px")
        self.node_margin_spin.setValue(8)
        node_layout.addRow("節點邊距:", self.node_margin_spin)

        # 最小間隙
        self.min_gap_spin = QSpinBox()
        self.min_gap_spin.setRange(8, 100)
        self.min_gap_spin.setSuffix(" px")
        self.min_gap_spin.setValue(16)
        node_layout.addRow("最小間隙:", self.min_gap_spin)

        layout.addWidget(node_group)

        layout.addStretch()
        return widget

    def create_advanced_tab(self) -> QWidget:
        """建立高級設定頁面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 高級佈局選項群組
        advanced_group = QGroupBox("高級佈局選項")
        advanced_layout = QFormLayout(advanced_group)

        # 對稱放置
        self.symmetric_checkbox = QCheckBox()
        self.symmetric_checkbox.setChecked(False)
        self.symmetric_checkbox.setEnabled(False)  # 暫不支援
        advanced_layout.addRow("對稱放置:", self.symmetric_checkbox)

        # 節點類型 (暫不支援)
        self.node_types_combo = QComboBox()
        self.node_types_combo.addItems(["無"])
        self.node_types_combo.setEnabled(False)
        advanced_layout.addRow("節點類型:", self.node_types_combo)

        # 最大持續時間
        self.max_duration_spin = QSpinBox()
        self.max_duration_spin.setRange(10, 300)
        self.max_duration_spin.setSuffix(" 秒")
        self.max_duration_spin.setValue(30)
        self.max_duration_spin.setEnabled(False)  # 暫不支援
        advanced_layout.addRow("最大持續時間:", self.max_duration_spin)

        layout.addWidget(advanced_group)

        # 說明文字
        info_label = QLabel(
            "此頁面包含進階佈局選項。\n"
            "部分功能尚未實現，將在未來版本中加入。"
        )
        info_label.setStyleSheet("color: #666; font-style: italic;")
        info_label.setWordWrap(True)

        layout.addWidget(info_label)
        layout.addStretch()
        return widget

    def loadSettings(self):
        """載入設定到控制項"""
        settings = self.current_settings

        # 一般設定
        if settings['orientation'] == 'TB':
            self.orientation_combo.setCurrentIndex(0)
        else:
            self.orientation_combo.setCurrentIndex(1)

        self.layer_spacing_spin.setValue(settings['layer_spacing'])
        self.node_spacing_spin.setValue(settings['node_spacing'])
        self.isolated_spacing_spin.setValue(settings['isolated_spacing'])

        self.components_separately_checkbox.setChecked(settings['layout_components_separately'])
        self.sketch_checkbox.setChecked(settings['use_drawing_as_sketch'])
        
        # 路由設定
        if settings['routing_style'] == 'normal':
            self.routing_combo.setCurrentIndex(0)  # 正設
        else:
            self.routing_combo.setCurrentIndex(1)  # 正射

        # 最小距離設定
        self.node_node_spin.setValue(settings['min_node_node'])
        self.node_edge_spin.setValue(settings['min_node_edge'])
        self.edge_edge_spin.setValue(settings['min_edge_edge'])
        self.layer_layer_spin.setValue(settings['min_layer_layer'])

        # 節點尺寸
        self.node_width_spin.setValue(settings['node_width'])
        self.node_height_spin.setValue(settings['node_height'])
        self.node_margin_spin.setValue(settings['node_margin'])
        self.min_gap_spin.setValue(settings['min_gap'])

    def getSettings(self) -> Dict[str, Any]:
        """取得使用者設定的參數"""
        return {
            'orientation': 'TB' if self.orientation_combo.currentIndex() == 0 else 'LR',
            'layer_spacing': self.layer_spacing_spin.value(),
            'node_spacing': self.node_spacing_spin.value(),
            'isolated_spacing': self.isolated_spacing_spin.value(),

            'min_node_node': self.node_node_spin.value(),
            'min_node_edge': self.node_edge_spin.value(),
            'min_edge_edge': self.edge_edge_spin.value(),
            'min_layer_layer': self.layer_layer_spin.value(),

            'node_width': self.node_width_spin.value(),
            'node_height': self.node_height_spin.value(),
            'node_margin': self.node_margin_spin.value(),
            'min_gap': self.min_gap_spin.value(),

            'layout_components_separately': self.components_separately_checkbox.isChecked(),
            'use_drawing_as_sketch': self.sketch_checkbox.isChecked(),
            'routing_style': 'normal' if self.routing_combo.currentIndex() == 0 else 'orthogonal',
        }

    def reset_to_defaults(self):
        """重設為預設值"""
        defaults = {
            'orientation': 'TB',
            'layer_spacing': 200,
            'node_spacing': 150,
            'isolated_spacing': 100,
            'min_node_node': 30.0,
            'min_node_edge': 15.0,
            'min_edge_edge': 15.0,
            'min_layer_layer': 10.0,
            'node_width': 120,
            'node_height': 60,
            'node_margin': 8,
            'min_gap': 16,
            'layout_components_separately': False,
            'use_drawing_as_sketch': False,
            'routing_style': 'normal'
        }

        self.current_settings = defaults
        self.loadSettings()

    def show_help(self):
        """顯示說明"""
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            "說明",
            "階層佈局設定說明：\n\n"
            "• 方向：選擇佈局的主要方向（上到下或左到右）\n"
            "• 層間距離：控制不同階層之間的距離\n"
            "• 節點間距離：控制同一階層內節點的間距\n"
            "• 孤立節點間距：控制沒有連接的節點間距\n"
            "• 最小距離：設定各種元素間的最小安全距離\n"
            "• 節點尺寸：調整節點的外觀尺寸"
        )
