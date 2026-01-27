# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'mainwindow.ui'
##
## Created by: Qt User Interface Compiler version 6.10.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QApplication, QComboBox, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMenu, QMenuBar,
    QProgressBar, QPushButton, QSizePolicy, QSlider,
    QStatusBar, QTextEdit, QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(914, 733)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.verticalLayoutWidget = QWidget(self.centralwidget)
        self.verticalLayoutWidget.setObjectName(u"verticalLayoutWidget")
        self.verticalLayoutWidget.setGeometry(QRect(20, 300, 871, 31))
        self.mainLayout = QVBoxLayout(self.verticalLayoutWidget)
        self.mainLayout.setObjectName(u"mainLayout")
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.label = QLabel(self.verticalLayoutWidget)
        self.label.setObjectName(u"label")

        self.horizontalLayout_2.addWidget(self.label)

        self.inputFileEdit = QLineEdit(self.verticalLayoutWidget)
        self.inputFileEdit.setObjectName(u"inputFileEdit")
        self.inputFileEdit.setReadOnly(True)

        self.horizontalLayout_2.addWidget(self.inputFileEdit)

        self.browseButton = QPushButton(self.verticalLayoutWidget)
        self.browseButton.setObjectName(u"browseButton")

        self.horizontalLayout_2.addWidget(self.browseButton)


        self.mainLayout.addLayout(self.horizontalLayout_2)

        self.horizontalLayoutWidget_2 = QWidget(self.centralwidget)
        self.horizontalLayoutWidget_2.setObjectName(u"horizontalLayoutWidget_2")
        self.horizontalLayoutWidget_2.setGeometry(QRect(20, 340, 135, 31))
        self.horizontalLayout_3 = QHBoxLayout(self.horizontalLayoutWidget_2)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.label_2 = QLabel(self.horizontalLayoutWidget_2)
        self.label_2.setObjectName(u"label_2")

        self.horizontalLayout_3.addWidget(self.label_2)

        self.codecCombo = QComboBox(self.horizontalLayoutWidget_2)
        self.codecCombo.addItem("")
        self.codecCombo.addItem("")
        self.codecCombo.addItem("")
        self.codecCombo.setObjectName(u"codecCombo")

        self.horizontalLayout_3.addWidget(self.codecCombo)

        self.horizontalLayoutWidget_3 = QWidget(self.centralwidget)
        self.horizontalLayoutWidget_3.setObjectName(u"horizontalLayoutWidget_3")
        self.horizontalLayoutWidget_3.setGeometry(QRect(170, 340, 171, 31))
        self.horizontalLayout_4 = QHBoxLayout(self.horizontalLayoutWidget_3)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.label_3 = QLabel(self.horizontalLayoutWidget_3)
        self.label_3.setObjectName(u"label_3")

        self.horizontalLayout_4.addWidget(self.label_3)

        self.containerCombo = QComboBox(self.horizontalLayoutWidget_3)
        self.containerCombo.addItem("")
        self.containerCombo.addItem("")
        self.containerCombo.setObjectName(u"containerCombo")

        self.horizontalLayout_4.addWidget(self.containerCombo)

        self.horizontalLayout_4.setStretch(1, 1)
        self.horizontalLayoutWidget_4 = QWidget(self.centralwidget)
        self.horizontalLayoutWidget_4.setObjectName(u"horizontalLayoutWidget_4")
        self.horizontalLayoutWidget_4.setGeometry(QRect(360, 340, 171, 31))
        self.horizontalLayout_5 = QHBoxLayout(self.horizontalLayoutWidget_4)
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.horizontalLayout_5.setContentsMargins(0, 0, 0, 0)
        self.label_4 = QLabel(self.horizontalLayoutWidget_4)
        self.label_4.setObjectName(u"label_4")

        self.horizontalLayout_5.addWidget(self.label_4)

        self.resolutionCombo = QComboBox(self.horizontalLayoutWidget_4)
        self.resolutionCombo.addItem("")
        self.resolutionCombo.addItem("")
        self.resolutionCombo.addItem("")
        self.resolutionCombo.addItem("")
        self.resolutionCombo.setObjectName(u"resolutionCombo")

        self.horizontalLayout_5.addWidget(self.resolutionCombo)

        self.horizontalLayout_5.setStretch(1, 1)
        self.horizontalLayoutWidget_5 = QWidget(self.centralwidget)
        self.horizontalLayoutWidget_5.setObjectName(u"horizontalLayoutWidget_5")
        self.horizontalLayoutWidget_5.setGeometry(QRect(650, 340, 237, 31))
        self.horizontalLayout_6 = QHBoxLayout(self.horizontalLayoutWidget_5)
        self.horizontalLayout_6.setObjectName(u"horizontalLayout_6")
        self.horizontalLayout_6.setContentsMargins(0, 0, 0, 0)
        self.label_5 = QLabel(self.horizontalLayoutWidget_5)
        self.label_5.setObjectName(u"label_5")
        self.label_5.setEnabled(True)

        self.horizontalLayout_6.addWidget(self.label_5)

        self.customResolutionEdit = QLineEdit(self.horizontalLayoutWidget_5)
        self.customResolutionEdit.setObjectName(u"customResolutionEdit")
        self.customResolutionEdit.setEnabled(True)

        self.horizontalLayout_6.addWidget(self.customResolutionEdit)

        self.label_6 = QLabel(self.centralwidget)
        self.label_6.setObjectName(u"label_6")
        self.label_6.setGeometry(QRect(20, 370, 131, 20))
        self.horizontalLayoutWidget_6 = QWidget(self.centralwidget)
        self.horizontalLayoutWidget_6.setObjectName(u"horizontalLayoutWidget_6")
        self.horizontalLayoutWidget_6.setGeometry(QRect(20, 390, 871, 73))
        self.horizontalLayout_7 = QHBoxLayout(self.horizontalLayoutWidget_6)
        self.horizontalLayout_7.setObjectName(u"horizontalLayout_7")
        self.horizontalLayout_7.setContentsMargins(0, 0, 0, 0)
        self.commandDisplay = QTextEdit(self.horizontalLayoutWidget_6)
        self.commandDisplay.setObjectName(u"commandDisplay")
        self.commandDisplay.setMaximumSize(QSize(16777215, 80))
        self.commandDisplay.setStyleSheet(u"background-color: #f0f0f0; font-family: Consolas;")
        self.commandDisplay.setReadOnly(False)

        self.horizontalLayout_7.addWidget(self.commandDisplay)

        self.copyCmdButton = QPushButton(self.horizontalLayoutWidget_6)
        self.copyCmdButton.setObjectName(u"copyCmdButton")

        self.horizontalLayout_7.addWidget(self.copyCmdButton)

        self.horizontalLayoutWidget_7 = QWidget(self.centralwidget)
        self.horizontalLayoutWidget_7.setObjectName(u"horizontalLayoutWidget_7")
        self.horizontalLayoutWidget_7.setGeometry(QRect(20, 500, 871, 41))
        self.horizontalLayout_8 = QHBoxLayout(self.horizontalLayoutWidget_7)
        self.horizontalLayout_8.setObjectName(u"horizontalLayout_8")
        self.horizontalLayout_8.setContentsMargins(0, 0, 0, 0)
        self.runButton = QPushButton(self.horizontalLayoutWidget_7)
        self.runButton.setObjectName(u"runButton")
        self.runButton.setStyleSheet(u"background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")

        self.horizontalLayout_8.addWidget(self.runButton)

        self.pauseResumeButton = QPushButton(self.horizontalLayoutWidget_7)
        self.pauseResumeButton.setObjectName(u"pauseResumeButton")
        self.pauseResumeButton.setEnabled(False)

        self.horizontalLayout_8.addWidget(self.pauseResumeButton)

        self.savePresetButton = QPushButton(self.horizontalLayoutWidget_7)
        self.savePresetButton.setObjectName(u"savePresetButton")

        self.horizontalLayout_8.addWidget(self.savePresetButton)

        self.loadPresetButton = QPushButton(self.horizontalLayoutWidget_7)
        self.loadPresetButton.setObjectName(u"loadPresetButton")

        self.horizontalLayout_8.addWidget(self.loadPresetButton)

        self.deletePresetButton = QPushButton(self.horizontalLayoutWidget_7)
        self.deletePresetButton.setObjectName(u"deletePresetButton")

        self.horizontalLayout_8.addWidget(self.deletePresetButton)

        self.exportPresetButton = QPushButton(self.horizontalLayoutWidget_7)
        self.exportPresetButton.setObjectName(u"exportPresetButton")

        self.horizontalLayout_8.addWidget(self.exportPresetButton)

        self.importPresetButton = QPushButton(self.horizontalLayoutWidget_7)
        self.importPresetButton.setObjectName(u"importPresetButton")

        self.horizontalLayout_8.addWidget(self.importPresetButton)

        self.label_7 = QLabel(self.centralwidget)
        self.label_7.setObjectName(u"label_7")
        self.label_7.setGeometry(QRect(20, 560, 131, 20))
        self.logDisplay = QTextEdit(self.centralwidget)
        self.logDisplay.setObjectName(u"logDisplay")
        self.logDisplay.setGeometry(QRect(20, 580, 871, 101))
        self.logDisplay.setReadOnly(True)
        self.openOutputFolderButton = QPushButton(self.centralwidget)
        self.openOutputFolderButton.setObjectName(u"openOutputFolderButton")
        self.openOutputFolderButton.setEnabled(False)
        self.openOutputFolderButton.setGeometry(QRect(20, 540, 151, 24))
        self.widget = QWidget(self.centralwidget)
        self.widget.setObjectName(u"widget")
        self.widget.setGeometry(QRect(10, -40, 120, 80))
        self.videoPreviewContainer = QWidget(self.centralwidget)
        self.videoPreviewContainer.setObjectName(u"videoPreviewContainer")
        self.videoPreviewContainer.setGeometry(QRect(270, 10, 401, 281))
        self.verticalLayoutWidget_2 = QWidget(self.videoPreviewContainer)
        self.verticalLayoutWidget_2.setObjectName(u"verticalLayoutWidget_2")
        self.verticalLayoutWidget_2.setGeometry(QRect(0, 0, 401, 281))
        self.verticalLayout = QVBoxLayout(self.verticalLayoutWidget_2)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.videoPreviewWidget = QWidget(self.verticalLayoutWidget_2)
        self.videoPreviewWidget.setObjectName(u"videoPreviewWidget")
        self.videoPreviewWidget.setMaximumSize(QSize(400, 300))
        self.videoPreviewWidget.setStyleSheet(u"border: 1px solid #cccccc; background-color: #000000;")

        self.verticalLayout.addWidget(self.videoPreviewWidget)

        self.videoTimelineSlider = QSlider(self.verticalLayoutWidget_2)
        self.videoTimelineSlider.setObjectName(u"videoTimelineSlider")
        self.videoTimelineSlider.setMaximum(10000)
        self.videoTimelineSlider.setOrientation(Qt.Orientation.Horizontal)

        self.verticalLayout.addWidget(self.videoTimelineSlider)

        self.videoControlsLayout = QHBoxLayout()
        self.videoControlsLayout.setSpacing(4)
        self.videoControlsLayout.setObjectName(u"videoControlsLayout")
        self.videoPlayButton = QPushButton(self.verticalLayoutWidget_2)
        self.videoPlayButton.setObjectName(u"videoPlayButton")

        self.videoControlsLayout.addWidget(self.videoPlayButton)

        self.videoStopButton = QPushButton(self.verticalLayoutWidget_2)
        self.videoStopButton.setObjectName(u"videoStopButton")

        self.videoControlsLayout.addWidget(self.videoStopButton)

        self.videoTimeLabel = QLabel(self.verticalLayoutWidget_2)
        self.videoTimeLabel.setObjectName(u"videoTimeLabel")

        self.videoControlsLayout.addWidget(self.videoTimeLabel)

        self.videoMuteButton = QPushButton(self.verticalLayoutWidget_2)
        self.videoMuteButton.setObjectName(u"videoMuteButton")

        self.videoControlsLayout.addWidget(self.videoMuteButton)

        self.videoControlsLayout.setStretch(0, 2)
        self.videoControlsLayout.setStretch(1, 2)

        self.verticalLayout.addLayout(self.videoControlsLayout)

        self.verticalLayout.setStretch(0, 6)
        self.verticalLayout.setStretch(1, 2)
        self.verticalLayout.setStretch(2, 1)
        self.encodingProgressBar = QProgressBar(self.centralwidget)
        self.encodingProgressBar.setObjectName(u"encodingProgressBar")
        self.encodingProgressBar.setGeometry(QRect(20, 470, 871, 23))
        self.encodingProgressBar.setValue(0)
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 914, 22))
        self.menumainwindow = QMenu(self.menubar)
        self.menumainwindow.setObjectName(u"menumainwindow")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.menubar.addAction(self.menumainwindow.menuAction())

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"MainWindow", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"\u0412\u0445\u043e\u0434\u043d\u043e\u0439 \u0444\u0430\u0439\u043b:", None))
        self.browseButton.setText(QCoreApplication.translate("MainWindow", u"\u041e\u0431\u0437\u043e\u0440...", None))
        self.label_2.setText(QCoreApplication.translate("MainWindow", u"\u041a\u043e\u0434\u0435\u043a:", None))
        self.codecCombo.setItemText(0, QCoreApplication.translate("MainWindow", u"libx264", None))
        self.codecCombo.setItemText(1, QCoreApplication.translate("MainWindow", u"libx265", None))
        self.codecCombo.setItemText(2, QCoreApplication.translate("MainWindow", u"copy", None))

        self.label_3.setText(QCoreApplication.translate("MainWindow", u"\u041a\u043e\u043d\u0442\u0435\u0439\u043d\u0435\u0440:", None))
        self.containerCombo.setItemText(0, QCoreApplication.translate("MainWindow", u"mp4", None))
        self.containerCombo.setItemText(1, QCoreApplication.translate("MainWindow", u"mkv", None))

        self.label_4.setText(QCoreApplication.translate("MainWindow", u"\u0420\u0430\u0437\u0440\u0435\u0448\u0435\u043d\u0438\u0435:", None))
        self.resolutionCombo.setItemText(0, QCoreApplication.translate("MainWindow", u"480p", None))
        self.resolutionCombo.setItemText(1, QCoreApplication.translate("MainWindow", u"720p", None))
        self.resolutionCombo.setItemText(2, QCoreApplication.translate("MainWindow", u"1080p", None))
        self.resolutionCombo.setItemText(3, QCoreApplication.translate("MainWindow", u"custom", None))

        self.label_5.setText(QCoreApplication.translate("MainWindow", u"Custom (width:height):", None))
        self.customResolutionEdit.setPlaceholderText(QCoreApplication.translate("MainWindow", u"1920:1080", None))
        self.label_6.setText(QCoreApplication.translate("MainWindow", u"\u041a\u043e\u043c\u0430\u043d\u0434\u0430 FFmpeg:", None))
        self.copyCmdButton.setText(QCoreApplication.translate("MainWindow", u"\u041a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c", None))
        self.runButton.setText(QCoreApplication.translate("MainWindow", u"\u0417\u0430\u043f\u0443\u0441\u0442\u0438\u0442\u044c \u043a\u043e\u0434\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u0435", None))
        self.pauseResumeButton.setText(QCoreApplication.translate("MainWindow", u"\u23f8 \u041f\u0430\u0443\u0437\u0430", None))
        self.savePresetButton.setText(QCoreApplication.translate("MainWindow", u"\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c \u043f\u0440\u0435\u0441\u0435\u0442", None))
        self.loadPresetButton.setText(QCoreApplication.translate("MainWindow", u"\u0417\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u043f\u0440\u0435\u0441\u0435\u0442", None))
        self.deletePresetButton.setText(QCoreApplication.translate("MainWindow", u"\u0423\u0434\u0430\u043b\u0438\u0442\u044c \u043f\u0440\u0435\u0441\u0435\u0442", None))
        self.exportPresetButton.setText(QCoreApplication.translate("MainWindow", u"\u042d\u043a\u0441\u043f\u043e\u0440\u0442 \u043f\u0440\u0435\u0441\u0435\u0442\u043e\u0432", None))
        self.importPresetButton.setText(QCoreApplication.translate("MainWindow", u"\u0418\u043c\u043f\u043e\u0440\u0442 \u043f\u0440\u0435\u0441\u0435\u0442\u043e\u0432", None))
        self.label_7.setText(QCoreApplication.translate("MainWindow", u"\u041b\u043e\u0433 \u0432\u044b\u043f\u043e\u043b\u043d\u0435\u043d\u0438\u044f:", None))
        self.openOutputFolderButton.setText(QCoreApplication.translate("MainWindow", u"\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u043f\u0430\u043f\u043a\u0443", None))
        self.videoPlayButton.setText(QCoreApplication.translate("MainWindow", u"\u25b6 Play", None))
        self.videoStopButton.setText(QCoreApplication.translate("MainWindow", u"\u23f9 Stop", None))
        self.videoTimeLabel.setText(QCoreApplication.translate("MainWindow", u"00:00 / 00:00", None))
        self.videoMuteButton.setText(QCoreApplication.translate("MainWindow", u"\U0000200b\U0001f50a", None))
        self.menumainwindow.setTitle(QCoreApplication.translate("MainWindow", u"mainwindow", None))
    # retranslateUi

