"""主視窗模組"""

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QProgressBar,
)


class MainWindow(QWidget):
    """主視窗，負責建立各個分頁"""

    def __init__(self) -> None:
        super().__init__()
        self._create_monte_carlo_tab()

    def _create_monte_carlo_tab(self) -> None:
        """建立蒙地卡羅模擬分頁"""
        container = QVBoxLayout()
        control_layout = QHBoxLayout()

        # 建立模擬控制元件
        self.mc_run_button = QPushButton('開始模擬')
        control_layout.addWidget(self.mc_run_button)

        self.mc_progress_bar = QProgressBar()
        control_layout.addWidget(self.mc_progress_bar)

        # 連接按鈕與執行函式
        self.mc_run_button.clicked.connect(self.run_monte_carlo_simulation)

        container.addLayout(control_layout)
        self.setLayout(container)

    def run_monte_carlo_simulation(self) -> None:
        """執行蒙地卡羅模擬（占位方法）"""
        pass
