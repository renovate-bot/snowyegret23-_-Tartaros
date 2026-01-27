from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QSpinBox, QCheckBox,
    QComboBox, QPushButton, QGroupBox, QFormLayout, QFileDialog, QTextEdit
)
from PySide6.QtCore import Qt
from ui.i18n import tr


def labeled_edit(label: str, placeholder: str = ""):
    w = QWidget()
    layout = QHBoxLayout(w)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    lab = QLabel(label)
    edit = QLineEdit()
    if placeholder:
        edit.setPlaceholderText(placeholder)
    layout.addWidget(lab)
    layout.addWidget(edit, 1)
    return w, edit


def labeled_textarea(label: str, placeholder: str = ""):
    w = QWidget()
    layout = QHBoxLayout(w)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    lab = QLabel(label)
    edit = QTextEdit()
    if placeholder:
        edit.setPlaceholderText(placeholder)
    edit.setFixedHeight(70)
    layout.addWidget(lab)
    layout.addWidget(edit, 1)
    return w, edit


def path_picker(label: str, placeholder: str = ""):
    w = QWidget()
    layout = QHBoxLayout(w)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    lab = QLabel(label)
    edit = QLineEdit()
    if placeholder:
        edit.setPlaceholderText(placeholder)
    btn = QPushButton("...")
    btn.setFixedWidth(32)

    def choose():
        path = QFileDialog.getExistingDirectory(w, tr("dialog.select_folder"))
        if path:
            edit.setText(path)

    btn.clicked.connect(choose)
    layout.addWidget(lab)
    layout.addWidget(edit, 1)
    layout.addWidget(btn)
    return w, edit


def file_picker(label: str, placeholder: str = ""):
    w = QWidget()
    layout = QHBoxLayout(w)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    lab = QLabel(label)
    edit = QLineEdit()
    if placeholder:
        edit.setPlaceholderText(placeholder)
    btn = QPushButton("...")
    btn.setFixedWidth(32)

    def choose():
        path, _ = QFileDialog.getOpenFileName(w, tr("dialog.select_file"))
        if path:
            edit.setText(path)

    btn.clicked.connect(choose)
    layout.addWidget(lab)
    layout.addWidget(edit, 1)
    layout.addWidget(btn)
    return w, edit


def checkbox_row(label: str):
    box = QCheckBox(label)
    return box


def group_box(title: str, widgets):
    gb = QGroupBox(title)
    layout = QVBoxLayout(gb)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(10)
    for w in widgets:
        layout.addWidget(w)
    return gb
