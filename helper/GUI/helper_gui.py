"""Everything in this module is very experimental. I'm still
very much learning PyQt5, and this is my first project that uses threading in
a major way. This might get interesting. Consider yourself warned.

Here be dragons
"""

import sys
import queue
import threading
from time import sleep

from PyQt5 import QtWidgets, QtCore

import helper as helper_
import helper.main as main_
import helper.GUI.qdarkstyle as qtdark
from helper.GUI.main_window import Ui_MainWindow as MainWindow_
from helper.GUI.device_tab import Ui_Form as DeviceTab_


class StdoutContainer(QtCore.QObject):
    updated = QtCore.pyqtSignal()

    def __init__(self, container=None):
        QtCore.QObject.__init__(self)

        if not container:
            container = queue.Queue()
        self.container = container


    def write(self, item):
        self.container.put(item, False)
        self.updated.emit()


    def read(self):
        return self.container.get(False)


class DeviceTab(QtWidgets.QFrame):
    recording_started = QtCore.pyqtSignal()
    recording_ended = QtCore.pyqtSignal()
    traces_pulled = QtCore.pyqtSignal()
    cleaning_ready = QtCore.pyqtSignal(dict)
    cleaning_started = QtCore.pyqtSignal()
    cleaning_ended = QtCore.pyqtSignal()

    def __init__(self, device):
        super(QtWidgets.QFrame, self).__init__()
        self.ui = DeviceTab_()
        self.ui.setupUi(self)
        self.setAcceptDrops(True)
        self.device = device

        self.last_console_line = ""
        self.stdout_container = StdoutContainer()
        self.stdout_container.updated.connect(self.write_to_console)
        self.ui.device_console.setWordWrapMode(3) # set word wrap to "anywhere"

        self.ui.traces_button.clicked.connect(self.pull_traces)

        # Installing
        self.ui.install_button.clicked.connect(self.install)

        # Cleaning
        self.ui.clean_button.clicked.connect(self.clean)
        self.cleaning_ready.connect(self._clean_confirm)
        self.cleaning_ended.connect(
            lambda: self.ui.clean_button.setEnabled(True))
        self.traces_pulled.connect(
            lambda: self.ui.traces_button.setEnabled(True))

        self.write_device_info()

        # TODO: Figure out recording functionality

    def dragEnterEvent(self, drop):
        mimedata = drop.mimeData()

        if mimedata.hasUrls():
            drop.accept()
        else:
            drop.ignore()


    def dropEvent(self, drop):
        mimedata = drop.mimeData()
        paths = [x.toLocalFile() for x in mimedata.urls()]
        self.stdout_container.write("Installation triggered through drag&drop")
        self.install(*paths)


    def write_device_info(self):
        text = self.device.get_full_info_string()
        print([text])
        self.ui.device_info.append(text)


    def _install(self, *args):
        print("aaaaaaA")
        print(*args)
        main_.install(self.device, *args, stdout_=self.stdout_container)

    def install(self, *args):
        threading.Thread(target=self._install,
                         args=(args)).start()


    def _pull_traces(self):
        result = main_.pull_traces(self.device)
        if result:
            text = "Traces saved to" + main_.pull_traces(self.device)
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
        config = main_.parse_cleaner_config()
        parsed_config = config[0]
        bad_config = config[1]
        del config

        if bad_config:
            self.stdout_container.write("Bad config encountered:")
            self.stdout_container.write(bad_config)
            self.stdout_container.write("Cleaning aborted!")
            self.cleaning_ended.emit()
        elif not parsed_config:
            print("Config empty")
            self.stdout_container.write("Cannot clean - config is empty")
            self.cleaning_ended.emit()
        else:
            print("config parsed ok")
            self.cleaning_ready.emit(parsed_config)


    def _clean_confirm(self, parsed_config):
        print("confirming cleaning")
        self.cleaning_ended.emit()


    def _clean_proper(self, parsed_config):
        pass


    def clean(self):
        self.ui.clean_button.setEnabled(False)
        threading.Thread(target=self._clean_prepare).start()

        # TODO: Show a popup for picking the config
        # continue based on the user choice

    def remove_last_line(self):
        self.ui.device_console.moveCursor(11)
        self.ui.device_console.moveCursor(4, 1)
        self.ui.device_console.textCursor().removeSelectedText()
        self.ui.device_console.moveCursor(11)

    def write_to_console(self):
        text = self.stdout_container.read().rstrip("\n")
        # spam prevention
        if text == self.last_console_line:
            return False

        self.last_console_line = text
        print("Device tab console log:", [text])
        self.ui.device_console.append(text)
        self.ui.device_console.moveCursor(11) # move to the end of document
        self.ui.device_display.setCurrentIndex(1) # switch to console


class MainWin(QtWidgets.QMainWindow):
    new_device_found = QtCore.pyqtSignal(main_.Device)
    device_connected = QtCore.pyqtSignal(main_.Device)
    device_disconnected = QtCore.pyqtSignal(main_.Device)


    def __init__(self):
        super(QtWidgets.QMainWindow, self).__init__()

        self.gui_devices = {}
        self.ui = MainWindow_()
        self.ui.setupUi(self)
        self.stdout_container = StdoutContainer()
        self.stdout_container.updated.connect(self.write_to_console)
        self.ui.status_console.setWordWrapMode(3) # set word wrap to "anywhere"
        self.last_console_line = ""

        # setup device discovery
        self.device_timer = QtCore.QTimer()
        self.device_timer.setSingleShot(False)
        self.device_timer.setInterval(1500)
        self.device_timer.timeout.connect(self.scan_devices)
        self.device_timer.start()
        self.ui.refresh_device_status.clicked.connect(self.scan_devices)
        self.ui.refresh_device_status.clicked.connect(self.device_timer.start)
        self.new_device_found.connect(self.add_new_device)
        self.device_connected.connect(self.show_device_tab)
        self.device_disconnected.connect(self.hide_device_tab)

        self.scan_devices()


    def _scan_devices(self):
        self.ui.refresh_device_status.setEnabled(False)
        connected_devices = main_.get_devices(stdout_=self.stdout_container)

        for device in self.gui_devices:
            tab = self.gui_devices[device]["tab"]

            if device in connected_devices:
                if self.ui.device_container.indexOf(tab) < 0:
                    self.device_connected.emit(device)
                connected_devices.remove(device)
            elif self.ui.device_container.indexOf(tab) >= 0:
                self.device_disconnected.emit(device)

        for device in connected_devices:
            self.new_device_found.emit(device)

        self.ui.refresh_device_status.setEnabled(True)


    def scan_devices(self):
        # TODO: send feedback when scanning manually
        threading.Thread(target=self._scan_devices).start()


    def add_new_device(self, device):
        tab_name = device.info["Product"]["Model"] + " -- "
        tab_name += device.info["Product"]["Manufacturer"]
        self.stdout_container.write(" ".join(["Initializing connection with",
                                              tab_name]))
        print(tab_name, "found, adding new tab")

        new_tab = DeviceTab(device)
        self.gui_devices[device] = {"tab":new_tab, "name":tab_name}
        self.device_connected.emit(device)


    def hide_device_tab(self, device):
        device_tab = self.gui_devices[device]["tab"]
        tab_name = self.gui_devices[device]["name"]
        self.stdout_container.write(" ".join(["Lost connection with",
                                              tab_name]))
        print(tab_name, "disconnected, hiding its tab")

        device_tab_index = self.ui.device_container.indexOf(device_tab)
        if device_tab_index >= 0:
            self.ui.device_container.removeTab(device_tab_index)
        if self.ui.device_container.count() == 0:
            self.ui.device_container.addTab(self.ui.empty_tab, "No devices")


    def show_device_tab(self, device):
        device_tab = self.gui_devices[device]["tab"]
        tab_name = self.gui_devices[device]["name"]
        self.stdout_container.write(" ".join(["Successfully connected with",
                                              tab_name]))
        print(tab_name, "connected, showing its tab")

        self.ui.device_container.addTab(device_tab, tab_name)
        self.ui.device_container.setCurrentWidget(device_tab)

        empty_tab_index = self.ui.device_container.indexOf(self.ui.empty_tab)
        if empty_tab_index >= 0:
            self.ui.device_container.removeTab(empty_tab_index)


    def write_to_console(self):
        blacklist = [
            'ERROR: No devices found! Check USB connection and try again.'
            ]
        text = self.stdout_container.read().rstrip("\n")

        # spam prevention
        if text in blacklist:
            return False
        if text == self.last_console_line:
            return False

        self.last_console_line = text
        print("Main window console log:", [text])
        self.ui.status_console.append(text)
        self.ui.status_console.moveCursor(11) # move to the end of document


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWin()

    app.setStyleSheet(qtdark.load_stylesheet())

    window.show()
    sys.exit(app.exec_())
