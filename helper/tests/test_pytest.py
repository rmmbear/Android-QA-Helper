import re
from pathlib import Path

import helper as helper_
#import helper.device as device_
#import helper.tests as tests_
import helper.extract_data as helper_extract


FULL_DEVICE_CONFIG = helper_.BASE + "/tests/full_config"
COMPATIBILITY_DIR = helper_.BASE + "/tests/compatibility"
COMPATIBILITY_OUT_DIR = helper_.BASE + "/tests/compatibility_output"


class TestExtractModule:
    def verify_info_config(self, config):
        """Verify that provided config is formatted correctly and uses existing info keys"""
        # config is a non-empty iterable
        assert config and hasattr(config, "__iter__")

        for section in config:
            # each item in config is either a list or tuple containing two elements
            assert isinstance(section, (list, tuple)) and len(section) == 2

            if isinstance(section, list):
                # section name is a non-empty string
                assert section[0] and isinstance(section[0], str)

                for pair in section[1]:
                    # each item within a section is an iterable containing two elements
                    assert len(pair) == 2
                    # the two are non-empty strings
                    assert ((pair[0] and pair[1]) and
                            isinstance(pair[0], str) and isinstance(pair[1], str))

                    assert pair[1] in helper_extract.INFO_KEYS
            else:
                # each of the objects in loose (name, key) tuple is a non-empty string
                assert (section[0] and section[1] and
                        isinstance(section[0], str) and isinstance(section[1], str))

                assert section[1] in helper_extract.INFO_KEYS


    def test_verify_config_test(self):
        """Test validity of the config test."""
        import pytest
        # input that is not an iterable
        bad_input = [None, 1, 1.5]

        with pytest.raises(AssertionError):
            for config in bad_input:
                self.verify_info_config(config)

        # bad structure
        bad_structure = [
            [[[]]], "12", [([],)],
            # reversed expectations
            [["Identity", [["Model", "device_model"]]], ["CPU Cores", "cpu_core_count"]],
            (("Identity", (("Model", "device_model"),)), ("CPU Cores", "cpu_core_count")),
            (("Identity", (("Model", "device_model"),)),),
            [["CPU Cores", "cpu_core_count"]],
            # wrong number of items
            (["Identity", [["Model", "device_model"]], "OwO"],),
            (["Identity", [["Model", "device_model", "hewwo"]]],),
            (["Identity", [["Model"]]],),
            [("CPU Cores", "cpu_core_count", "'sup")],
            [("CPU Cores",)],
        ]
        with pytest.raises(AssertionError):
            for config in bad_structure:
                self.verify_info_config(config)

        # valid structure, bad contents
        bad_contents = [
            # empty nested iterables
            [([],), [[], []]], [([],)], [[[]]],
            # empty strings
            [("", ""), ["", ("", "")]], [("", "")], [["", ("", "")]],
            # unexpected type
            [(1, 2), [3, (4, 5)]], [(0.1, 0.2)], [[True, (True, True)]],
            [("dd"), ["c", ("cc")]], [("bb")], [["a", ("aa")]],
        ]
        with pytest.raises(AssertionError):
            for config in bad_contents:
                self.verify_info_config(config)

        # valid config
        valid_configs = [
            # section -> (name, key), loose (name, key)
            (["Identity", [("Model", "device_model")]], ("CPU Cores", "cpu_core_count")),
            # no loose tuple
            (["Identity", [["Model", "device_model"]]],),
            # only loose (name, key)
            [("CPU Cores", "cpu_core_count")],
        ]
        for config in valid_configs:
            print(config)
            self.verify_info_config(config)


    def test_verify_brief_surfaced_config(self):
        """Verify that brief surfaced info config is formatted correctly and references existing info keys."""
        self.verify_info_config(helper_extract.SURFACED_BRIEF)


    def test_verify_verbose_surfaced_config(self):
        """Verify that verbose surfaced info config is formatted correctly and references existing info keys."""
        self.verify_info_config(helper_extract.SURFACED_VERBOSE)


    def test_reference_existing_keys_only(self):
        """Check if the module references existing info keys."""
        extraction_module = Path(helper_.BASE) / "extract_data.py"

        with extraction_module.open(mode="r", encoding="utf-8") as module:
            extraction_code = module.read()

        # a bit naive approach, but it works
        # FIX: this will not catch indirect references
        info_keys = re.findall("(?:device\\.info\\_dict\\[\\\")([^\\]\\\"]*)", extraction_code)

        for key in info_keys:
            assert key in helper_extract.INFO_KEYS


    def test_reference_existing_keys_only_main(self):
        """Check if the module references existing info keys."""
        extraction_module = Path(helper_.BASE) / "main.py"

        with extraction_module.open(mode="r", encoding="utf-8") as module:
            extraction_code = module.read()

        # a bit naive approach, but it works
        # FIX: this will not catch indirect references
        info_keys = re.findall("(?:device\\.info\\_dict\\[\\\")([^\\]\\\"]*)", extraction_code)

        for key in info_keys:
            assert key in helper_extract.INFO_KEYS

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
