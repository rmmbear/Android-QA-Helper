"""Everything in this module is very experimental. I'm still
very much learning PyQt5, and this is my first project that uses threading in
a major way. This might get interesting. Consider yourself warned.

Here be dragons
"""
import re
import sys
import queue
import threading
from time import sleep, strftime

from PyQt5 import QtWidgets, QtCore

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
    recording_stopped = QtCore.pyqtSignal()
    recording_ended = QtCore.pyqtSignal()
    traces_pulled = QtCore.pyqtSignal()
    cleaning_ready = QtCore.pyqtSignal(dict)
    cleaning_started = QtCore.pyqtSignal()
    cleaning_ended = QtCore.pyqtSignal()
    connection_reset = QtCore.pyqtSignal()

    def __init__(self, device):
        super(QtWidgets.QFrame, self).__init__()
        self.ui = DeviceTab_()
        self.ui.setupUi(self)
        self.setAcceptDrops(True)
        self.device = device
        self.recording_job = None

        self.last_console_line = ""
        self.stdout_container = StdoutContainer()
        self.stdout_container.updated.connect(self.write_to_console)
        self.ui.device_console.setWordWrapMode(3) # set word wrap to "anywhere"

        # recording
        self.ui.record_button.clicked.connect(self.record)
        self.ui.record_button.clicked.connect(self.disable_buttons)
        self.recording_stopped.connect(self._copy_recording)

        # traces
        self.ui.traces_button.clicked.connect(self.pull_traces)

        # Installing
        self.ui.install_button.clicked.connect(self.install)

        # Cleaning
        self.ui.clean_button.clicked.connect(self.clean)
        self.cleaning_ready.connect(self._clean_confirm)
        self.cleaning_ended.connect(self.enable_buttons)
        self.traces_pulled.connect(self.enable_buttons)

        self.write_device_info()


    def dragEnterEvent(self, drop):
        mimedata = drop.mimeData()

        if mimedata.hasUrls() and self.ui.install_button.isEnabled():
            drop.accept()
        else:
            drop.ignore()


    def dropEvent(self, drop):
        mimedata = drop.mimeData()
        paths = [x.toLocalFile() for x in mimedata.urls()]
        self.stdout_container.write("Installation triggered through drag&drop")
        self.install(*paths)
        # TODO: Show a confirmation popup before drag & drop installation


    def write_device_info(self):
        text = self.device.get_full_info_string()
        print([text])
        self.ui.device_info.append(text)


    def enable_buttons(self):
        self.ui.install_button.setEnabled(True)
        self.ui.record_button.setEnabled(True)
        self.ui.traces_button.setEnabled(True)
        self.ui.clean_button.setEnabled(True)


    def disable_buttons(self):
        self.ui.install_button.setEnabled(False)
        self.ui.record_button.setEnabled(False)
        self.ui.traces_button.setEnabled(False)
        self.ui.clean_button.setEnabled(False)


    def _record(self, lock):
        recording_name = self.recording_job[1]
        record_ = threading.Thread(
            target=main_.record_start, args=(self.device, recording_name),
            kwargs={"stdout_":self.stdout_container}, daemon=True)
        record_.start()
        sleep(0.2) # wait before enabling buttons
        # TODO: let the thread know that everything is setup and buttons can be enabled
        self.ui.record_button.setEnabled(True)
        while not lock.acquire(False):
            if not record_.is_alive():
                # make sure the file is saved ()
                sleep(1)
                self.recording_stopped.emit()
                return False
            sleep(0.5)
        self.device.adb_command("reconnect")
        self.connection_reset.emit()
        self.recording_stopped.emit()


    def _copy_recording_(self):
        sleep(1)
        filename = self.recording_job[1]
        remote_recording = self.device.ext_storage + "/" + filename
        copied = main_.record_copy(self.device, remote_recording, "./",
                                   stdout_=self.stdout_container)
        if not copied:
            self.stdout_container.write("Could not copy recorded clip!")
        else:
            self.stdout_container.write("Clip copied to:\n" + copied)

        self.ui.record_button.clicked.disconnect(self.recording_job[2])
        self.ui.record_button.clicked.connect(self.record)
        self.recording_job = None
        self.recording_ended.emit()
        self.enable_buttons()


    def _copy_recording(self):
        threading.Thread(target=self._copy_recording_).start()


    def record(self):
        self.stdout_container.write("Started recording")
        recording_lock = threading.Lock()
        filename = "screenrecord_" + strftime("%Y.%m.%d_%H.%M.%S") + ".mp4"
        self.recording_job = (
            threading.Thread(target=self._record, args=(recording_lock,)),
            filename, recording_lock.release)
        self.ui.record_button.clicked.disconnect(self.record)
        self.ui.record_button.clicked.connect(self.recording_job[2])
        recording_lock.acquire()
        self.recording_job[0].start()


    def _install(self, *args):
        if not args:
            self.stdout_container.write(
                "Cannot install, no files were provided")
            self.enable_buttons()
            return
        print("Started install with following args:", *args)
        main_.install(self.device, *args, stdout_=self.stdout_container)
        self.enable_buttons()


    def install(self, *args):
        # TODO: display a picker, pass picked files to _install
        if args == (False,):
            args = ""
        self.disable_buttons()
        threading.Thread(target=self._install,
                         args=(args)).start()


    def _pull_traces(self):
        result = main_.pull_traces(self.device, stdout_=self.stdout_container)
        if result:
            text = "Traces saved to" + result

        self.stdout_container.write(text)
        sleep(0.25) # let's not pull those logs too often :V
        self.traces_pulled.emit()


    def pull_traces(self):
        self.disable_buttons()
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
        print("Confirming cleaning with following config:")
        print(parsed_config)
        # TODO: Show a confirmation popup before attempting cleaning
        threading.Thread(
            target=self._clean_proper, args=([parsed_config])).start()


    def _clean_proper(self, parsed_config):
        main_.clean(self.device, parsed_config=parsed_config, force=True,
                    stdout_=self.stdout_container)
        self.cleaning_ended.emit()


    def clean(self):
        self.disable_buttons()
        threading.Thread(target=self._clean_prepare).start()
        # TODO: Allow the user to choose config file / create a new one


    def remove_last_line(self):
        self.ui.device_console.moveCursor(11)
        self.ui.device_console.moveCursor(4, 1) # move to start of current block
        self.ui.device_console.moveCursor(7, 1) # move to end of last block
        self.ui.device_console.textCursor().removeSelectedText()
        self.ui.device_console.moveCursor(11)

    def write_to_console(self):
        text = self.stdout_container.read().rstrip()
        # spam prevention
        if not text or text == self.last_console_line:
            return

        status = re.search("^\[...%\]", text)
        if status:
            if re.search("^\[...%\]", self.last_console_line):
                self.remove_last_line()

        self.last_console_line = text
        print("Device tab console log:", [text])
        self.ui.device_console.append(text)
        self.ui.device_console.moveCursor(11) # move to the end of document
        self.ui.device_display.setCurrentIndex(1) # switch to console


class MainWin(QtWidgets.QMainWindow):
    new_device_found = QtCore.pyqtSignal(main_.Device)
    device_connected = QtCore.pyqtSignal(main_.Device)
    device_disconnected = QtCore.pyqtSignal(main_.Device)
    device_scan_started = QtCore.pyqtSignal()
    device_scan_ended = QtCore.pyqtSignal()

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
        self.new_device_found.connect(self.add_new_device)
        self.device_connected.connect(self.show_device_tab)
        self.device_disconnected.connect(self.hide_device_tab)
        self.device_scan_started.connect(self.device_timer.stop)
        self.device_scan_ended.connect(self.device_timer.start)

        self.scan_devices()


    def _scan_devices(self):
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

        self.device_scan_ended.emit()


    def scan_devices(self):
        self.device_scan_started.emit()
        threading.Thread(target=self._scan_devices).start()


    def add_new_device(self, device):
        model = device.info["Product"]["Model"]
        if model is None:
            model = "Unknown model"
        manufacturer = device.info["Product"]["Manufacturer"]
        if manufacturer is None:
            manufacturer = "Unknown manufacturer"

        tab_name = model + " -- "
        tab_name += manufacturer
        self.stdout_container.write(" ".join(["Initializing connection with",
                                              tab_name]))
        print(tab_name, "found, adding new tab")

        new_tab = DeviceTab(device)
        self.gui_devices[device] = {"tab":new_tab, "name":tab_name}
        new_tab.connection_reset.connect(self.device_timer.stop)
        new_tab.recording_ended.connect(self.device_timer.start)
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
        text = self.stdout_container.read().rstrip()

        # spam prevention
        if text in blacklist:
            return False
        if text == self.last_console_line:
            return False

        self.last_console_line = text
        text = "".join(["[", strftime("%H:%M:%S"), "] ", text])
        print("Main window console log:", [text])
        self.ui.status_console.append(text)
        self.ui.status_console.moveCursor(11) # move to the end of document


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWin()

    app.setStyleSheet(qtdark.load_stylesheet())

    window.show()
    sys.exit(app.exec_())
