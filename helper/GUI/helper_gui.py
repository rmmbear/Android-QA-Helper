"""Everything in this module is very experimental. I'm still
very much learning PyQt5, and this is my first project that uses threading in
a major way. This might get interesting. Consider yourself warned.

Here be dragons
"""

import sys
import queue
import threading
from time import sleep
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
    recording_started = pyqtSignal()
    recording_stopped = pyqtSignal()
    traces_pulled = pyqtSignal()
    cleaning_ready = pyqtSignal(dict)
    cleaning_started = pyqtSignal()
    cleaning_stopped = pyqtSignal()

    def __init__(self, device):
        super(QtWidgets.QFrame, self).__init__()
        self.ui = device_tab()
        self.ui.setupUi(self)

        self.device = device
        self.stdout_container = StdoutContainer()

        # set word wrap to "anywhere"
        self.ui.device_console.setWordWrapMode(3)

        self.ui.traces_button.clicked.connect(self.pull_traces)
        self.ui.clean_button.clicked.connect(self.clean)
        self.stdout_container.updated.connect(self.write_to_console)

        self.cleaning_ready.connect(self._clean_confirm)
        self.cleaning_stopped.connect(lambda: self.ui.clean_button.setEnabled(True))
        self.traces_pulled.connect(lambda: self.ui.traces_button.setEnabled(True))

        self.write_device_info()

    def write_device_info(self):
        text = self.device.get_full_info_string()
        print([text])
        self.ui.device_info.append(text)


    def _pull_traces(self):
        result = _main.pull_traces(self.device)
        if result:
            text = "Traces saved to" + _main.pull_traces(self.device)
        else:
            text = "Traces could not be saved"


        self.stdout_container.write(text)
        sleep(1) # let's not pull those logs too often :V
        self.traces_pulled.emit()

    def pull_traces(self):
        print("Pulling traces")
        self.ui.traces_button.setEnabled(False)
        threading.Thread(target=self._pull_traces).start()


    def _clean_prepare(self):
        config = _main.parse_cleaner_config(_stdout=self.stdout_container)
        parsed_config = config[0]
        bad_config = config[1]
        del config

        if bad_config:
            self.stdout_container.write("Bad config encountered:")
            self.stdout_container.write(bad_config)
            self.stdout_container.write("Cleaning aborted!")
            self.cleaning_stopped.emit()
        elif not parsed_config:
            print("Config empty")
            self.stdout_container.write("Cannot clean - config is empty")
            self.cleaning_stopped.emit()
        else:
            print("config parsed ok")
            self.cleaning_ready.emit(parsed_config)


    def _clean_confirm(self, parsed_config):
        print("confirming cleaning")
        self.cleaning_stopped.emit()


    def _clean_proper(self, parsed_config):
        pass


    def clean(self):
        self.ui.clean_button.setEnabled(False)
        threading.Thread(target=self._clean_prepare).start()

        # Show a popup for picking the config
        # continue based on the user choice


    def write_to_console(self):
        text = self.stdout_container.read().rstrip("\n")
        print([text])
        self.ui.device_console.append(text)
        self.ui.device_console.moveCursor(11) # move to the end of document
        self.ui.device_display.setCurrentIndex(1) # switch to console


class MainWin(QtWidgets.QMainWindow):
    new_device_detected = pyqtSignal(_main.Device)

    def __init__(self):
        super(QtWidgets.QMainWindow, self).__init__()

        self.GUI_devices = {}
        self.ui = main_win()
        self.ui.setupUi(self)
        self.stdout_container = StdoutContainer()

        self.stdout_container.updated.connect(self.write_to_console)

        self.ui.refresh_device_status.clicked.connect(self.scan_devices)
        self.new_device_detected.connect(self.add_device_tab)


    def _scan_devices(self):
        print("Scanning for devices")
        self.ui.refresh_device_status.setEnabled(False)
        connected_devices = _main.get_devices(_stdout=self.stdout_container)
        for device in connected_devices:
            if not device in self.GUI_devices:
                print(self.GUI_devices)
                self.new_device_detected.emit(device)

            else:
                self.GUI_devices[device].setEnabled(True)

        self.ui.refresh_device_status.setEnabled(True)


    def scan_devices(self):
        threading.Thread(target=self._scan_devices).start()


    def add_device_tab(self, device):
        print("New device found, adding new tab")

        tab_name = device.info["Product"]["Model"] + " -- "
        tab_name += device.info["Product"]["Manufacturer"]
        new_tab = DeviceTab(device)

        print("Device:", tab_name)

        self.ui.device_container.addTab(new_tab, tab_name)
        self.ui.device_container.setCurrentWidget(new_tab)

        self.GUI_devices[device] = new_tab
        empty_tab_index = self.ui.device_container.indexOf(self.ui.empty_tab)
        if empty_tab_index >= 0:
            self.ui.device_container.removeTab(empty_tab_index)


    def write_to_console(self):
        text = self.stdout_container.read().rstrip("\n")
        print([text])
        self.ui.status_console.append(text)
        self.ui.status_console.moveCursor(11) # move to the end of document


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWin()

    app.setStyleSheet(qtdark.load_stylesheet())

    window.show()
    sys.exit(app.exec_())

