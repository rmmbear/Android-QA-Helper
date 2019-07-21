import sys
from cx_Freeze import setup, Executable

from helper import VERSION

options = {
    "build_exe": {
        "excludes": ["tkinter"],
        "optimize": 2,
        "path": sys.path + ["helper", "helper/tools"],
        # adding multiprocessing resolves issues with queue module not being available for requests
        # this adds about 0.8MB to the final package size
        "packages": ["multiprocessing"]
    },
}

executables = (
    Executable("./helper/tools/tool_grabber.py"),
    Executable("./helper/apk.py", targetName="app_inspector"),
    Executable("./helper/__main__.py", targetName="helper"),
)

setup(
    name="Android QA Helper",
    version=VERSION,
    options=options,
    executables=executables
)
