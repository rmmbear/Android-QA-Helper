import helper as _helper
from helper import shutil
from helper import Path
from helper import OrderedDict
from helper import main as _main


FULL_DEVICE_CONFIG = _helper.BASE + "/tests/full_config"
DEVICE_CONFIG = {
    "ls /system/bin"                        :"available_commands",
    "cat /proc/meminfo"                     :"meminfo",
    "wm size"                               :"screen_size",
    "wm density"                            :"screen_density",
    "getprop"                               :"getprop",
    "cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq" :"cpu_freq",
    "cat /proc/cpuinfo"                     :"cpuinfo",
    "cat /sys/devices/system/cpu/present"   :"cpu_cores",
    "dumpsys SurfaceFlinger"                :"surfaceflinger_dump"
    }

GARBAGE = "".join([chr(x) for x in range(1, 0x110000) if chr(x).isprintable()])

class DummyDevice(_main.Device):


    def __init__(self, config_dir, serial=999999, status="device"):

        self.serial = serial
        self.config_dir = Path(config_dir)

        self.anr_trace_path = None
        self.available_commands = None
        self.info = OrderedDict()

        info = [
            ("Product", ["Model",
                         "Name",
                         "Manufacturer",
                         "Brand",
                         "Device"]),
            ("OS",      ["Android Version",
                         "Android API Level",
                         "Build ID",
                         "Build Fingerprint"]),
            ("RAM",     ["Total"]),
            ("CPU",     ["Chipset",
                         "Processor",
                         "Cores",
                         "Architecture",
                         "Max Frequency",
                         "Available ABIs"]),
            ("GPU",     ["Model",
                         "GL Version",
                         "Compression Types"]),
            ("Display", ["Resolution",
                         "Refresh-rate",
                         "V-Sync",
                         "Soft V-Sync",
                         "Density",
                         "X-DPI",
                         "Y-DPI"])
            ]

        for pair in info:
            props = OrderedDict()

            for prop in pair[1]:
                props[prop] = None

            self.info[pair[0]] = props

        self.initialized = False

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
        an_unlikely_directory = "/a/b/c/d/f/v/g/h/n/v/sd/a"
        # TODO: generate an unlikely directory instead of having it hard-coded

        device = DummyDevice(an_unlikely_directory)

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
        tmp = Path(_helper.BASE + "/tests/garbage_config")
        tmp.mkdir(exist_ok=True)

        config_filenames = list(DEVICE_CONFIG.values())

        garbage = tmp / config_filenames[0]
        with garbage.open(mode="w", encoding="utf-8") as eff_me_up:
            eff_me_up.write(GARBAGE)

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
        tmp = Path(_helper.BASE + "/tests/garbage_full_config")
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
                      "[ro.sf.lcd_density]"]

        with (tmp / "getprop").open(mode="w", encoding="utf-8") as getprop_file:
            for prop in prop_names:
                getprop_file.write(prop + " : [")
                getprop_file.write(GARBAGE)
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


class TestADB:

    def test_no_adb(self):
        """Make sure the program stops when there is no adb binary.
        """
        _main.ADB = "/just/some/nonsense"

        try:
            _main.adb_execute("")
        except SystemExit:
            assert True
            return True

        assert False

    def test_no_aapt(self):
        """Make sure the program stops when there is no aapt binary.
        """
        _main.AAPT = "/just/some/nonsense"

        try:
            _main.aapt_execute("")
        except SystemExit:
            assert True
            return True

        assert False


def dump_devices(directory):
    """Function for dumping device information used in device initiation. Dumped
    files can be used with TestDeviceInit.test_full().
    """
    print("Before continuing, please remember that ALL dumped files may contain",
          "sensitive data. Please pay special attention to the 'getprop' file",
          "which almost certainly will contain data you do not want people to",
          "see.",)
    input("Press enter to continue")

    Path(directory).mkdir(exist_ok=True)

    for device in _main.get_devices():
        device_id = device.info["Product"]["Model"] + "_" + device.info["Product"]["Manufacturer"]
        device_dir = Path(directory, device_id + "_DUMP")
        device_dir.mkdir(exist_ok=True)
        print()
        print("Dumping", device_id)

        for command, filename in DEVICE_CONFIG.items():
            output = device.shell_command(command, return_output=True,
                                          as_list=False)

            with Path(device_dir, filename).open(mode="w", encoding="utf-8") as dump_file:
                dump_file.write(output)

        print("Device dumped to", str(device_dir.resolve()))
