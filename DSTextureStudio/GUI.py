from PySide6.QtWidgets import (QWidget, QVBoxLayout, QCheckBox, QDialog, QLabel, QPushButton, QMessageBox, QLineEdit, QComboBox, QDialogButtonBox)
from PySide6.QtCore import Signal
from PySide6.QtGui import QPalette, QColor
from .GameInfo import Types
from .Enums import Game

class Palettes():
    DARK_STYLESHEET = """
    QWidget {
        background-color: #1E1E1E;
        color: #FFFFFF;
    }

    QPushButton {
        background-color: #2D2D2D;
        color: #FFFFFF;
    }

    QPushButton:hover {
        background-color: #313131;
    }

    QPushButton:pressed {
        background-color: #2A2A2A;
    }

    QPushButton:disabled {
        color: #777777;
    }

    QListWidget {
        background-color: #2D2D2D;
        color: #FFFFFF;
        border: 1px solid #2D2D2D;
        border-radius: 6px;
    }

    QMenu {
        background-color: #0F0F0F;
        color: #FFFFFF;
        border: 1px solid #3A3A3A;
        border-radius: 6px;
    }

    QMenu::item {
        background-color: #0F0F0F;
        padding: 5px 30px 5px 10px; /* top right bottom left */
        border: 0px solid #3A3A3A;
        border-radius: 6px;
    }

    QMenu::item:selected {
        background-color: #1D1D1D;
        padding: 3px 30px 3px 10px; /* top right bottom left */
        border-radius: 6px;
    }

    QMenu::separator {
        height: 1px;
        background: #3A3A3A;
        margin: 5px 6px 5px 6px;
    }

    QSplitter::handle {
        background: #1E1E1E;
    } /* if i ever wana try get fusion to work */

    QCheckBox {
        color: #FFFFFF;
    }

    QComboBox {
        background-color: #2D2D2D;
        color: #FFFFFF;
        padding: 3px 0px 3px 0px; /* top right bottom left */
    }

    QMessageBox,
    QInputDialog {
        background-color: #1E1E1E;
        color: #FFFFFF;
    }

    QListWidget {
        background-color: #2D2D2D;
        color: #FFFFFF;
        border: none;
        outline: 0;
        font-family: "Segoe UI";
        font-size: 9pt;
        padding: 1px;
    }

    QListWidget::item {
        color: white;
        border: none;
        padding: 0px 8px 0px 8px; /* top right bottom left */
        border-radius: 4px;
    }

    QListWidget::item:selected {
        background: #393939;
        color: white;
        padding: 0px 10px 0px 10px; /* top right bottom left */

        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,

            stop:0      transparent,
            stop:0.015  #2AA8FF,
            stop:0.022  #2AA8FF,
            stop:0.023  transparent,
            stop:0.05   #3A3A3A,
            stop:1      #3A3A3A
        );

        border-radius: 4px;
        margin: 2px;
    }

    QListWidget::item:focus {
        outline: none;
        border-radius: 4px;

    }

    QListWidget QScrollBar:vertical {
        background: #2D2D2D;
        width: 6px;
        margin: 0px;
        padding: 5px 0px 5px 0px; /* top right bottom left */
        border-radius: 3px;
    }

    QListWidget QScrollBar::handle:vertical {
        background: #444444;
        border: 0px;
        border-radius: 3px;
        min-height: 50px;
    }

    QListWidget QScrollBar::handle:vertical:hover {
        background: #575757;
    }

    QListWidget QScrollBar::add-line:vertical,
    QListWidget QScrollBar::sub-line:vertical {
        height: 0px;
    }

    QListWidget QScrollBar::add-page:vertical,
    QListWidget QScrollBar::sub-page:vertical {
        background: none;
    }
    """

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
    options = [
        "Demon's Souls",
        "Dark Souls 1",
        "Dark Souls 2",
        "Dark Souls 3",
        "Bloodborne",
        "Sekiro",
        "Elden Ring",
        "Nightreign"
    ]

    dialog = QDialog(None)
    dialog.setWindowTitle("Select Game Type")
    dialog.setModal(True)

    layout = QVBoxLayout(dialog)

    label = QLabel("Choose one of the following:")
    combo = QComboBox()
    combo.setStyleSheet("""QComboBox {padding: 3px 0px 3px 6px;}""")
    combo.addItems(options)

    buttons = QDialogButtonBox(
        QDialogButtonBox.Ok | QDialogButtonBox.Cancel
    )

    layout.addWidget(label)
    layout.addWidget(combo)
    layout.addWidget(buttons)

    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)

    result = dialog.exec()

    if result == QDialog.Accepted:
        return Game(combo.currentText())

    return Game(None)

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
            showError("Inputted ID is not an asserted UInt16.\nThis may silently throw errors in Smithbox or elsewhere.\nRename this icon if that wasn't your intention.", "Warning", QMessageBox.Warning)
        return f"{self.prefix_input.currentText()}_{id}", half
