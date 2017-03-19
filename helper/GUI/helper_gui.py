import sys
import queue
import threading
from PyQt5 import QtGui, QtWidgets
from PyQt5.QtCore import QObject, pyqtSignal

import helper as _helper
import helper.main as _main
import helper.GUI.qdarkstyle as qtdark
from helper.GUI.main_window import Ui_MainWindow as main_win
from helper.GUI.device_tab import Ui_Form as device_tab


class StdoutContainer(QObject):
    updated = pyqtSignal()

    def __init__(self, container=None):
        QObject.__init__(self)

        if not container:
            container = queue.Queue()
        self.container = container


    def write(self, item):
        self.container.put(item, False)
        self.updated.emit()


    def read(self):
        return self.container.get(False)


class DeviceTab(QtWidgets.QFrame):
    def __init__(self, device):
        super(QtWidgets.QFrame, self).__init__()
        self.ui = device_tab()
        self.ui.setupUi(self)

        self.device = device
        self.stdout_container = StdoutContainer()


        self.ui.traces_button.clicked.connect(self.pull_traces)
        self.stdout_container.updated.connect(self.write_to_console)

    def pull_traces(self):
        self.stdout_container.write(_main.pull_traces(self.device))

    def write_to_console(self):
        text = self.stdout_container.read()
        self.ui.device_console.insertPlainText(text)




class MainWin(QtWidgets.QMainWindow):
    def __init__(self):
        super(QtWidgets.QMainWindow, self).__init__()

        self.GUI_devices = {}
        self.ui = main_win()
        self.ui.setupUi(self)

        self.ui.refresh_device_status.clicked.connect(self.scan_devices)


    def scan_devices(self):
        print("Scanning for devices")
        connected_devices = _main.get_devices()

        for device in connected_devices:
            if not device in self.GUI_devices:
                self.GUI_devices[device] = self.add_device_tab(device)

            else:
                self.GUI_devices[device].setEnabled(True)


    def add_device_tab(self, device):
        print("New device found, adding new tab")

        tab_name = device.info["Product"]["Model"] + " -- "
        tab_name += device.info["Product"]["Manufacturer"]
        new_tab = DeviceTab(device)

        print("Device:", tab_name)

        self.ui.device_container.addTab(new_tab, tab_name)

        return new_tab


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWin()

    app.setStyleSheet(qtdark.load_stylesheet())

    window.show()
    sys.exit(app.exec_())

