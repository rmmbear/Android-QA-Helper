import re
from pathlib import Path

import pytest

import helper as helper_
import helper.device as device_
from helper.tests import DummyDevice

from helper.extract_data import INFO_KEYS, SURFACED_VERBOSE

FULL_DEVICE_CONFIG = helper_.CWD + "/tests/full_config"
COMPATIBILITY_DIR = helper_.CWD + "/../compat_data"


try:
    DUMP_DATA_AVAILABLE = bool([x for x in Path(COMPATIBILITY_DIR).iterdir() if x.is_dir])
except:
    DUMP_DATA_AVAILABLE = False

PHYSICAL_DEVICE_REQUIRED = pytest.mark.skipif(
    not device_.get_devices(initialize=False),
    reason="Physical (or emulated) device required, none found.")
DUMP_DATA_REQUIRED = pytest.mark.skipif(
    not DUMP_DATA_AVAILABLE, reason="Dump data required, none found.")


class TestExtractModule:
    def verify_info_config(self, config):
        """Verify that provided config is formatted correctly and uses existing info keys"""
        # config is a dictionary
        # dict = {section_name : ((variable_name, variable_value),)}
        for section, section_items in config.items():
            try:
                #section's value must be iterable
                iter(section_items)
            except TypeError:
                pytest.fail(f"value of key '{section}' is not an iterable")

            for pair in section_items:
                # each item is an iterable containing two values
                assert len(pair) == 2
                var_name, var_ref = pair
                # name must be a string or None, in which case it is ignored
                assert isinstance(var_name, str) or var_name is None
                # var reference must be a string and a reference to existing info variable
                assert isinstance(var_ref, str)
                assert var_ref in INFO_KEYS


    def test_verify_verbose_surfaced_config(self):
        """Verify that verbose surfaced info config is formatted correctly and references existing info keys."""
        self.verify_info_config(SURFACED_VERBOSE)


    def test_reference_existing_keys_only(self):
        """Check if the modules references existing info keys."""
        extraction_module = Path(helper_.CWD) / "helper/extract_data.py"
        extraction_module = Path(helper_.CWD) / "helper/main.py"
        extraction_module = Path(helper_.CWD) / "helper/cli.py"
        extraction_module = Path(helper_.CWD) / "helper/apk.py"

        with extraction_module.open(mode="r", encoding="utf-8") as module:
            extraction_code = module.read()

        # a bit naive approach, but it works
        # FIX: this will not catch indirect references
        info_keys = re.findall("(?:device\\.info\\_dict\\[\\\")([^\\]\\\"]*)", extraction_code)

        for key in info_keys:
            assert key in INFO_KEYS


class TestPhysicalDevice:
    @PHYSICAL_DEVICE_REQUIRED
    def test_full_init(self):
        connected_devices = device_.get_devices()

        if not connected_devices:
            pytest.skip("")

        found_bad = False
        for p_device in connected_devices:
            for key in INFO_KEYS:
                if not p_device.info_dict[key]:
                    found_bad = True
                    print(key, ":", [p_device.info_dict[key]])

        assert not found_bad


class TestDummyDevice:
    @DUMP_DATA_REQUIRED
    def test_full_init(self):
        """Test device initialization using dumped data."""
        indent = 4
        dummy_count = 0

        device_list = {}

        for device_dir in Path(COMPATIBILITY_DIR).iterdir():
            if not device_dir.is_dir():
                continue

            print("-----")
            print(device_dir.name)

            dummy_count += 1
            device_dummy = DummyDevice(device_dir, "dummy_{}".format(dummy_count))
            device_dummy._status = "device"
            device_dummy.load_dummy_data()
            device_dummy.extract_data()

            print(device_dummy.name)

            with (device_dir / "__DUMMY_INFO_DUMP").open(mode="w", encoding="utf-8") as info_out:
                info_out.write(device_dummy.full_info_string(initialize=False))

            unexpected_keys = []
            empty_keys = []

            with (device_dir / "__DUMMY_INFO_DICT").open(mode="w", encoding="utf-8") as info_dict_out:
                longest_key = 0
                for key in device_dummy.info_dict:
                    if len(key) > longest_key:
                        longest_key = len(key)

                line_template = "".join(["{:", str(longest_key), "} : {}"])

                for key in sorted(device_dummy.info_dict.keys()):
                    val = device_dummy.info_dict[key]
                    if not val:
                        empty_keys.append(key)
                    if key not in INFO_KEYS:
                        unexpected_keys.append(key)

                    info_dict_out.write(line_template.format(key, [val]))
                    info_dict_out.write("\n")


            missing_keys = []

            for key in INFO_KEYS:
                if key not in device_dummy.info_dict:
                    missing_keys.append(key)

            if empty_keys:
                print("Keys did not have values assigned ({}):".format(len(empty_keys)))
                for key in empty_keys:
                    print(" "*indent, key)
            if unexpected_keys:
                print("Keys were not expected ({}):".format(len(unexpected_keys)))
                for key in unexpected_keys:
                    print(" "*indent, key)
            if missing_keys:
                print("Keys from INFO_KEYS were not found ({}):".format(len(missing_keys)))
                for key in missing_keys:
                    print(" "*indent, key)

            device_list[device_dir.name] = {}
            device_list[device_dir.name]["unexpected"] = unexpected_keys
            device_list[device_dir.name]["empty"] = empty_keys
            device_list[device_dir.name]["missing"] = missing_keys
            print("/////")

        for device in device_list:
            assert bool(not device_list[device]["unexpected"])
            assert bool(not device_list[device]["missing"])
            assert bool(not device_list[device]["empty"])

# TODO: rewrite everything below this comment

"""
class TestDeviceInit:
    def test_full(self, config_dir=FULL_DEVICE_CONFIG, write_output=None,
                  ignore_nonexistent_files=False):
        """"""Test device initialization with a complete input from an actual
        device.
        """"""
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

        for category in device.info_dict.values():
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
        #""""""
        device = DummyDevice("dummy_fill_limited", limit_init=('asssss',),
                             config_dir=config_dir)

        print(device.full_info_string(initialize=False))

        assert not device.available_commands
        assert not device.anr_trace_path

        for category in device.info_dict.values():
            for key, value in category.items():
                assert key and not value


    def test_empty(self):
        """"""Test device initialization without any actual input.
        """"""
        random_dir = tests_.get_nonexistent_path()
        device = DummyDevice("dummy_empty", config_dir=random_dir,
                             ignore_nonexistent_files=True)

        print(device.full_info_string(initialize=False))

        assert not device.available_commands
        assert not device.anr_trace_path

        for category in device.info_dict.values():
            for key, value in category.items():
                assert key and not value
"""
