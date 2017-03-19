# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file '/home/mac/Desktop/Helper_GUI/helper/GUI/source_ui/device_tab.ui'
#
# Created by: PyQt5 UI code generator 5.8.1
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_Form(object):
    def setupUi(self, Form):
        Form.setObjectName("Form")
        Form.resize(641, 480)
        self.horizontalLayout = QtWidgets.QHBoxLayout(Form)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.control_panel = QtWidgets.QFrame(Form)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.control_panel.sizePolicy().hasHeightForWidth())
        self.control_panel.setSizePolicy(sizePolicy)
        self.control_panel.setMinimumSize(QtCore.QSize(90, 0))
        self.control_panel.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.control_panel.setFrameShadow(QtWidgets.QFrame.Raised)
        self.control_panel.setObjectName("control_panel")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.control_panel)
        self.verticalLayout.setContentsMargins(5, -1, 5, -1)
        self.verticalLayout.setObjectName("verticalLayout")
        self.install_button = QtWidgets.QPushButton(self.control_panel)
        self.install_button.setMinimumSize(QtCore.QSize(125, 0))
        self.install_button.setFocusPolicy(QtCore.Qt.NoFocus)
        self.install_button.setObjectName("install_button")
        self.verticalLayout.addWidget(self.install_button)
        self.record_button = QtWidgets.QPushButton(self.control_panel)
        self.record_button.setFocusPolicy(QtCore.Qt.NoFocus)
        self.record_button.setObjectName("record_button")
        self.verticalLayout.addWidget(self.record_button)
        self.traces_button = QtWidgets.QPushButton(self.control_panel)
        self.traces_button.setFocusPolicy(QtCore.Qt.NoFocus)
        self.traces_button.setObjectName("traces_button")
        self.verticalLayout.addWidget(self.traces_button)
        self.clean_button = QtWidgets.QPushButton(self.control_panel)
        self.clean_button.setFocusPolicy(QtCore.Qt.NoFocus)
        self.clean_button.setObjectName("clean_button")
        self.verticalLayout.addWidget(self.clean_button)
        spacerItem = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout.addItem(spacerItem)
        self.horizontalLayout.addWidget(self.control_panel)
        self.device_display = QtWidgets.QTabWidget(Form)
        self.device_display.setTabPosition(QtWidgets.QTabWidget.East)
        self.device_display.setObjectName("device_display")
        self.device_info_tab = QtWidgets.QWidget()
        self.device_info_tab.setObjectName("device_info_tab")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout(self.device_info_tab)
        self.horizontalLayout_2.setContentsMargins(3, 3, 3, 3)
        self.horizontalLayout_2.setSpacing(0)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.device_info = QtWidgets.QTextBrowser(self.device_info_tab)
        self.device_info.setFocusPolicy(QtCore.Qt.NoFocus)
        self.device_info.setStyleSheet("")
        self.device_info.setTextInteractionFlags(QtCore.Qt.LinksAccessibleByKeyboard|QtCore.Qt.LinksAccessibleByMouse|QtCore.Qt.TextBrowserInteraction|QtCore.Qt.TextSelectableByKeyboard|QtCore.Qt.TextSelectableByMouse)
        self.device_info.setObjectName("device_info")
        self.horizontalLayout_2.addWidget(self.device_info)
        self.device_display.addTab(self.device_info_tab, "")
        self.device_console_tab = QtWidgets.QWidget()
        self.device_console_tab.setObjectName("device_console_tab")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.device_console_tab)
        self.verticalLayout_2.setContentsMargins(3, 3, 3, 3)
        self.verticalLayout_2.setSpacing(0)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.device_console = QtWidgets.QTextBrowser(self.device_console_tab)
        self.device_console.setObjectName("device_console")
        self.verticalLayout_2.addWidget(self.device_console)
        self.device_display.addTab(self.device_console_tab, "")
        self.horizontalLayout.addWidget(self.device_display)
        spacerItem1 = QtWidgets.QSpacerItem(0, 20, QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem1)

        self.retranslateUi(Form)
        self.device_display.setCurrentIndex(0)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        _translate = QtCore.QCoreApplication.translate
        Form.setWindowTitle(_translate("Form", "Form"))
        self.install_button.setText(_translate("Form", "Install"))
        self.record_button.setText(_translate("Form", "Record Screen"))
        self.traces_button.setText(_translate("Form", "Pull Traces"))
        self.clean_button.setText(_translate("Form", "Clean"))
        self.device_info.setHtml(_translate("Form", "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" \"http://www.w3.org/TR/REC-html40/strict.dtd\">\n"
"<html><head><meta name=\"qrichtext\" content=\"1\" /><style type=\"text/css\">\n"
"p, li { white-space: pre-wrap; }\n"
"</style></head><body style=\" font-family:\'Droid Sans\'; font-size:10pt; font-weight:400; font-style:normal;\">\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">Product:</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">    Model: Q-SMART</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">    Name: myPhone</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">    Manufacturer: myPhone</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">    Brand: myPhone</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">    Device: myPhone</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">OS:</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">    Android Version: 4.4.2</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">    Android API Level: 19</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">    Build ID: KOT49H</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">    Build Fingerprint: myPhone/myPhone/myPhone:4.4.2/KOT49H/1409822800:user/test-keys</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">RAM:</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">    Total: 965 MB</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">CPU:</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">    Chipset: MT6582</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">    Processor: ARMv7 Processor rev 3 (v7l)</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">    Cores: 4</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">    Architecture: 32bit (ARM)</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">    Max Frequency: 1300.0 MHz</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">    Available ABIs: armeabi, armeabi-v7a</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">GPU:</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">    Model: ARM Mali-400 MP</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">    GL Version: OpenGL ES 2.0</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">    Compression Types: ETC1</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">Display:</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">    Resolution: 480x854</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">    Refresh-rate: 59.390002 fps</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">    V-Sync: disabled</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">    Soft V-Sync: disabled</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">    Density: 240</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">    X-DPI: 240.000000</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">    Y-DPI: 240.000000</p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><br /></p></body></html>"))
        self.device_display.setTabText(self.device_display.indexOf(self.device_info_tab), _translate("Form", "Device Information"))
        self.device_display.setTabText(self.device_display.indexOf(self.device_console_tab), _translate("Form", "Console"))

