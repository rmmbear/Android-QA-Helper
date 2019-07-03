import sys
import logging
from pathlib import Path

from helper import extract_data
from helper.device import DeviceOfflineError, Device

LOGGER = logging.getLogger(__name__)
EXTRACTION_FUNCTIONS = {x[8::]:getattr(extract_data, x) for x in dir(extract_data) if x.startswith("extract_")}

class DummyDevice(Device):
    def __init__(self, config_dir, *args, **kwargs):
        self.config_dir = config_dir
        self._loaded_dummy_data = False
        self.ignore_load_errors = True

        # avoid triggering automatic data extraction
        if len(args) > 1:
            if not isinstance(args, list):
                args = list(args)

            status = args[1]
            args[1] = "offline"
        else:
            try:
                status = kwargs["status"]
                kwargs["status"] = "offline"
            except KeyError:
                status = "offline"

        super().__init__(*args, **kwargs)
        self._status = status


    @property
    def name(self):
        """Property holding a human-readable name of the device.

        Name consists of: dummy number, manufacturer, model and serial number."""
        if self._name:
            return self._name

        if "identity" not in self._extracted_info_groups:
            return "Unknown device ({})".format(self.serial)

        self._name = "".join([self.info_dict["device_manufacturer"], " - ",
                              self.info_dict["device_model"], " (", self.serial,
                              ")"])
        return self._name


    @property
    def status(self):
        """Dummy's status never changes."""
        return self._status


    def adb_command(self, *args, **kwargs):
        """Always return a blank string for dummy adb commands."""
        print(args, kwargs)
        if self.status != "device":
            raise DeviceOfflineError("Called adb command while device {} was offline".format(self.serial), self.serial)
        #return command_output
        return ""


    def shell_command(self, *args, **kwargs):
        """Always return a blank string for dummy shell commands."""
        if self.status != "device":
            raise DeviceOfflineError("Called shell command while device {} was offline".format(self.serial), self.serial)
        #return command_output
        return ""


    def is_type(self, file_path, file_type, check_read=False,
                check_write=False, check_execute=False, symlink_ok=True):
        """Always return True for dummy path queries."""
        #LOGGER.debug("% : queried % with kwargs %", self.name, args, kwargs)
        return True


    def load_dummy_data(self, config_dir=None):
        """Load dump data into _init_cache.
        Data in the cache is used for data extraction functions.
        """
        if not config_dir:
            config_dir = self.config_dir

        for source_name in extract_data.INFO_SOURCES:
            try:
                with (Path(config_dir) / source_name).open(mode="r", encoding="utf-8") as dummy_data:
                    self._init_cache[source_name] = dummy_data.read()
            except FileNotFoundError:
                LOGGER.error("Could not open %s", "/".join([str(config_dir), source_name]))
                if not self.ignore_load_errors:
                    raise


    def extract_data(self, limit_to=(), force_extract=False):
        """Extracting data with a dummy will result in loading all
        dump data, no matter what is specified in limit_to.
        """
        for command_id, command in EXTRACTION_FUNCTIONS.items():
            if limit_to:
                if command_id not in limit_to:
                    continue

            if command in self._extracted_info_groups:
                if not force_extract:
                    #LOGGER.debug("'%s' - skipping extraction of '%s' - command already executed", self.name, command_id)
                    continue

            command(self)
            if command_id not in self._extracted_info_groups:
                self._extracted_info_groups.append(command_id)

        #self._init_cache = {}
