#         Android QA Helper - helping you test Android apps!
#          Copyright (C) 2017  rmmbear
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program. If not, see <http://www.gnu.org/licenses/>.

"""Interactive terminal prompt for Helper.

Mostly broken - work in progress.
Bless this mess.
"""

from string import printable as printable_chars
import os
import helper


def cls():
    """CLS
    """
    if os.name == "nt":
        command = "cls"
    else:
        command = "clear"

    os.system(command)


def interactive_loop():
    """Helper interactive loop.
    """

    cls()
    print(helper.VERSION_STRING)
    print(helper.SOURCE_STRING)

    last_action = ''
    actions = {"I":{"name":"Installling",
                    "action":helper.install},
               "R":{"name":"Recording",
                    "action":helper.record}
              }

    while True:
        print("")
        current_devices = helper.get_devices()
        if current_devices:
            if len(current_devices) == 1:
                print("There is currently one device connected:")
            else:
                print("There are currently", len(current_devices),
                      "devices connected:")

            for device in current_devices:
                device.print_basic_info()
                print("")

        print("'I' - Begin [I]nstallation process")
        print("'R' - Start screen [R]ecording")
        print("'C' - [C]lean device")
        print("'T' - Pull ANR log / dalvik vm [T]race file")
        print("Press enter to search for devices")

        print("\n", last_action, "\n", sep="")
        user_choice = input("> ").upper().strip()

        sanitized_choice = ""
        for char in user_choice:
            if char in printable_chars:
                sanitized_choice += char
            else:
                sanitized_choice += "?"

        if sanitized_choice not in actions:
            last_action = "".join(['"', sanitized_choice, '"',
                                   " is not a valid option!"])
            cls()
            continue

        last_action = actions[user_choice]["name"]
        try:
            actions[user_choice]["action"].__call__()
            print(actions[user_choice]["action"])
        except Exception as err:
            print(*err.args)

        input("Press enter to continue")

        raise NotImplementedError("Interactive loop not yet fully written.")

        cls()
