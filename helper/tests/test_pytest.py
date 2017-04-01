import shutil
from pathlib import Path

import helper as helper_
import helper.main as main_
import helper.tests as tests_


FULL_DEVICE_CONFIG = tests_.FULL_DEVICE_CONFIG
DEVICE_CONFIG = tests_.DEVICE_CONFIG

class DummyDevice(main_.Device):


    def __init__(self, config_dir, serial=999999, status="device"):
        self.config_dir = Path(config_dir)
        self.ext_storeage = None

        main_.Device.__init__(self, serial)

        if not status:
            self.status = "device"
        else:
            self.status = status


    @property
    def status(self):
        self._status = "device"
        return self._status


    @status.setter
    def status(self, status):
        self._status = status
        self._device_init()


    def shell_command(self, *args, return_output=False, check_server=True,
                      as_list=True):

        command = " ".join(args)
        if not return_output:
            print("Tried executing", command)
            print("This is a dummy device, dummy!")
            return False

        if command in DEVICE_CONFIG:
            command_file = (self.config_dir / DEVICE_CONFIG[command])
            if command_file.is_file():
                with command_file.open(mode="r", encoding="utf-8") as f:
                    output = f.read()
            else:
                output = ""
        else:
            output = ""

        if as_list:
            output = output.splitlines()

        return output


class TestDeviceInit:
    def test_empty(self):
        """Test device initialization without any actual input.
        """
        device = DummyDevice(tests_.get_nonexistent_path())

        assert device.initialized
        assert not device.available_commands
        assert not device.anr_trace_path

        for category in device.info.values():
            for key, value in category.items():
                assert key
                assert not value

        return device


    def test_garbage(self):
        """Test device initialization with garbage unicode input for all
        device's info gathering methods.
        """
        tmp = Path(helper_.BASE + "/tests/garbage_config")
        tmp.mkdir(exist_ok=True)

        config_filenames = list(DEVICE_CONFIG.values())

        garbage = tmp / config_filenames[0]
        with garbage.open(mode="w", encoding="utf-8") as eff_me_up:
            eff_me_up.write(
         "".join([chr(x) for x in range(1, 0x110000) if chr(x).isprintable()]))

        for filename in config_filenames[1::]:
            shutil.copy(str(garbage), str(tmp / filename))


        shutil.move(str(garbage), str(tmp / config_filenames[0]))

        device = DummyDevice(tmp)
        for config_file in tmp.iterdir():
            config_file.unlink()
        tmp.rmdir()

        assert device.initialized
        assert device.available_commands
        assert not device.anr_trace_path

        for category in device.info.values():
            for key, value in category.items():
                assert key
                assert not value

        return device


    def test_full(self):
        """Test device initialization with a complete input from an actual
        device.
        """

        device = DummyDevice(FULL_DEVICE_CONFIG)

        assert device.initialized
        assert device.available_commands
        assert device.anr_trace_path

        for category in device.info.values():
            for key, value in category.items():
                assert key
                assert value

        return device


    def test_full_garbage(self):
        """Test device initialization with a complete input consisting of
        unicode garbage, meaning that all attributes will be filled with
        meaningless unicode string.
        """
        tmp = Path(helper_.BASE + "/tests/garbage_full_config")
        tmp.mkdir(exist_ok=True)

        for filename in DEVICE_CONFIG.values():
            shutil.copy(FULL_DEVICE_CONFIG + "/" + filename, str(tmp) + "/" + filename)

        # generate getprop
        prop_names = ["[dalvik.vm.stack-trace-file]",
                      "[ro.product.cpu.abi]",
                      "[ro.product.cpu.abi2]",
                      "[ro.product.cpu.abilist]",
                      "[ro.product.cpu.abilist32]",
                      "[ro.product.cpu.abilist64]",
                      "[ro.product.cpu.abi]",
                      "[ro.mediatek.platform]",
                      "[ro.board.platform]",
                      "[dalvik.vm.stack-trace-file]",
                      "[ro.product.model]",
                      "[ro.product.name]",
                      "[ro.product.manufacturer]",
                      "[ro.product.brand]",
                      "[ro.product.device]",
                      "[ro.build.version.release]",
                      "[ro.build.version.sdk]",
                      "[ro.build.id]",
                      "[ro.build.fingerprint]",
                      "[ro.sf.lcd_density]"
                     ]

        garbage_ = "".join(
            [chr(x) for x in range(1, 0x110000) if chr(x).isprintable()])
        with (tmp / "getprop").open(mode="w", encoding="utf-8") as getprop_file:

            for prop in prop_names:
                getprop_file.write(prop + " : [")
                getprop_file.write(garbage_)
                getprop_file.write("]\n")

        device = DummyDevice(tmp)
        for config_file in tmp.iterdir():
            config_file.unlink()
        tmp.rmdir()

        assert device.initialized
        assert device.available_commands
        assert device.anr_trace_path

        for category in device.info.values():
            for key, value in category.items():
                assert value, key

        return device


class TestNonexistentBinaries:
    def test_no_adb(self):
        """Make sure the program stops when there is no adb binary.
        """
        main_.ADB = tests_.get_nonexistent_path()

        try:
            main_.adb_execute("")
        except SystemExit:
            assert True
            return True

        assert False

    def test_no_aapt(self):
        """Make sure the program stops when there is no aapt binary.
        """
        main_.AAPT = tests_.get_nonexistent_path()

        try:
            main_.aapt_execute("")
        except SystemExit:
            assert True
            return True

        assert False
