"""Everything in this module is very experimental. I'm still very much
learning PyQt5, and this is my first project that uses threading in a
major way. This might get interesting.

Consider yourself warned.

Here be dragons
"""
import re
import sys
import queue
import threading
from time import sleep, strftime
from pathlib import Path

from PyQt5 import QtWidgets, QtCore

import helper.main as main_
import helper.device as device_
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

    def flush(self):
        # TODO: move cursor back to end of last line when stdout_ is flushed
        # TODO: display loading indicator until the next write
        #       can be done by continuously writing and deleting a set of
        #       characters, to create effect shown below
        #       [   ] -> [.  ] -> [.. ] -> [...] -> [   ]
        pass


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
        super().__init__()
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
        self.ui.record_button.clicked.connect(self.switch_to_console)
        #self.recording_stopped.connect(self._copy_recording)

        # traces
        self.ui.traces_button.clicked.connect(self.pull_traces)
        self.ui.traces_button.clicked.connect(self.switch_to_console)

        # Installing
        self.ui.install_button.clicked.connect(self.install)
        self.ui.install_button.clicked.connect(self.switch_to_console)

        # Cleaning
        self.ui.clean_button.clicked.connect(self.clean)
        self.ui.clean_button.clicked.connect(self.switch_to_console)
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
        # this will be the same as the confirmation popup in normal install
        # but pre-populated with files received from drag & drop


    def write_device_info(self):
        #text = self.device.get_full_info_string()
        #print([text])
        #self.ui.device_info_tab.append(text)
        pass


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
        filename = "".join([self.device.info("Product", "Model"),
                            "_screenrecord_",
                            strftime("%Y.%m.%d_%H.%M.%S"), ".mp4"])
        record_ = threading.Thread(
            target=main_.record, args=(self.device,),
            kwargs={"name":filename, "silent":True,},
            daemon=True)

        record_.start()
        sleep(0.2) # wait before enabling buttons
        # TODO: let the thread know that everything is setup and buttons can be enabled
        self.ui.record_button.setEnabled(True)

        while not lock.acquire(False):
            sleep(0.3)

        self.ui.record_button.clicked.disconnect(self.recording_job[1])
        self.ui.record_button.setEnabled(False)
        self.connection_reset.emit()
        if Path(filename).is_file:
            self.stdout_container.write("File saved to {} I guess?".format(Path(filename).resolve()))
        self.recording_stopped.emit()
        self.enable_buttons()



    def record(self):
        self.disable_buttons()
        self.stdout_container.write("Started recording")

        recording_lock = threading.Lock()
        self.recording_job = (
            threading.Thread(target=self._record, args=(recording_lock,),
                             daemon=True),
            recording_lock.release)
        # TODO: the 'recording_job' is a dirty hack
        # it is here because the disconnect all function for some reason does
        # not actually disconnect anything
        self.ui.record_button.clicked.disconnect(self.record)
        self.ui.record_button.clicked.connect(self.recording_job[1])
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
        self.disable_buttons()

        if args == (False,):
            args = ""

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
        if not text:
            return

        status = re.search("^\\[...%\\]", text)
        if status:
            if re.search("^\\[...%\\]", self.last_console_line):
                self.remove_last_line()

        self.last_console_line = text
        print("Device tab console log:", [text])
        self.ui.device_console.append(text)
        self.ui.device_console.moveCursor(11) # move to the end of document


    def switch_to_console(self):
        console_index = self.ui.device_display.indexOf(self.ui.device_console_tab)
        self.ui.device_display.setCurrentIndex(console_index)


class MainWin(QtWidgets.QMainWindow):
    new_device_found = QtCore.pyqtSignal(device_.Device)
    device_connected = QtCore.pyqtSignal(device_.Device)
    device_disconnected = QtCore.pyqtSignal(device_.Device)
    device_scan_started = QtCore.pyqtSignal()
    device_scan_ended = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()

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
        # list of serial ids of connected devices
        connected_serials = {device.serial: device for device in device_.get_devices(initialize=False)}

        for device_serial in self.gui_devices:
            # device known and tab initialized -- show the tab if hidden (index below 0)
            if device_serial in connected_serials:
                if self.ui.device_container.indexOf(self.gui_devices[device_serial]['tab']) < 0:
                    self.device_connected.emit(self.gui_devices[device_serial]['device'])

                connected_serials.pop(device_serial)
            # tab's device not connected, hide the tab if shown (index above 0)
            elif self.ui.device_container.indexOf(self.gui_devices[device_serial]['tab']) >= 0:
                self.device_disconnected.emit(self.gui_devices[device_serial]['device'])

        for device_serial in connected_serials:
            device = connected_serials[device_serial]
            self.new_device_found.emit(device)

        self.device_scan_ended.emit()


    def scan_devices(self):
        self.device_scan_started.emit()
        threading.Thread(target=self._scan_devices).start()


    def add_new_device(self, device):
        """Create and add a new device tab to tab widget."""
        #raise NotImplementedError

        #device.device_init()

        model = device.info_dict("Product", "Model")
        if model is None:
            model = "Unknown model"
        manufacturer = device.info("Product", "Manufacturer")
        if manufacturer is None:
            manufacturer = "Unknown manufacturer"

        tab_name = " ".join([manufacturer, "--", model])
        self.stdout_container.write(" ".join(["Initializing connection with",
                                              tab_name]))

        new_tab = DeviceTab(device)
        self.gui_devices[device.serial] = {"tab":new_tab, "name":tab_name, 'device':device}
        new_tab.connection_reset.connect(self.device_timer.stop)
        new_tab.recording_ended.connect(self.device_timer.start)
        self.device_connected.emit(device)


    def hide_device_tab(self, device):
        device_tab = self.gui_devices[device.serial]["tab"]
        tab_name = self.gui_devices[device.serial]["name"]
        self.stdout_container.write(" ".join(["Lost connection with",
                                              tab_name]))
        print(tab_name, "disconnected, hiding its tab")

        device_tab_index = self.ui.device_container.indexOf(device_tab)
        if device_tab_index >= 0:
            self.ui.device_container.removeTab(device_tab_index)
        if self.ui.device_container.count() == 0:
            self.ui.device_container.addTab(self.ui.empty_tab, "No devices")


    def show_device_tab(self, device):
        device_tab = self.gui_devices[device.serial]["tab"]
        tab_name = self.gui_devices[device.serial]["name"]
        self.stdout_container.write(" ".join(["Successfully connected with",
                                              tab_name]))
        print(tab_name, "connected, showing its tab")

        self.ui.device_container.addTab(device_tab, tab_name)
        self.ui.device_container.setCurrentWidget(device_tab)

        empty_tab_index = self.ui.device_container.indexOf(self.ui.empty_tab)
        if empty_tab_index >= 0:
            self.ui.device_container.removeTab(empty_tab_index)


    def write_to_console(self):
        blacklist = []
        text = self.stdout_container.read().rstrip()
        if not text:
            return False

        # spam prevention
        if text in blacklist:
            return False
        #if text == self.last_console_line:
        #    return False

        self.last_console_line = text
        text = "".join(["[", strftime("%H:%M:%S"), "] ", text])
        print("Main window console log:", [text])
        self.ui.status_console.append(text)
        self.ui.status_console.moveCursor(11) # move to the end of document


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWin()

    window.show()
    sys.exit(app.exec_())
