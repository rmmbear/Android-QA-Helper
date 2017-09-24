import re
import helper

def _load_known_compressions():
    with open(helper.COMPRESSION_DEFINITIONS, mode="r", encoding="utf-8") as comps:
        for line in comps.read().splitlines():
            if not line or line.startswith("#"):
                continue

            name, comp_id = line.split("=", maxsplit=1)
            KNOWN_COMPRESSION_NAMES[comp_id] = name.strip()


def extract_compression_names(surfaceflinger_dump):
    """"""
    extensions = []
    for identifier, name in KNOWN_COMPRESSION_NAMES.items():
        if identifier in surfaceflinger_dump:
            extensions.append(name)

    return extensions


def abi_to_arch(abi):
    """"""
    if abi not in helper.ABI_TO_ARCH:
        return "Unknown ({})".format(abi)

    return helper.ABI_TO_ARCH[abi]


KNOWN_COMPRESSION_NAMES = {}
_load_known_compressions()


class InfoSpec:
    """"""
    __slots__ = ('var_name', 'var_dict_1', 'var_dict_2', 'extraction_commands',
                 'resolve_multiple_values', 'resolve_existing_values',
                 'post_extraction_commands')
    def __init__(self, var_name, var_dict_1=None, var_dict_2=None,
                 extraction_commands=((),), post_extraction_commands=None,
                 resolve_multiple_values='append', resolve_existing_values='append'):
        """"""
        self.var_name = var_name
        self.var_dict_1 = var_dict_1
        self.var_dict_2 = var_dict_2

        self.extraction_commands = extraction_commands
        self.post_extraction_commands = post_extraction_commands
        self.resolve_multiple_values = resolve_multiple_values
        self.resolve_existing_values = resolve_existing_values


    def get_info_variable_container(self, device):
        """Return dictionary object that is supposed to contain the
        extracted info value.
        """
        container = device.__dict__
        for name in (self.var_dict_2, self.var_dict_1):
            if not name:
                continue
            try:
                container = container[name]
            except KeyError:
                container[name] = {}
                container = container[name]

        return container


    def can_run(self, device):
        """Check if value can be assigned to info container"""
        try:
            exists = bool(self.get_info_variable_container(device)[self.var_name])
        except KeyError:
            exists = False
        return not (exists and self.resolve_existing_values == 'drop')


    def run(self, device, source):
        """"""
        value_container = self.get_info_variable_container(device)

        try:
            exists = bool(value_container[self.var_name])
        except KeyError:
            exists = False

        extracted = []
        for extraction_strategy in self.extraction_commands:
            if self.resolve_multiple_values == 'drop' and extracted:
                break

            tmp_extracted = self._extract_value(extraction_strategy, source)
            tmp_extracted = self._format_value(tmp_extracted)
            if not tmp_extracted:
                continue

            try:
                tmp_extracted = tmp_extracted.strip()
            except AttributeError:
                pass

            if self.resolve_multiple_values == 'replace':
                if isinstance(tmp_extracted, list):
                    extracted = tmp_extracted
                else:
                    extracted = [tmp_extracted]
            else:
                if isinstance(tmp_extracted, list):
                    extracted.extend(tmp_extracted)
                else:
                    extracted.append(tmp_extracted)

        if extracted:
            if exists and self.resolve_existing_values in ("append", "prepend"):

                for item in extracted:
                    sanitized_item = item.lower().replace(" ", "")
                    for existing_value in value_container[self.var_name]:
                        sanitized_existing_value = existing_value.lower().replace(" ", "")
                        # check if the extracted info is redundant
                        if sanitized_item in sanitized_existing_value:
                            extracted.remove(item)
                            break
                        # check if extracted info is more verbose than the existing value
                        elif sanitized_existing_value in sanitized_item:
                            old_item = value_container[self.var_name].index(existing_value)
                            value_container[self.var_name][old_item] = item
                            extracted.remove(item)
                            break

                #if value_container[self.var_name].lower() in extracted.lower():
                #    value_container[self.var_name] = extracted

                if self.resolve_existing_values == "append":
                    value_container[self.var_name].extend(extracted)
                else:
                    extracted.extend(value_container[self.var_name])
                    value_container[self.var_name] = extracted
            else:
                value_container[self.var_name] = extracted


    def _extract_value(self, extraction_command, source):
        """"""
        if not extraction_command:
            return source

        self_kwargs = {"$group":0}

        try:
            args = list(extraction_command[1])
        except IndexError:
            args = []

        while '$source' in args:
            args[args.index('$source')] = source
        try:
            kwargs = extraction_command[2]
        except IndexError:
            kwargs = ()

        for pair in kwargs:
            while "$source" in pair:
                pair[pair.index('$source')] = source

        kwargs = dict(kwargs)
        for var in self_kwargs:
            if var in kwargs:
                self_kwargs[var] = kwargs.pop(var)

        extracted_value = extraction_command[0](*args, **kwargs)
        if extraction_command[0] == re.search and extracted_value:
            extracted_value = extracted_value.group(self_kwargs['$group'])

        return extracted_value


    def _format_value(self, extracted_value):
        """"""
        if not self.post_extraction_commands:
            return extracted_value
        if extracted_value is None:
            return ''

        for formatting_commands in self.post_extraction_commands:
            # 0 - command, 1 - *args, 2 - **kwargs
            try:
                args = list(formatting_commands[2])
            except IndexError:
                args = []
            try:
                kwargs = formatting_commands[3]
            except IndexError:
                kwargs = dict()

            while '$extracted' in args:
                args[args.index('$extracted')] = extracted_value

            for pair in kwargs:
                while "$extracted" in pair:
                    pair[pair.index('$extracted')] = extracted_value

            try:
                if formatting_commands[0] == "function":
                    extracted_value = formatting_commands[1](*args, **kwargs)

                else:
                    extracted_value = extracted_value.__getattribute__(
                        formatting_commands[1])(*args, **kwargs)
            except ValueError:
                extracted_value = ''

            if not extracted_value:
                return None

        return extracted_value


INFO_EXTRACTION_CONFIG = {
    (("getprop",), (("as_list", False), ("return_output", True)), "getprop") : (
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.product\\.model\\]: \\[).*(?=\\])', '$source')),),
            var_name='Model', var_dict_1='Product', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.product\\.manufacturer\\]: \\[).*(?=\\])', '$source')),),
            var_name='Manufacturer', var_dict_1='Product', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.product\\.device\\]: \\[).*(?=\\])', '$source')),),
            var_name='Device', var_dict_1='Product', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.product\\.name\\]: \\[).*(?=\\])', '$source')),),
            var_name='Name', var_dict_1='Product', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.product\\.brand\\]: \\[).*(?=\\])', '$source')),),
            var_name='Brand', var_dict_1='Product', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.sf\\.lcd_density\\]: \\[).*(?=\\])', '$source')),),
            var_name='Density', var_dict_1='Display', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.build\\.version\\.release\\]: \\[).*(?=\\])', '$source')),),
            var_name='Version', var_dict_1='OS', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.build\\.version\\.sdk\\]: \\[).*(?=\\])', '$source')),),
            var_name='API Level', var_dict_1='OS', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.build\\.id\\]: \\[).*(?=\\])', '$source')),),
            var_name='Build ID', var_dict_1='OS', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.build\\.fingerprint\\]: \\[).*(?=\\])', '$source')),),
            var_name='Build Fingerprint', var_dict_1='OS', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.board\\.platform\\]: \\[).*(?=\\])', '$source')),),
            var_name='Chipset and Type', var_dict_1='CPU', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.product\\.cpu\\.abi\\]: \\[).*(?=\\])', '$source')),),
            var_name='Architecture', var_dict_1='CPU', var_dict_2='_info',
            post_extraction_commands=(
                ('function', abi_to_arch, ('$extracted',)),)),
        # accommodate for device that only have two abis and abilist is not available in getprop
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.product\\.cpu\\.abi\\]\\: \\[).*(?=\\])', '$source')),
                (re.search, ('(?<=\\[ro\\.product\\.cpu\\.abi2\\]\\: \\[).*(?=\\])', '$source'))),
            var_name='Available ABIs', var_dict_1='CPU', var_dict_2='_info'),
        # replace the above info if abilist is available
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[ro\\.product\\.cpu\\.abilist\\]\\: \\[).*(?=\\])', '$source')),),
            var_name='Available ABIs', var_dict_1='CPU', var_dict_2='_info', resolve_existing_values='replace',
            post_extraction_commands=(
                ('method', 'replace', (',', ', ')),
                ('method', 'replace', ('  ', ' ')))),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[dalvik\\.vm\\.stack\\-trace\\-file\\]: \\[).*(?=\\])', '$source')),),
            var_name='anr_trace_path'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[internal\\_sd\\_path\\]: \\[).*(?=\\])', '$source')),),
            var_name='internal_sd_path', resolve_existing_values='drop'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=\\[external\\_sd\\_path\\]: \\[).*(?=\\])', '$source')),),
            var_name='external_sd_path', resolve_existing_values='drop'),
    ),
    (("dumpsys", "SurfaceFlinger"), (("as_list", False), ("return_output", True)), "surfaceflinger_dump"): (
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?:GLES\\:\\ )(.*?)(?:\\,)', '$source'), (('$group', 1),)),),
            var_name='Vendor', var_dict_1='GPU', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?:GLES\\:\\ .*?\\,)(.*?)(?:\\,)', '$source'), (('$group', 1),)),),
            var_name='Model', var_dict_1='GPU', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=GLES: )(?:[^\\,]+\\,){2}(.*)', '$source'), (('$group', 1),)),),
            var_name='GL Version', var_dict_1='GPU', var_dict_2='_info'),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=x-dpi).*', '$source')),),
            var_name='X-DPI', var_dict_1='Display', var_dict_2='_info',
            post_extraction_commands=(
                ('method', 'strip', (' :\t',)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=y-dpi).*', '$source')),),
            var_name='Y-DPI', var_dict_1='Display', var_dict_2='_info',
            post_extraction_commands=(
                ('method', 'strip', (' :\t',)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=Display\\[0\\] :)[^,]*', '$source')),),
            var_name='Resolution', var_dict_1='Display', var_dict_2='_info',
            post_extraction_commands=(
                ('method', 'strip', (' :\t',)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=GLES:)(.*)(\\n*)(.*\\n*.*)', '$source'), (('$group', 3),)),),
            var_name='gles_extensions',
            post_extraction_commands=(
                ('method', 'split'),)),
        InfoSpec(
            var_name='Texture Types', var_dict_1='GPU', var_dict_2='_info',
            post_extraction_commands=(
                ('function', extract_compression_names, ('$extracted',)),)),
    ),
    (("cat", "/proc/cpuinfo"), (("as_list", False), ("return_output", True)), "cpuinfo"): (
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=Hardware).*', '$source')),),
            var_name='Chipset and Type', var_dict_1='CPU', var_dict_2='_info', resolve_existing_values='prepend',
            post_extraction_commands=(
                ('method', 'strip', (' :\t',)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=model name).*', '$source')),
                (re.search, ('(?<=Processor).*', '$source'))),
            var_name='Chipset and Type', var_dict_1='CPU', var_dict_2='_info', resolve_multiple_values='drop',
            post_extraction_commands=(
                ('method', 'strip', (' :\t',)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=Features).*', '$source')),),
            var_name='CPU Features', var_dict_1='CPU', var_dict_2='_info', resolve_multiple_values='drop',
            post_extraction_commands=(
                ('method', 'strip', (' :\t',)),)),
    ),
    (("cat", "/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq"), (("as_list", False), ("return_output", True)), "cpu_freq"): (
        InfoSpec(
            var_name='Max Frequency', var_dict_1='CPU', var_dict_2='_info',
            post_extraction_commands=(
                ('function', int, ('$extracted',)),
                ('method', '__floordiv__', (1000,)),
                ('function', str, ('$extracted',)),
                ('method', "__add__", (' MHz',)))),
    ),
    (("cat", "/sys/devices/system/cpu/possible"), (("as_list", False), ("return_output", True)), "cpu_cores"): (
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=-).*', '$source')),
                (re.search, ('.*', '$source'))),
            var_name='Cores', var_dict_1='CPU', var_dict_2='_info', resolve_multiple_values='drop',
            post_extraction_commands=(
                ('function', lambda x: int(x) + 1, ('$extracted',)),
                ('function', str, ('$extracted',)))),
    ),
    (("cat", "/proc/version"), (("as_list", False), ("return_output", True)), "kernel_version"): (
        InfoSpec(
            var_name='Kernel Version', var_dict_1='OS', var_dict_2='_info',),
    ),
    (("cat", "/proc/meminfo"), (("as_list", False), ("return_output", True)), "meminfo") : (
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=^MemTotal:)[^A-z]*', '$source')),),
            var_name='Total', var_dict_1='RAM', var_dict_2='_info',
            post_extraction_commands=(
                ('function', int, ('$extracted',)),
                ('method', '__floordiv__', (1024,)),
                ('function', str, ('$extracted',)),
                ('method', '__add__', (' MB',)))),
    ),
    (("printenv",), (("as_list", False), ("return_output", True)), "shell_environment") :(
        InfoSpec(
            extraction_commands=(
                (re.search, ("(?<=EXTERNAL_STORAGE=).*", "$source")),),
            var_name="internal_sd_path", resolve_existing_values="drop"),
        InfoSpec(
            extraction_commands=(
                (re.search, ("(?<=SECONDARY_STORAGE=).*", "$source")),),
            var_name="external_sd_path", resolve_existing_values="drop"),
    ),
    (("ls", "/system/bin"), (('as_list', True), ("return_output", True)), "available_commands") :(
        InfoSpec(
            var_name='available_commands', resolve_existing_values='replace'),
    ),
    (("pm", "list", "features"), (('as_list', False), ("return_output", True)), "device_features") :(
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=feature:)android.hardware.bluetooth', '$source')),),
            var_name="Bluetooth", var_dict_1='Notable Features', var_dict_2='_info',
            post_extraction_commands=(
                ('function', str, (u"\u2714",)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=feature:)android.hardware.bluetooth_le', '$source')),),
            var_name="Bluetooth Low Energy", var_dict_1='Notable Features', var_dict_2='_info',
            post_extraction_commands=(
                ('function', str, (u"\u2714",)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=feature:)android.hardware.consumerir', '$source')),),
            var_name="Infrared", var_dict_1='Notable Features', var_dict_2='_info',
            post_extraction_commands=(
                ('function', str, (u"\u2714",)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=feature:)android.hardware.fingerprint', '$source')),),
            var_name="Fingerprint Scanner", var_dict_1='Notable Features', var_dict_2='_info',
            post_extraction_commands=(
                ('function', str, (u"\u2714",)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=feature:)android.software.freeform_window_management', '$source')),),
            var_name="Freeform Window Management", var_dict_1='Notable Features', var_dict_2='_info',
            post_extraction_commands=(
                ('function', str, (u"\u2714",)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=feature:)android.hardware.nfc', '$source')),),
            var_name="NFC", var_dict_1='Notable Features', var_dict_2='_info',
            post_extraction_commands=(
                ('function', str, (u"\u2714",)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=feature:)android.hardware.telephony.cdma', '$source')),),
            var_name="CDMA Telephony", var_dict_1='Notable Features', var_dict_2='_info',
            post_extraction_commands=(
                ('function', str, (u"\u2714",)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=feature:)android.hardware.telephony.gsm', '$source')),),
            var_name="GSM Telephony", var_dict_1='Notable Features', var_dict_2='_info',
            post_extraction_commands=(
                ('function', str, (u"\u2714",)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=feature:)android.hardware.vr.headtracking', '$source')),),
            var_name="VR Headtracking", var_dict_1='Notable Features', var_dict_2='_info',
            post_extraction_commands=(
                ('function', str, (u"\u2714",)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=feature:)android.software.vr.mode', '$source')),),
            var_name="VR Mode", var_dict_1='Notable Features', var_dict_2='_info',
            post_extraction_commands=(
                ('function', str, (u"\u2714",)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=feature:)android.hardware.vr.high_performance', '$source')),),
            var_name="High-Performance VR Mode", var_dict_1='Notable Features', var_dict_2='_info',
            post_extraction_commands=(
                ('function', str, (u"\u2714",)),)),
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=feature:)android.hardware.wifi.aware', '$source')),),
            var_name="WiFi-Aware", var_dict_1='Notable Features', var_dict_2='_info',
            post_extraction_commands=(
                ('function', str, (u"\u2714",)),)),
        InfoSpec(
            extraction_commands=(
                (re.findall, ('((?<=feature:).*?)\r', '$source')),),
            var_name='device_features'),
    ),
    (("pm", "list", "packages", "-s"), (('as_list', False), ("return_output", True)), "system_apps") :(
        InfoSpec(
            extraction_commands=(
                (re.findall, ('((?<=package:).*?)\r', '$source')),),
            var_name='system_apps', resolve_existing_values='replace'),
    ),
    (("pm", "list", "packages", "-3"), (('as_list', False), ("return_output", True)), "thirdparty_apps") :(
        InfoSpec(
            extraction_commands=(
                (re.findall, ('((?<=package:).*?)\r', '$source')),),
            var_name='thirdparty_apps', resolve_existing_values='replace'),
    ),
    (("wm", "size"), (('as_list', False), ("return_output", True)), "screen_size") :(
        InfoSpec(
            extraction_commands=(
                (re.search, ('(?<=Physical size:).*', '$source')),),
            var_name='Resolution', var_dict_1='Display', var_dict_2='_info', resolve_existing_values='drop'),
    ),
    (("wm", "density"), (('as_list', False), ("return_output", True)), "screen_density") :(
        InfoSpec(
            extraction_commands=(
                (re.search, ("(?<=Physical density:).*", '$source')),),
            var_name='Density', var_dict_1='Display', var_dict_2='_info', resolve_existing_values='drop'),
    ),
    (("cat", "/system/build.prop"), (('as_list', False), ("return_output", True)), "build.prop") :(
        # this is here only to be picked up during debug helper device dumps
    ),
    (("dumpsys",), (('as_list', False), ("return_output", True)), "dumpsys_services") :(
        # this is here only to be picked up during debug helper device dumps
    ),
}
