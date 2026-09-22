import sys
import os
import threading
import msvcrt
from PyQt6.QtCore import Qt, QTimer, QPoint, QSettings, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QFrame, QMenu
)
from PyQt6.QtGui import QAction, QKeyEvent, QPixmap
import psutil

class TerminalListener(QObject):
    quit_signal = pyqtSignal()
    def start(self):
        threading.Thread(target=self._run, daemon=True).start()
    def _run(self):
        print("Press 'q' in this terminal to close the widget.")
        while True:
            if msvcrt.getch().decode('utf-8', errors='ignore').lower() == 'q':
                self.quit_signal.emit()
                break

class DesktopMonitorWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnBottomHint |
            Qt.WindowType.SubWindow
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        # Make the widget taller and narrower to focus on the image
        self.setFixedSize(220, 260)
        self._drag_pos = QPoint()

        self.settings = QSettings("DesktopMonitor", "Settings")
        self.is_locked = self.settings.value("locked", False, type=bool)

        # --- Image Animation Logic State ---
        self.low_images = ["png/Sleepping/pose_1.png", "png/Sleepping/pose_2.png", "png/Sleepping/pose_4.png"]
        self.high_image = "png/other/pose_3.png"
        self.current_frame = 0
        self.is_high_load = False

        self._restore_position()
        self._init_ui()

        # Timer 1: Hardware Metrics (every 1 second)
        self.metric_timer = QTimer(self)
        self.metric_timer.timeout.connect(self.update_metrics)
        self.metric_timer.start(1000)

        # Timer 2: Image Rotation (every 1.5 seconds)
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.rotate_image)
        self.anim_timer.start(1500)

        # Force initial image load
        self.update_image_display()

    def _restore_position(self):
        saved_pos = self.settings.value("pos", QPoint(100, 100))
        self.move(saved_pos)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(8)

        # Header (Close Button Only)
        header_layout = QHBoxLayout()
        header_layout.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setObjectName("close_btn")
        close_btn.setFixedSize(18, 18)
        close_btn.clicked.connect(self.close)
        header_layout.addWidget(close_btn)
        card_layout.addLayout(header_layout)

        # Central Image Viewer
        self.image_label = QLabel("No Image")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setObjectName("image_label")
        card_layout.addWidget(self.image_label, stretch=1)

        # Minimal Footer Metrics
        metrics_layout = QHBoxLayout()
        self.cpu_val = QLabel("CPU: --%")
        self.ram_val = QLabel("RAM: --%")
        self.cpu_val.setObjectName("metric_val")
        self.ram_val.setObjectName("metric_val")
        
        metrics_layout.addWidget(self.cpu_val)
        metrics_layout.addStretch()
        metrics_layout.addWidget(self.ram_val)
        card_layout.addLayout(metrics_layout)

        main_layout.addWidget(card)

        self.setStyleSheet("""
            #card {
                background-color: rgba(23, 23, 23, 210);
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 12px;
            }
            #close_btn {
                background: transparent; color: #6b7280; border: none; font-size: 11px; font-weight: bold;
            }
            #close_btn:hover { color: #ef4444; }
            #image_label {
                background-color: rgba(0, 0, 0, 40);
                border-radius: 8px;
                color: #6b7280;
            }
            #metric_val {
                color: #9ca3af; font-size: 11px; font-weight: 600;
            }
        """)

    def update_metrics(self):
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
        
        self.cpu_val.setText(f"CPU: {cpu:.0f}%")
        self.ram_val.setText(f"RAM: {ram:.0f}%")

        # Determine state
        if cpu >= 30.0 and not self.is_high_load:
            self.is_high_load = True
            self.update_image_display()
        elif cpu < 30.0 and self.is_high_load:
            self.is_high_load = False
            self.current_frame = 0
            self.update_image_display()

    def rotate_image(self):
        # Only rotate if we are in the low load state
        if not self.is_high_load:
            self.current_frame = (self.current_frame + 1) % len(self.low_images)
            self.update_image_display()

    # def update_image_display(self):
    #     image_name = self.high_image if self.is_high_load else self.low_images[self.current_frame]
        
    #     # Load and scale the image to fit the container while maintaining aspect ratio
    #     if os.path.exists(image_name):
    #         pixmap = QPixmap(image_name)
    #         # Scale to fit exactly within 180x180 pixels maximum
    #         scaled_pixmap = pixmap.scaled(
    #             180, 180, 
    #             Qt.AspectRatioMode.KeepAspectRatio, 
    #             Qt.TransformationMode.SmoothTransformation
    #         )
    #         self.image_label.setPixmap(scaled_pixmap)
    #     else:
    #         self.image_label.setText(f"Missing\n{image_name}")

    def update_image_display(self):
        # 1. Get the relative image name based on CPU state
        image_name = self.high_image if self.is_high_load else self.low_images[self.current_frame]
        
        # 2. Get the absolute path to the directory where this script lives
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 3. Combine them to get the absolute path to the image
        full_image_path = os.path.join(script_dir, image_name)
        
        # 4. Load and scale the image using the absolute path
        if os.path.exists(full_image_path):
            pixmap = QPixmap(full_image_path)
            scaled_pixmap = pixmap.scaled(
                180, 180, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
        else:
            self.image_label.setText(f"Missing\n{image_name}")

    # --- Mouse Dragging & Context Menu ---
    def mousePressEvent(self, event):
        if not self.is_locked and event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if not self.is_locked and event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self._drag_pos
            self.move(new_pos)
            self.settings.setValue("pos", new_pos)
            event.accept()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    def show_context_menu(self, position):
        menu = QMenu(self)
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

    listener = TerminalListener()
    listener.quit_signal.connect(app.quit)
    listener.start()

    sys.exit(app.exec())