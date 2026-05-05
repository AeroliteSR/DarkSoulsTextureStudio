from PySide6.QtWidgets import (QWidget, QVBoxLayout, QCheckBox, QDialog, QLabel, QPushButton, QMessageBox, QLineEdit, QComboBox, QInputDialog)
from PySide6.QtCore import Signal
from PySide6.QtGui import QPalette, QColor
from .GameInfo import Types
from .Enums import Game

class Palettes():
    dark = QPalette()
    dark.setColor(QPalette.Window, QColor("#1E1E1E"))
    dark.setColor(QPalette.Base, QColor("#2D2D2D"))
    dark.setColor(QPalette.WindowText, QColor("#ffffff"))
    dark.setColor(QPalette.Text, QColor("#ffffff"))
    dark.setColor(QPalette.ButtonText, QColor("#FFFFFF"))
    dark.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#A7A7A7"))
    dark.setColor(QPalette.Disabled, QPalette.Text, QColor("#A7A7A7"))
    dark.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#444444"))

def showError(text, title="Error", _type=QMessageBox.Critical):
    """Error popup with specified text"""
    msg = QMessageBox()
    msg.setIcon(_type)
    msg.setWindowTitle(title) 
    msg.setText(text) 
    msg.exec()

def showQuery(title, text):
    return QMessageBox.question(None, title, text, QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)

def gameTypeDialog() -> Game:
    options = ["Demon's Souls", "Dark Souls 1", "Dark Souls 2", "Dark Souls 3", "Bloodborne", "Sekiro", "Elden Ring", "Nightreign"]
    choice, ok = QInputDialog.getItem(None, "Select Game Type", "Choose one of the following:", options, 0, False)

    if choice and ok:
        return Game(choice)
    return None

class SearchWindow(QWidget):
    results = Signal(str, bool) # text, atlas search mode

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Search")
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Search text:"))
        self.search_input = QLineEdit()

        self.atlas_search = QCheckBox("Search Atlases")

        flags_layout = QVBoxLayout()
        flags_layout.addWidget(self.atlas_search)

        self.search_button = QPushButton("Search")
        layout.addWidget(self.search_input)
        layout.addLayout(flags_layout)
        layout.addWidget(self.search_button)

        self.setLayout(layout)
        self.search_button.clicked.connect(self.emit_search)

    def emit_search(self):
        text = self.search_input.text()
        self.results.emit(text, self.atlas_search.isChecked())

class TextureNamePrompt(QDialog):
    def __init__(self, halfprompt=True):
        super().__init__()
        self.halfprompt = halfprompt
        self.setWindowTitle("Prompt")

        layout = QVBoxLayout()

        layout.addWidget(QLabel("Prefix:"))
        self.prefix_input = QComboBox()
        self.prefix_input.addItems(Types.SubtexturePrefix)
        self.prefix_input.setEditable(True)
        layout.addWidget(self.prefix_input)

        layout.addWidget(QLabel("Icon ID:"))
        self.id_input = QLineEdit()
        layout.addWidget(self.id_input)

        if self.halfprompt:
            self.half_checkbox = QCheckBox("Half")
            layout.addWidget(self.half_checkbox)

        self.submit_button = QPushButton("Submit")
        layout.addWidget(self.submit_button)

        self.setLayout(layout)

        self.submit_button.clicked.connect(self.accept)

    def get_result(self):
        if self.halfprompt:
            half = self.half_checkbox.isChecked()
        else:
            half = False

        id = self.id_input.text()
        if not id.isdigit() or not 0 <= int(id) < 65536:
            showError(None, "Inputted ID is not an asserted UInt16.\nThis may silently throw errors in Smithbox or elsewhere.\nRename this icon if that wasn't your intention.", "Warning", QMessageBox.Warning)
        return f"{self.prefix_input.currentText()}_{id}", half
