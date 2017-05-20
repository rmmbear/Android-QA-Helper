from pathlib import Path

import helper as helper_
import helper.device as device_
import helper.tests as tests_


FULL_DEVICE_CONFIG = helper_.BASE + "/tests/full_config"
COMPATIBILITY_DIR = helper_.BASE + "/tests/compatibility"


class DummyDevice(device_.Device):
    def _device_init(self, config_dir, ignore_nonexistent_files=False):
        """Gather all the information."""
        for info_source, info_specs in device_.INFO_EXTRACTION_CONFIG.items():
            if self.limit_init and info_source[-1] not in self.limit_init:
                continue

            try:
                kwargs = dict(info_source[1])
            except IndexError:
                kwargs = {}

            source_file = Path(config_dir) / info_source[-1]
            source_output = ''
            print("Reading file:", str(source_file))
            try:
                with source_file.open(mode="r", encoding="utf-8") as f:
                    source_output = f.read()
            except FileNotFoundError:
                if not ignore_nonexistent_files:
                    raise

            if 'as_list' in kwargs:
                if kwargs['as_list']:
                    source_output = source_output.splitlines()

            for info_object in info_specs:
                if info_object.can_run(self):
                    info_object.run(self, source_output)

        self.initialized = True


class TestDeviceInit:
    def test_full(self, config_dir=FULL_DEVICE_CONFIG):
        """Test device initialization with a complete input from an actual
        device.
        """
        device = DummyDevice(config_dir, 'dummy')
        device._device_init(config_dir)

        device.print_full_info()

        assert device.available_commands
        assert device.anr_trace_path

        for category in device.info.values():
            for key, value in category.items():
                # extracting resolution is not all that reliant
                # I'm fine with missing this one key if all others are present
                if key == 'Resolution':
                    continue
                assert key and value


    def test_compatibility(self, config_dir=COMPATIBILITY_DIR):
        config_dir = Path(config_dir)

        for path in config_dir.iterdir():
            if path.is_dir():
                self.test_full(str(path))


    def test_all_limited(self, config_dir=FULL_DEVICE_CONFIG):
        """"""
        device = DummyDevice(1, 'dummy', limit_init=['nonexistent_info_source'])
        device._device_init(config_dir)

        device.print_full_info()

        assert not device.available_commands
        assert not device.anr_trace_path

        for category in device.info.values():
            for key, value in category.items():
                assert key and not value


    def test_empty(self):
        """Test device initialization without any actual input.
        """
        random_dir = tests_.get_nonexistent_path()
        device = DummyDevice(2, 'dummy')
        device._device_init(random_dir, True)

        device.print_full_info()

        assert not device.available_commands
        assert not device.anr_trace_path

        for category in device.info.values():
            for key, value in category.items():
                assert key and not value


    '''
    def test_garbage(self):
        """Test device initialization with garbage unicode input for all
        device's info gathering methods.
        """
        tmp = Path(helper_.BASE + "/tests/garbage_config")
        tmp.mkdir(exist_ok=True)

        garbage = tmp / 'garbage_file'
        with garbage.open(mode="w", encoding="utf-8") as eff_me_up:
            eff_me_up.write("".join([chr(x) for x in range(1, 0x110000) if chr(x).isprintable()]))

        for info_source in device_.INFO_EXTRACTION_CONFIG:
            filename = info_source[-1]
            shutil.copy(str(garbage), str(tmp / filename))

        device = DummyDevice(1234567890)
        device._device_init(tmp)

        #for config_file in tmp.iterdir():
        #    config_file.unlink()
        #tmp.rmdir()

        assert device.available_commands
        assert not device.anr_trace_path

        for category in device.info.values():
            for key, value in category.items():
                assert key
                assert not value

        return device


    '''
    '''
    def test_full_garbage(self):
        """Test device initialization with a complete input consisting of
        unicode garbage, meaning that all attributes will be filled with
        meaningless unicode string.
        """
        tmp = Path(helper_.BASE + "/tests/garbage_full_config")
        tmp.mkdir(exist_ok=True)

        for info_source in device_.INFO_EXTRACTION_CONFIG:
            filename = info_source[-1]
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
            [chr(x) for x in range(1, 0x100) if chr(x).isprintable()])

        import string

        for character in string.whitespace:
            garbage_.replace(character, '')
        with (tmp / "getprop").open(mode="w", encoding="utf-8") as getprop_file:

            for prop in prop_names:
                getprop_file.write(prop + " : [")
                getprop_file.write(garbage_)
                getprop_file.write("]\n")

        device = DummyDevice(tmp)
        for config_file in tmp.iterdir():
            config_file.unlink()
        tmp.rmdir()

        #assert device.available_commands
        #assert device.anr_trace_path

        for category in device.info.values():
            for key, value in category.items():
                assert category and key and value

        return device
    '''
