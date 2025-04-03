import cv2
import os

from qtpy.QtCore import QThread, QObject, QTimer, Qt, Signal, Slot
from PyQt5.QtCore import pyqtSignal

# Worker to convert a file to AVI.

class QtWorkerC2A(QObject):

    file_ready = pyqtSignal(str)

    def __init__(self, in_path, out_path):
        super().__init__()
        self.in_path   = in_path
        self.out_path  = out_path
        print(f"Converting {self.in_path} to AVI...")
        print(f"The file will be written at: {self.out_path}")

    def convert_to_avi(self):
        if os.path.isfile(self.out_path):
            print(f"File {self.out_path} already exists.")
            return
        
        cap = cv2.VideoCapture(self.in_path)
        if not cap.isOpened():
            return

        width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps    = cap.get(cv2.CAP_PROP_FPS)
        codec  = 'MJPG'

        fourcc = cv2.VideoWriter_fourcc(*codec)
        out = cv2.VideoWriter(self.out_path, fourcc, fps, (width, height))
        i = 0
        n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            if i % 100 == 0:
                print(f"{(i/n_frames)*100:.2f}%")
            i += 1
            out.write(frame)

        cap.release()
        out.release()

    def run(self):
        if not os.path.isfile(self.out_path):
            self.convert_to_avi()
        self.file_ready.emit(self.out_path)
