# Android-QA-Helper
Android QA Helper is a collection of utilities for Android devices. As the name implies, the project was meant to help with tasks often needed in QA on mobile devices (automated installation, gathering logs and device information, automated cleaning, etc.).

# Functionality:
- Extract device information into a file in human-readable format (system info, GPU, CPU, storage, installed apps, hardware capabilities, and more!)
- Install and remove apps (with support for OBB files, built-in compatibility checks)
- View app requirements, used permissionsand compatibility info extracted from the apk's AndroidManifest.xml
- Record your device's screen and automatically pull videos and screenshots to your pc
- ToolGrabber utility which automatically downloads adb and aapt from Android project repository

Planned:
- Cleaner utility with extensible config, allowing you to remove files, apps, clear app data from connected devices
- View and save live system logs

# Usage:
Download or clone this repository using ```git clone``` (frozen code package for windows can be found on [releases page](https://github.com/rmmbear/Android-QA-Helper/releases)). From the root of the project:```python -m helper <option>```. Use ```--help``` to see the list of available commands.
If you're using the frozen code package on windows, you must use call 'helper.exe' from cmd and not use the exe directly.

# Requirements:
- Python 3.6
- [requests](https://requests.kennethreitz.org/en/master/) [used in toolgrabber]

# Getting AAPT and ADB
Both ADB and AAPT are required for this program to work. A ToolGrabber utility is included in the project, which will automatically download necessary packages from Android project repositories and extract the required tools. Simply run it on the command line If you prefer, you can also:
- Download the latest release of platform-tools (which contains adb only) from https://developer.android.com/studio/releases/platform-tools#downloads
- Download the whole Android SDK suite and get platform-tools (adb) and build-tools (aapt) using the SDK manager
- Download the packages directly from Google's Android repositories (listing can be found in xml form at https://dl-ssl.google.com/android/repository/repository-12.xml)


