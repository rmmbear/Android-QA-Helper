# Android-QA-Helper
For changelog and Windows binaries see releases page: https://github.com/rmmbear/Android-QA-Helper/releases/

# Requirements:
- Python 3.6 (if not using binary package)
- ADB
- AAPT
- PyQt5 [optional - GUI]
- pytest [optyional - for tests]

# Getting AAPT and ADB
Both ADB and AAPT are required for this program to work. To get them, you can do one of two things:
- Download the whole Android SDK suite and get their packages using the SDK manager
- Download the latest release of platform-tools (ADB) package from https://developer.android.com/studio/releases/platform-tools#downloads
- Download the packages directly from Google's Android repositories


To download the platform-tools package, search for ```<sdk:url>platform-tools```, find the package corresponding to your platform, copy the url and replace the last part of the page's url with it. At the time of writing, this would be https://dl-ssl.google.com/android/repository/platform-tools_r25.0.3-linux.zip .
Do the same for build-tools: search for ```<sdk:url>build-tools```, find your platform, replace the last part of the page's url with the found url and download (at the time of writing: https://dl-ssl.google.com/android/repository/build-tools_r25.0.2-linux.zip).

# Installation:
Download or clone this repository using ```git clone``` (if you are on windows, you can also download the frozen code from the [releases page](https://github.com/rmmbear/Android-QA-Helper/releases)).

In the root directory of the project there should be two directories: "adb" and "aapt". Place the adb (and its dlls, if on windows) and aapt into their corresponding directories. See requirements section on instructions how to get them.

# Usage:
From the root of the project:```python -m helper <option>```. You can use ```--help``` to see the list of available options.
If you're using the frozen code package on windows, you must call the 'helper.exe' from cmd.


# Functionality:
- Extract info about connected devices
- Record videos
- Read ANR logs
- Read logcat logs
- Install remove apps (with obbs)
- Extract app files from device
- Test app/device compatibility



# GUI:
The current GUI prototype can be accessed with ```helper gui```
