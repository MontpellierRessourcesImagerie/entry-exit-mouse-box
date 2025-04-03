import os
from qtpy.QtWidgets import (QWidget, QVBoxLayout, QLineEdit, QHBoxLayout,
                            QPushButton, QFileDialog, QLabel)
from qtpy.QtCore import QThread
import napari
from napari.utils import progress
from napari.utils.notifications import show_info
from entry_exit_mouse_box.convert_format import QtWorkerC2A


class VideoConverterWidget(QWidget):
    
    def __init__(self, napari_viewer: "napari.Viewer"):
        super().__init__()
        self.selected_folder = None
        self.viewer = napari_viewer
        self.current = 0
        self.files = None
        self.init_ui()

    def init_ui(self):

        self.btn_select_folder = QPushButton("Input folder", self)
        self.extension_field = QLineEdit(self)
        self.btn_start_conversion = QPushButton("Launch", self)
        self.btn_start_conversion.setEnabled(False)

        layout = QVBoxLayout()
        layout.addWidget(self.btn_select_folder)
        h_layout = QHBoxLayout()
        h_layout.addWidget(QLabel("Extension:"))
        h_layout.addWidget(self.extension_field)
        layout.addLayout(h_layout)

        layout.addSpacing(20)

        layout.addWidget(self.btn_start_conversion)
        self.setLayout(layout)

        self.btn_select_folder.clicked.connect(self.select_folder)
        self.btn_start_conversion.clicked.connect(self.start_conversion)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select a folder")
        if not folder:
            return
        self.selected_folder = folder
        self.btn_start_conversion.setEnabled(True)

    def start_conversion(self):
        if not self.selected_folder:
            return

        self.files = [os.path.join(self.selected_folder, f) for f in os.listdir(self.selected_folder) if f.endswith(self.extension_field.text())]
        if not self.files:
            show_info("No file found.")
            return
        
        self.launch_convert(self.files[self.current])

    def launch_convert(self, file_path):
        output_folder = os.path.join(
            os.path.dirname(file_path), 
            ".".join(os.path.basename(file_path).split(".")[:-1]) + ".tmp"
        )
        print("OUTPUT:", output_folder)
        os.makedirs(output_folder, exist_ok=True)
        self.set_active_ui(False)
        show_info("Converting video:" + file_path)
        self.pbr = progress(total=0)
        self.pbr.set_description("Converting video...")

        self.thread = QThread()
        self.c2a = QtWorkerC2A(file_path, os.path.join(output_folder, os.path.basename(file_path)))
        self.c2a.moveToThread(self.thread)
        self.c2a.file_ready.connect(self.done_a_file)
        self.thread.started.connect(self.c2a.run)
        self.thread.start()
    
    def done_a_file(self, _):
        print(f"Finished file {str(self.current+1).zfill(2)}/{str(len(self.files)).zfill(2)}")
        self.pbr.close()
        self.thread.quit()
        self.thread.wait()
        self.thread.deleteLater()
        self.thread = None
        self.set_active_ui(True)
        self.current += 1
        if self.current < len(self.files):
            self.launch_convert(self.files[self.current])
        else:
            show_info("All files converted")

    def set_active_ui(self, active):
        self.btn_select_folder.setEnabled(active)
        self.extension_field.setEnabled(active)
        self.btn_start_conversion.setEnabled(active)
