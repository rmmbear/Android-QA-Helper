# -*- coding: utf-8 -*-

# Created by: PyQt5 UI code generator 5.8.1
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(550, 650)
        MainWindow.setMinimumSize(QtCore.QSize(525, 500))
        MainWindow.setStyleSheet("")
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self._3 = QtWidgets.QVBoxLayout(self.centralwidget)
        self._3.setContentsMargins(0, 0, 0, 0)
        self._3.setSpacing(0)
        self._3.setObjectName("_3")
        self.device_container = QtWidgets.QTabWidget(self.centralwidget)
        self.device_container.setObjectName("device_container")
        self.empty_tab = QtWidgets.QWidget()
        self.empty_tab.setObjectName("empty_tab")
        self._2 = QtWidgets.QGridLayout(self.empty_tab)
        self._2.setContentsMargins(0, 0, 0, 0)
        self._2.setObjectName("_2")
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self._2.addItem(spacerItem, 3, 3, 1, 1)
        spacerItem1 = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self._2.addItem(spacerItem1, 7, 2, 1, 1)
        self.label_description = QtWidgets.QLabel(self.empty_tab)
        self.label_description.setAlignment(QtCore.Qt.AlignCenter)
        self.label_description.setWordWrap(True)
        self.label_description.setObjectName("label_description")
        self._2.addWidget(self.label_description, 3, 2, 1, 1)
        spacerItem2 = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self._2.addItem(spacerItem2, 1, 2, 1, 1)
        self.status_console = QtWidgets.QTextBrowser(self.empty_tab)
        self.status_console.setFocusPolicy(QtCore.Qt.NoFocus)
        self.status_console.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.status_console.setObjectName("status_console")
        self._2.addWidget(self.status_console, 6, 1, 1, 3)
        spacerItem3 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self._2.addItem(spacerItem3, 3, 1, 1, 1)
        self.label_icon = QtWidgets.QLabel(self.empty_tab)
        self.label_icon.setPixmap(QtGui.QPixmap(":/misc_icons/images/close-pressed.png"))
        self.label_icon.setAlignment(QtCore.Qt.AlignCenter)
        self.label_icon.setObjectName("label_icon")
        self._2.addWidget(self.label_icon, 2, 2, 1, 1)
        spacerItem4 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self._2.addItem(spacerItem4, 3, 0, 1, 1)
        spacerItem5 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self._2.addItem(spacerItem5, 3, 4, 1, 1)
        self.device_container.addTab(self.empty_tab, "")
        self._3.addWidget(self.device_container)
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setObjectName("menubar")
        self.about_menu = QtWidgets.QMenu(self.menubar)
        self.about_menu.setObjectName("about_menu")
        self.config_menu = QtWidgets.QMenu(self.menubar)
        self.config_menu.setObjectName("config_menu")
        MainWindow.setMenuBar(self.menubar)
        self.menubar.addAction(self.config_menu.menuAction())
        self.menubar.addAction(self.about_menu.menuAction())

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "Android Helper"))
        self.label_description.setText(_translate("MainWindow", "There are currently no devices connected, please check your USB connection."))
        self.device_container.setTabText(self.device_container.indexOf(self.empty_tab), _translate("MainWindow", "No devices"))
        self.about_menu.setTitle(_translate("MainWindow", "About"))
        self.config_menu.setTitle(_translate("MainWindow", "Configuration"))

from helper.GUI import icons_rc
