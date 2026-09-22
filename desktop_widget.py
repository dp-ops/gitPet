import sys
import threading
import msvcrt
from PyQt6.QtCore import Qt, QTimer, QPoint, QSettings, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QProgressBar, QPushButton, QFrame, QMenu
)
from PyQt6.QtGui import QAction, QKeyEvent
import psutil

class TerminalListener(QObject):
    quit_signal = pyqtSignal()

    def start(self):
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self):
        print("Terminal listener active: Press 'q' in this terminal to close the widget.")
        while True:
            char = msvcrt.getch().decode('utf-8', errors='ignore').lower()
            if char == 'q':
                print("\n'q' received. Shutting down...")
                self.quit_signal.emit()
                break

class DesktopMonitorWidget(QWidget):
    def __init__(self):
        super().__init__()

        # --- 1. Desktop Pinning & Window Flags ---
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnBottomHint |  # Sits behind all normal apps
            Qt.WindowType.SubWindow                 # Merges into desktop layer
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        self.setFixedSize(260, 160)
        self._drag_pos = QPoint()

        # --- 2. Persistent Settings (Coordinates & Lock State) ---
        # Stored automatically in Windows Registry under:
        # HKEY_CURRENT_USER\Software\DesktopMonitor\Settings
        self.settings = QSettings("DesktopMonitor", "Settings")
        self.is_locked = self.settings.value("locked", False, type=bool)

        self._restore_position()
        self._init_ui()

        # Update metrics every 1 second
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_metrics)
        self.timer.start(1000)

    def _restore_position(self):
        # Default to (100, 100) if no prior coordinates exist
        saved_pos = self.settings.value("pos", QPoint(100, 100))
        self.move(saved_pos)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 14)
        card_layout.setSpacing(10)

        # Header
        header_layout = QHBoxLayout()
        title_label = QLabel("SYSTEM MONITOR")
        title_label.setObjectName("title")

        close_btn = QPushButton("✕")
        close_btn.setObjectName("close_btn")
        close_btn.setFixedSize(18, 18)
        close_btn.clicked.connect(self.close)

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(close_btn)
        card_layout.addLayout(header_layout)

        # CPU Row
        cpu_header = QHBoxLayout()
        cpu_title = QLabel("CPU")
        self.cpu_val = QLabel("0%")
        cpu_title.setObjectName("metric_label")
        self.cpu_val.setObjectName("metric_val")
        cpu_header.addWidget(cpu_title)
        cpu_header.addStretch()
        cpu_header.addWidget(self.cpu_val)
        card_layout.addLayout(cpu_header)

        self.cpu_bar = QProgressBar()
        self.cpu_bar.setObjectName("cpu_bar")
        self.cpu_bar.setTextVisible(False)
        self.cpu_bar.setRange(0, 100)
        card_layout.addWidget(self.cpu_bar)

        # RAM Row
        ram_header = QHBoxLayout()
        ram_title = QLabel("RAM")
        self.ram_val = QLabel("0%")
        ram_title.setObjectName("metric_label")
        self.ram_val.setObjectName("metric_val")
        ram_header.addWidget(ram_title)
        ram_header.addStretch()
        ram_header.addWidget(self.ram_val)
        card_layout.addLayout(ram_header)

        self.ram_bar = QProgressBar()
        self.ram_bar.setObjectName("ram_bar")
        self.ram_bar.setTextVisible(False)
        self.ram_bar.setRange(0, 100)
        card_layout.addWidget(self.ram_bar)

        main_layout.addWidget(card)

        self.setStyleSheet("""
            #card {
                background-color: rgba(23, 23, 23, 210);
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 12px;
            }
            #title {
                color: #9ca3af;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1px;
            }
            #close_btn {
                background: transparent;
                color: #6b7280;
                border: none;
                font-size: 11px;
                font-weight: bold;
            }
            #close_btn:hover {
                color: #ef4444;
            }
            #metric_label, #metric_val {
                color: #f3f4f6;
                font-size: 11px;
                font-weight: 600;
            }
            QProgressBar {
                background-color: rgba(255, 255, 255, 20);
                border: none;
                border-radius: 4px;
                height: 6px;
            }
            #cpu_bar::chunk {
                background-color: #3b82f6;
                border-radius: 4px;
            }
            #ram_bar::chunk {
                background-color: #10b981;
                border-radius: 4px;
            }
        """)

    def update_metrics(self):
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
        self.cpu_bar.setValue(int(cpu))
        self.cpu_val.setText(f"{cpu:.1f}%")
        self.ram_bar.setValue(int(ram))
        self.ram_val.setText(f"{ram:.1f}%")

    # --- Mouse Dragging & Persistent Coordinate Saving ---
    def mousePressEvent(self, event):
        if not self.is_locked and event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if not self.is_locked and event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self._drag_pos
            self.move(new_pos)
            self.settings.setValue("pos", new_pos)  # Instantly store coordinates
            event.accept()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    # --- Context Menu with Position Locking ---
    def show_context_menu(self, position):
        menu = QMenu(self)

        # Toggleable Lock Action
        lock_action = QAction("Lock Position", self)
        lock_action.setCheckable(True)
        lock_action.setChecked(self.is_locked)
        lock_action.triggered.connect(self.toggle_lock)
        menu.addAction(lock_action)

        menu.addSeparator()

        close_action = QAction("Exit Monitor", self)
        close_action.triggered.connect(self.close)
        menu.addAction(close_action)

        menu.exec(self.mapToGlobal(position))

    def toggle_lock(self, checked):
        self.is_locked = checked
        self.settings.setValue("locked", self.is_locked)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = DesktopMonitorWidget()
    widget.show()

    # Start background listener for 'q'
    listener = TerminalListener()
    listener.quit_signal.connect(app.quit)
    listener.start()

    sys.exit(app.exec())