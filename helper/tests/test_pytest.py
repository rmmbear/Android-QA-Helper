from pathlib import Path

import helper as helper_
import helper.device as device_
import helper.tests as tests_


FULL_DEVICE_CONFIG = helper_.BASE + "/tests/full_config"
COMPATIBILITY_DIR = helper_.BASE + "/tests/compatibility"
COMPATIBILITY_OUT_DIR = helper_.BASE + "/tests/compatibility_output"


class DummyDevice(device_.Device):
    def __init__(self, *args, config_dir=None, ignore_nonexistent_files=False,
                 **kwargs):

        self.config_dir = config_dir
        self.ignore_nonexistent_files = ignore_nonexistent_files

        super().__init__(*args, **kwargs)


    def device_init(self, limit_init=(), force_init=False,
                    ignore_nonexistent_files=None):

        if not ignore_nonexistent_files:
            ignore_nonexistent_files = self.ignore_nonexistent_files

        for info_source, info_specs in device_.INFO_EXTRACTION_CONFIG.items():
            if limit_init and info_source[-1] not in limit_init:
                continue

            # skip debug info sources
            if not info_specs:
                continue

            try:
                kwargs = dict(info_source[1])
            except IndexError:
                kwargs = {}

            source_file = Path(self.config_dir) / info_source[-1]
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
    def test_full(self, config_dir=FULL_DEVICE_CONFIG, write_output=None,
                  ignore_nonexistent_files=False):
        """Test device initialization with a complete input from an actual
        device.
        """
        device = DummyDevice("dummy_full", config_dir=config_dir,
                             ignore_nonexistent_files=ignore_nonexistent_files)
        device.device_init()

        print(device.full_info_string(initialize=False))
        if write_output:
            device_file = "".join(["/", device.info('Product', 'Manufacturer'),
                                   "_", device.info('Product', 'Model')])
            write_output += device_file
            with open(write_output, mode='w', encoding='utf-8') as output_file:
                output_file.write(device.full_info_string())
                output_file.write("\n\n\n")
                for key, value in device.__dict__.items():
                    output_file.write("".join([str(key), " : ", str(value)]))
                    output_file.write("\n")

        assert device.available_commands
        assert device.anr_trace_path

        for category in device._info.values():
            if isinstance(category, list):
                assert category
            else:
                for key, value in category.items():
                    # extracting resolution is not all that reliant
                    # I'm fine with missing this one key if all others are present
                    if key == 'Resolution':
                        continue
                    assert key and value


    def test_compatibility(self, config_dir=COMPATIBILITY_DIR,
                           output_dir=COMPATIBILITY_OUT_DIR):
        config_dir = Path(config_dir)
        config_dir.mkdir(exist_ok=True)
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)

        for path in config_dir.iterdir():
            if path.is_dir():
                self.test_full(str(path), write_output=str(output_dir),
                               ignore_nonexistent_files=True)


    def test_all_limited(self, config_dir=FULL_DEVICE_CONFIG):
        """"""
        device = DummyDevice("dummy_fill_limited", limit_init=('asssss',),
                             config_dir=config_dir)

        print(device.full_info_string(initialize=False))

        assert not device.available_commands
        assert not device.anr_trace_path

        for category in device._info.values():
            for key, value in category.items():
                assert key and not value


    def test_empty(self):
        """Test device initialization without any actual input.
        """
        random_dir = tests_.get_nonexistent_path()
        device = DummyDevice("dummy_empty", config_dir=random_dir,
                             ignore_nonexistent_files=True)

        print(device.full_info_string(initialize=False))

        assert not device.available_commands
        assert not device.anr_trace_path

        for category in device._info.values():
            for key, value in category.items():
                assert key and not value
