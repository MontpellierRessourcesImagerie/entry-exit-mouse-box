from qtpy.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QApplication, QMainWindow,
                            QTableWidget, QTableWidgetItem, QFileDialog)
from PyQt5.QtGui import QColor, QFont
import numpy as np
import csv
import math

class ResultsTable(QMainWindow):
    def __init__(self, data, name='Data Table', parent=None):
        super(ResultsTable, self).__init__(parent)
        self.exp_name = "untitled.csv"
        self.setWindowTitle(name)
        self.font = QFont()
        self.font.setFamily("Arial Unicode MS, Segoe UI Emoji, Apple Color Emoji, Noto Color Emoji")
        self.init_ui()
        self.set_data(data)

    def init_ui(self):
        # Central widget
        self.centralWidget = QWidget(self)
        self.setCentralWidget(self.centralWidget)

        # Layout
        self.layout = QVBoxLayout(self.centralWidget)

        # Table
        self.table = QTableWidget()
        self.layout.addWidget(self.table)  # Add table to layout

        # Export Button
        self.exportButton = QPushButton('💾 Save as CSV')
        self.exportButton.setFont(self.font)
        self.exportButton.clicked.connect(self.export_data)
        self.layout.addWidget(self.exportButton)

    def set_data(self, data):
        # Assume we have some data structure holding CSV-like data
        columnHeaders = ['Column 1', 'Column 2', 'Column 3']
        rowHeaders = ['Row 1', 'Row 2']
        rowData = [['Row1-Col1', 'Row1-Col2', 'Row1-Col3'],
                   ['Row2-Col1', 'Row2-Col2', 'Row2-Col3']]

        self.table.setColumnCount(len(columnHeaders))
        self.table.setRowCount(len(rowData))
        self.table.setHorizontalHeaderLabels(columnHeaders)
        self.table.setVerticalHeaderLabels(rowHeaders)

        for row, data in enumerate(rowData):
            for column, value in enumerate(data):
                item = QTableWidgetItem(value)
                # Set background color for the cell
                item.setBackground(QColor(255, 255, 200))  # Light yellow background
                self.table.setItem(row, column, item)

    def set_exp_name(self, name):
        self.exp_name = ".".join(name.replace(" ", "-").split('.')[:-1]) + ".csv"

    def export_data(self):
        options = QFileDialog.Options()
        try:
            fileName, _ = QFileDialog.getSaveFileName(
                self, 
                "QFileDialog.getSaveFileName()", 
                self.exp_name,
                "CSV Files (*.csv);;All Files (*)", 
                options=options
            )
        except:
            fileName = None

        if not fileName:
            print("No file selected")
            return
        
        self.export_table_to_csv(fileName)

    def export_table_to_csv(self, filename: str):
        # Open a file in write mode
        with open(filename, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file, delimiter=';')
            
            # Writing headers (optional)
            headers = [self.table.horizontalHeaderItem(i).text() if self.table.horizontalHeaderItem(i) is not None else "" for i in range(self.table.columnCount())]
            writer.writerow(headers)
            
            # Writing data
            for row in range(self.table.rowCount()):
                row_data = []
                for column in range(self.table.columnCount()):
                    item = self.table.item(row, column)
                    # Check if the cell is not empty
                    if item is not None:
                        row_data.append(item.text())
                    else:
                        row_data.append('')
                writer.writerow(row_data)


# ====> The first result table contains the visibility and the centroid.


class FrameWiseResultsTable(ResultsTable):
    def __init__(self, data, parent=None):
        name = "visibility+centroids"
        super(FrameWiseResultsTable, self).__init__(data, name, parent)
        self.init_ui()
        self.set_data(data)
        print("Centroid and visibility table created")

    def set_data(self, data):
        colors, centroids, visibility, box_names = data
        
        # Setting headers for each box.
        headers = ['Visibility', 'X', 'Y']
        nHeaders = len(headers)
        columnHeaders = []
        for name in box_names:
            for header in headers:
                columnHeaders.append(f'{header} ({name})')
        
        # Settings rows headers.
        rowHeaders = [str(i+1) for i in range(len(centroids))]
        
        self.table.setColumnCount(len(columnHeaders))
        self.table.setRowCount(len(rowHeaders))
        self.table.setHorizontalHeaderLabels(columnHeaders)
        self.table.setVerticalHeaderLabels(rowHeaders)

        # Filling the table.
        for frame in range(len(centroids)): # For each frame
            for box in range(len(box_names)):
                v_str = ""
                v = visibility[box][frame]
                if v < 0:
                    v_str = ""
                elif v == 0:
                    v_str = "Hidden"
                else:
                    v_str = "Visible"

                c = centroids[frame][box]

                color = QColor(colors[box][0], colors[box][1], colors[box][2], 100)
                item_v = QTableWidgetItem(v_str)
                item_x = QTableWidgetItem(str(round(c[0], 2)) if c[0] >= 0.0 else "")
                item_y = QTableWidgetItem(str(round(c[1], 2)) if c[0] >= 0.0 else "")
                item_v.setBackground(color)
                item_x.setBackground(color)
                item_y.setBackground(color)
                self.table.setItem(frame, box * nHeaders + 0, item_v)
                self.table.setItem(frame, box * nHeaders + 1, item_x)
                self.table.setItem(frame, box * nHeaders + 2, item_y)
        
        self.table.resizeColumnsToContents()


# ====> The second result table contains the session data (session time, session distance)


class SessionsResultsTable(ResultsTable):
    def __init__(self, data, parent=None):
        name = "sessions"
        super(SessionsResultsTable, self).__init__(data, name, parent)
        self.init_ui()
        self.set_data(data)
        print("Sessions table created")

    def set_data(self, data):
        colors_raw, sessions, box_names, visibility, unit, fps = data
        colors = [QColor(int(colors_raw[box_index][0]), int(colors_raw[box_index][1]), int(colors_raw[box_index][2]), 100) for box_index in range(len(box_names))]
        
        # Setting headers for each box.
        # Time start of the session, duration of the session, number of go in/go out for this box
        headers = ['Time start (s)', 'Time start (f)', 'Duration (s)', 'Duration (f)', f'Distance ({unit})']
        status  = ['V', 'H']
        last    = '#I/O'
        nHeaders = len(box_names) * len(headers) * len(status) + len(box_names)

        # Searching for the maximum number of sessions.
        max_count    = max([sessions[box]['count'] for box in sessions.keys()])
        max_sessions = int(1 + math.ceil(float(max_count) / 2.0))
        
        # Settings rows headers.
        rowHeaders = [" ", " "] + [str(i+1) for i in range(max_sessions)]
        
        self.table.setColumnCount(nHeaders)
        self.table.setRowCount(len(rowHeaders))
        self.table.setVerticalHeaderLabels(rowHeaders)

        # Filling the headers
        nBoxHeaders = len(headers) * len(status) + 1
        for box_index in range(len(box_names)):
            box_header = [box_names[box_index]] + [" " for i in range(nBoxHeaders-1)]
            color = colors[box_index]
            for i in range(nBoxHeaders):
                item = QTableWidgetItem(box_header[i])
                item.setBackground(color)
                self.table.setItem(0, nBoxHeaders * box_index + i, item)
            for s_i, s_t in enumerate(status):
                for h_i, h_t in enumerate(headers):
                    item = QTableWidgetItem(f"[{s_t}] {h_t}")
                    item.setBackground(color)
                    self.table.setItem(1, nBoxHeaders * box_index + s_i * len(headers) + h_i, item)
            item = QTableWidgetItem(last)
            item.setBackground(color)
            self.table.setItem(1, nBoxHeaders * box_index + nBoxHeaders - 1, item)

        last_pos_by_column = [2 for _ in range(len(box_names) * nBoxHeaders)]
        for box_idx in range(len(box_names)):
            s     = sessions[box_idx]['sessions']
            color = colors[box_idx]
            for session_idx, session in enumerate(s):
                start_frames     = int(session['start'])
                start_seconds    = round(start_frames / fps, 2)
                duration_frames  = int(session['duration'])
                duration_seconds = round(duration_frames / fps, 2)
                distance         = round(session['distance'], 2)
                visible          = session['status']
                shift            = 0 if visible > 0 else 1
                col_index        = nBoxHeaders * box_idx + shift * len(headers)

                item = QTableWidgetItem(str(start_seconds))
                item.setBackground(color)
                self.table.setItem(last_pos_by_column[col_index+0], col_index+0, item)

                item = QTableWidgetItem(str(start_frames))
                item.setBackground(color)
                self.table.setItem(last_pos_by_column[col_index+1], col_index+1, item)

                item = QTableWidgetItem(str(duration_seconds))
                item.setBackground(color)
                self.table.setItem(last_pos_by_column[col_index+2], col_index+2, item)

                item = QTableWidgetItem(str(duration_frames))
                item.setBackground(color)
                self.table.setItem(last_pos_by_column[col_index+3], col_index+3, item)

                item = QTableWidgetItem(str(distance))
                item.setBackground(color)
                self.table.setItem(last_pos_by_column[col_index+4], col_index+4, item)

                for i in range(5):
                    last_pos_by_column[col_index+i] += 1
        
        # Filling the last column with the number of go in/out.
        for box_idx in range(len(box_names)):
            color = colors[box_idx]
            item = QTableWidgetItem(str(sessions[box_idx]['count']))
            item.setBackground(color)
            self.table.setItem(2, nBoxHeaders * box_idx + nBoxHeaders - 1, item)

        self.table.resizeColumnsToContents()




def read_names(f_path):
    descr = open(f_path, "r")
    content = descr.read()
    descr.close()
    box_names = content.split(";")
    return box_names


def main_sessions():
    from time import sleep

    visibility   = np.load("/media/benedetti/5B0AAEC37149070F/mice-videos/2084-2086-2104-2106-T0.tmp//visibility.npy")
    sessions     = np.load("/home/benedetti/Documents/projects/25-entry-exit-mouse-monitor/tmp/sessions.npy")
    # centroids    = np.squeeze(np.load("/home/benedetti/Documents/projects/25-entry-exit-mouse-monitor/tmp/centroids.npy"))
    colors       = np.load("/home/benedetti/Documents/projects/25-entry-exit-mouse-monitor/tmp/colors.npy")
    box_names    = read_names("/home/benedetti/Documents/projects/25-entry-exit-mouse-monitor/tmp/box_names.txt")

    app = QApplication([])
    table = SessionsResultsTable((colors, sessions, box_names, visibility, "px"))
    table.set_exp_name("Nom de manip.mp4")
    table.show()
    app.exec_()

    print("DONE.")


if __name__ == '__main__':
    main_sessions()