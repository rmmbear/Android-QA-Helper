# Android-QA-Helper
For changelog and Windows binaries see releases page: https://github.com/rmmbear/Android-QA-Helper/releases/

# Requirements:
- Python 3.6 (if not using binary package)
- PyQt5 and QT 5.8 (if not using binary package)
- pytest (for tests)
- ADB (can be found in platform-tools from Android SDK)
- AAPT (can be found in build-tools from Android SDK)

Both ADB and AAPT are required for this program to work. To get them, you can do one of two things:
- Download the whole Android SDK suite and get their packages using the 'Android SDK manager'
- Download the packages directly from Google's Android repository

While the first option is pretty straight-forward, it may be quite an overkill to install the whole SDK, when you only need two files. To download the packages directly go to https://dl-ssl.google.com/android/repository/repository-11.xml the link points to an xml tree, which contains an overview of the whole (publicly available) Android repository (this file is what the Android SDK manager uses internally to find new packages and updates).

To download the platform-tools package, search for ```<sdk:url>platform-tools```, find the package corresponding to your platform, copy the url and replace the last part of the page's url with it. At the time of writing, this would be https://dl-ssl.google.com/android/repository/platform-tools_r25.0.3-linux.zip .
Do the same for build-tools: search for ```<sdk:url>build-tools```, find your platform, replace the last part of the page's url with the found url and download (at the time of writing: https://dl-ssl.google.com/android/repository/build-tools_r25.0.2-linux.zip).

# Installation:
Download or clone this repository using ```git clone``` (if you are on windows, you can also download the frozen code from the [realeases page](https://github.com/rmmbear/Android-QA-Helper/releases)).

In the root directory of the project there should be two directories: "adb" and "aapt". Place the adb (and its dlls, if on windows) and aapt into their corresponding directories. See requirements section on instructions how to get them.

# Usage:
From the root of the project:```python -m helper <option>```. You can use ```--help``` to see the list of available options.
If you're using the frozen code package on windows, you must call the 'helper.exe' from command line, since helper is a command-line only utility (for now). 

# GUI:
The current GUI prototype can be accessed with ```helper --gui```
It currently has the following functionality:
- Automatic device detection
- Recording (press button in a device tab to start recording, press it again to stop)
- Installing (only through drag & drop, the 'install' button currently does nothing)
- Cleaning (press 'clean' button WARNING: this may be destructive and there currently is no confirmation dialog)
- Pulling traces file / anr log (just press the 'pull traces' button)


# Current plans:
- Finish GUI
- Clean up the code some more
- Extend cleaning to support user-defined commands *-- not for 1.0*
- Plan new functionality (screenshots? functions enabling doze/standby for testing? recovering apks of installed apps from asec directory?) *-- not for 1.0*
