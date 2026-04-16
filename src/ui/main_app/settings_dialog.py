"""主視窗設定對話框。"""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)


class SettingsDialog(QDialog):
    """設定 k 係數的對話框。"""

    def __init__(self, current_params, parent=None):
        """初始化對話框。"""
        super().__init__(parent)
        self.setWindowTitle("k 係數參數設定")
        self.setModal(True)

        layout = QVBoxLayout()
        form_layout = QFormLayout()

        self.trfScaleInput = QLineEdit(str(current_params.get("trf_scale", 1.0)))
        self.trfDivisorInput = QLineEdit(str(current_params.get("trf_divisor", 10.0)))
        self.nCoefInput = QLineEdit(str(current_params.get("n_coef", 0.05)))

        self.overrideCheck = QCheckBox("直接覆蓋 k 值 (Override)")
        overrideValue = current_params.get("override")
        self.overrideInput = QLineEdit("" if overrideValue is None else str(overrideValue))
        self.overrideInput.setEnabled(False)

        form_layout.addRow("轉換比例 (trf_scale):", self.trfScaleInput)
        form_layout.addRow("轉換除數 (trf_divisor):", self.trfDivisorInput)
        form_layout.addRow("數量係數 (n_coef):", self.nCoefInput)
        form_layout.addRow(self.overrideCheck)
        form_layout.addRow("覆寫值:", self.overrideInput)
        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)
        self.overrideCheck.stateChanged.connect(
            lambda state: self.overrideInput.setEnabled(bool(state))
        )
        if overrideValue is not None:
            self.overrideCheck.setChecked(True)
            self.overrideInput.setEnabled(True)

    def get_settings(self):
        """讀取使用者輸入的設定值。"""
        try:
            override_value = None
            if self.overrideCheck.isChecked():
                override_text = self.overrideInput.text().strip()
                override_value = float(override_text) if override_text else None

            return {
                "base": 1.0,
                "trf_scale": float(self.trfScaleInput.text()),
                "trf_divisor": float(self.trfDivisorInput.text()),
                "n_coef": float(self.nCoefInput.text()),
                "override": override_value,
            }
        except ValueError:
            return None


__all__ = ["SettingsDialog"]
