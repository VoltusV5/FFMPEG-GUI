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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QHBoxLayout, QHeaderView,
    QLabel, QLayout, QMainWindow, QMenu,
    QMenuBar, QProgressBar, QPushButton, QSizePolicy,
    QSlider, QStatusBar, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.setEnabled(True)
        MainWindow.resize(1313, 958)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.horizontalLayoutWidget_7 = QWidget(self.centralwidget)
        self.horizontalLayoutWidget_7.setObjectName(u"horizontalLayoutWidget_7")
        self.horizontalLayoutWidget_7.setGeometry(QRect(20, 590, 431, 41))
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

        self.showFFmpegLogButton = QPushButton(self.horizontalLayoutWidget_7)
        self.showFFmpegLogButton.setObjectName(u"showFFmpegLogButton")

        self.horizontalLayout_8.addWidget(self.showFFmpegLogButton)

        self.videoPreviewContainer = QWidget(self.centralwidget)
        self.videoPreviewContainer.setObjectName(u"videoPreviewContainer")
        self.videoPreviewContainer.setGeometry(QRect(210, 10, 401, 291))
        self.verticalLayoutWidget_2 = QWidget(self.videoPreviewContainer)
        self.verticalLayoutWidget_2.setObjectName(u"verticalLayoutWidget_2")
        self.verticalLayoutWidget_2.setGeometry(QRect(0, 0, 401, 291))
        self.verticalLayout = QVBoxLayout(self.verticalLayoutWidget_2)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.videoPreviewWidget = QWidget(self.verticalLayoutWidget_2)
        self.videoPreviewWidget.setObjectName(u"videoPreviewWidget")
        self.videoPreviewWidget.setMaximumSize(QSize(384, 216))
        self.videoPreviewWidget.setStyleSheet(u"border: 1px solid #cccccc; background-color: #000000;")

        self.horizontalLayout.addWidget(self.videoPreviewWidget)


        self.verticalLayout.addLayout(self.horizontalLayout)

        self.videoTimelineSlider = QSlider(self.verticalLayoutWidget_2)
        self.videoTimelineSlider.setObjectName(u"videoTimelineSlider")
        self.videoTimelineSlider.setMaximum(10000)
        self.videoTimelineSlider.setOrientation(Qt.Orientation.Horizontal)

        self.verticalLayout.addWidget(self.videoTimelineSlider)

        self.videoControlsLayout = QHBoxLayout()
        self.videoControlsLayout.setSpacing(2)
        self.videoControlsLayout.setObjectName(u"videoControlsLayout")
        self.videoControlsLayout.setSizeConstraint(QLayout.SizeConstraint.SetDefaultConstraint)
        self.videoPlayButton = QPushButton(self.verticalLayoutWidget_2)
        self.videoPlayButton.setObjectName(u"videoPlayButton")
        self.videoPlayButton.setMaximumSize(QSize(16777215, 16777215))

        self.videoControlsLayout.addWidget(self.videoPlayButton)

        self.PreviousFrame = QPushButton(self.verticalLayoutWidget_2)
        self.PreviousFrame.setObjectName(u"PreviousFrame")
        self.PreviousFrame.setMaximumSize(QSize(30, 16777215))

        self.videoControlsLayout.addWidget(self.PreviousFrame)

        self.NextFrame = QPushButton(self.verticalLayoutWidget_2)
        self.NextFrame.setObjectName(u"NextFrame")
        self.NextFrame.setMaximumSize(QSize(30, 16777215))

        self.videoControlsLayout.addWidget(self.NextFrame)

        self.videoTimeLabel = QLabel(self.verticalLayoutWidget_2)
        self.videoTimeLabel.setObjectName(u"videoTimeLabel")
        self.videoTimeLabel.setMaximumSize(QSize(65, 16777215))

        self.videoControlsLayout.addWidget(self.videoTimeLabel)

        self.AddKeepArea = QPushButton(self.verticalLayoutWidget_2)
        self.AddKeepArea.setObjectName(u"AddKeepArea")
        self.AddKeepArea.setMaximumSize(QSize(30, 16777215))

        self.videoControlsLayout.addWidget(self.AddKeepArea)

        self.SetInPoint = QPushButton(self.verticalLayoutWidget_2)
        self.SetInPoint.setObjectName(u"SetInPoint")
        self.SetInPoint.setMaximumSize(QSize(30, 16777215))

        self.videoControlsLayout.addWidget(self.SetInPoint)

        self.SetOutPoint = QPushButton(self.verticalLayoutWidget_2)
        self.SetOutPoint.setObjectName(u"SetOutPoint")
        self.SetOutPoint.setMaximumSize(QSize(30, 16777215))

        self.videoControlsLayout.addWidget(self.SetOutPoint)

        self.videoMuteButton = QPushButton(self.verticalLayoutWidget_2)
        self.videoMuteButton.setObjectName(u"videoMuteButton")
        self.videoMuteButton.setMaximumSize(QSize(40, 16777215))

        self.videoControlsLayout.addWidget(self.videoMuteButton)


        self.verticalLayout.addLayout(self.videoControlsLayout)

        self.verticalLayout.setStretch(0, 6)
        self.verticalLayout.setStretch(1, 2)
        self.verticalLayout.setStretch(2, 1)
        self.queueContainer = QWidget(self.centralwidget)
        self.queueContainer.setObjectName(u"queueContainer")
        self.queueContainer.setGeometry(QRect(20, 300, 791, 281))
        self.verticalLayoutWidget = QWidget(self.queueContainer)
        self.verticalLayoutWidget.setObjectName(u"verticalLayoutWidget")
        self.verticalLayoutWidget.setGeometry(QRect(0, 20, 771, 261))
        self.queueContainerLayout = QVBoxLayout(self.verticalLayoutWidget)
        self.queueContainerLayout.setObjectName(u"queueContainerLayout")
        self.queueContainerLayout.setContentsMargins(0, 0, 0, 0)
        self.queueTableWidget = QTableWidget(self.verticalLayoutWidget)
        if (self.queueTableWidget.columnCount() < 6):
            self.queueTableWidget.setColumnCount(6)
        __qtablewidgetitem = QTableWidgetItem()
        self.queueTableWidget.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.queueTableWidget.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.queueTableWidget.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.queueTableWidget.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        __qtablewidgetitem4 = QTableWidgetItem()
        self.queueTableWidget.setHorizontalHeaderItem(4, __qtablewidgetitem4)
        __qtablewidgetitem5 = QTableWidgetItem()
        self.queueTableWidget.setHorizontalHeaderItem(5, __qtablewidgetitem5)
        self.queueTableWidget.setObjectName(u"queueTableWidget")
        self.queueTableWidget.setAcceptDrops(True)
        self.queueTableWidget.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.queueTableWidget.setAlternatingRowColors(True)
        self.queueTableWidget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.queueTableWidget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.queueContainerLayout.addWidget(self.queueTableWidget)

        self.queueButtonsLayout = QHBoxLayout()
        self.queueButtonsLayout.setObjectName(u"queueButtonsLayout")
        self.addFilesButton = QPushButton(self.verticalLayoutWidget)
        self.addFilesButton.setObjectName(u"addFilesButton")

        self.queueButtonsLayout.addWidget(self.addFilesButton)

        self.removeFromQueueButton = QPushButton(self.verticalLayoutWidget)
        self.removeFromQueueButton.setObjectName(u"removeFromQueueButton")

        self.queueButtonsLayout.addWidget(self.removeFromQueueButton)

        self.QueueUp = QPushButton(self.verticalLayoutWidget)
        self.QueueUp.setObjectName(u"QueueUp")

        self.queueButtonsLayout.addWidget(self.QueueUp)

        self.QueueDown = QPushButton(self.verticalLayoutWidget)
        self.QueueDown.setObjectName(u"QueueDown")

        self.queueButtonsLayout.addWidget(self.QueueDown)

        self.queueButtonsLayout.setStretch(0, 4)
        self.queueButtonsLayout.setStretch(1, 3)
        self.queueButtonsLayout.setStretch(2, 1)
        self.queueButtonsLayout.setStretch(3, 1)

        self.queueContainerLayout.addLayout(self.queueButtonsLayout)

        self.queueContainerLayout.setStretch(0, 9)
        self.queueContainerLayout.setStretch(1, 1)
        self.queueLabel = QLabel(self.queueContainer)
        self.queueLabel.setObjectName(u"queueLabel")
        self.queueLabel.setGeometry(QRect(0, 0, 101, 16))
        self.presetEditorContainer = QWidget(self.centralwidget)
        self.presetEditorContainer.setObjectName(u"presetEditorContainer")
        self.presetEditorContainer.setGeometry(QRect(820, 10, 471, 291))
        self.verticalLayoutWidget_3 = QWidget(self.presetEditorContainer)
        self.verticalLayoutWidget_3.setObjectName(u"verticalLayoutWidget_3")
        self.verticalLayoutWidget_3.setGeometry(QRect(0, 0, 471, 291))
        self.presetEditorLayout = QVBoxLayout(self.verticalLayoutWidget_3)
        self.presetEditorLayout.setObjectName(u"presetEditorLayout")
        self.presetEditorLayout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(self.verticalLayoutWidget_3)
        self.label.setObjectName(u"label")

        self.presetEditorLayout.addWidget(self.label)

        self.presetEditorTopButtonsLayout = QHBoxLayout()
        self.presetEditorTopButtonsLayout.setObjectName(u"presetEditorTopButtonsLayout")
        self.presetExportButton = QPushButton(self.verticalLayoutWidget_3)
        self.presetExportButton.setObjectName(u"presetExportButton")

        self.presetEditorTopButtonsLayout.addWidget(self.presetExportButton)

        self.presetImportButton = QPushButton(self.verticalLayoutWidget_3)
        self.presetImportButton.setObjectName(u"presetImportButton")

        self.presetEditorTopButtonsLayout.addWidget(self.presetImportButton)


        self.presetEditorLayout.addLayout(self.presetEditorTopButtonsLayout)

        self.presetsTableWidget = QTableWidget(self.verticalLayoutWidget_3)
        if (self.presetsTableWidget.columnCount() < 4):
            self.presetsTableWidget.setColumnCount(4)
        __qtablewidgetitem6 = QTableWidgetItem()
        self.presetsTableWidget.setHorizontalHeaderItem(0, __qtablewidgetitem6)
        __qtablewidgetitem7 = QTableWidgetItem()
        self.presetsTableWidget.setHorizontalHeaderItem(1, __qtablewidgetitem7)
        __qtablewidgetitem8 = QTableWidgetItem()
        self.presetsTableWidget.setHorizontalHeaderItem(2, __qtablewidgetitem8)
        font = QFont()
        font.setPointSize(9)
        __qtablewidgetitem9 = QTableWidgetItem()
        __qtablewidgetitem9.setFont(font);
        self.presetsTableWidget.setHorizontalHeaderItem(3, __qtablewidgetitem9)
        self.presetsTableWidget.setObjectName(u"presetsTableWidget")
        self.presetsTableWidget.setAlternatingRowColors(True)
        self.presetsTableWidget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.presetsTableWidget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.presetsTableWidget.setColumnCount(4)
        self.presetsTableWidget.horizontalHeader().setCascadingSectionResizes(False)
        self.presetsTableWidget.horizontalHeader().setDefaultSectionSize(100)
        self.presetsTableWidget.horizontalHeader().setHighlightSections(True)
        self.presetsTableWidget.horizontalHeader().setProperty(u"showSortIndicator", False)

        self.presetEditorLayout.addWidget(self.presetsTableWidget)

        self.presetEditorBottomButtonsLayout = QHBoxLayout()
        self.presetEditorBottomButtonsLayout.setObjectName(u"presetEditorBottomButtonsLayout")
        self.presetEditorBottomButtonsLayout.setContentsMargins(-1, -1, -1, 10)
        self.createPresetButton = QPushButton(self.verticalLayoutWidget_3)
        self.createPresetButton.setObjectName(u"createPresetButton")

        self.presetEditorBottomButtonsLayout.addWidget(self.createPresetButton)

        self.savePresetChangesButton = QPushButton(self.verticalLayoutWidget_3)
        self.savePresetChangesButton.setObjectName(u"savePresetChangesButton")

        self.presetEditorBottomButtonsLayout.addWidget(self.savePresetChangesButton)


        self.presetEditorLayout.addLayout(self.presetEditorBottomButtonsLayout)

        self.presetEditorLayout.setStretch(2, 20)
        self.presetEditorLayout.setStretch(3, 2)
        self.presetSettingsContainer = QWidget(self.centralwidget)
        self.presetSettingsContainer.setObjectName(u"presetSettingsContainer")
        self.presetSettingsContainer.setGeometry(QRect(820, 320, 471, 341))
        self.verticalLayoutWidget_4 = QWidget(self.presetSettingsContainer)
        self.verticalLayoutWidget_4.setObjectName(u"verticalLayoutWidget_4")
        self.verticalLayoutWidget_4.setGeometry(QRect(0, 0, 471, 141))
        self.presetSettingsLayout = QVBoxLayout(self.verticalLayoutWidget_4)
        self.presetSettingsLayout.setObjectName(u"presetSettingsLayout")
        self.presetSettingsLayout.setContentsMargins(0, 0, 0, 0)
        self.codecRowLayout = QHBoxLayout()
        self.codecRowLayout.setSpacing(5)
        self.codecRowLayout.setObjectName(u"codecRowLayout")
        self.codecLabel = QLabel(self.verticalLayoutWidget_4)
        self.codecLabel.setObjectName(u"codecLabel")

        self.codecRowLayout.addWidget(self.codecLabel)

        self.codecCurrentButton = QPushButton(self.verticalLayoutWidget_4)
        self.codecCurrentButton.setObjectName(u"codecCurrentButton")

        self.codecRowLayout.addWidget(self.codecCurrentButton)

        self.codecLibx264Button = QPushButton(self.verticalLayoutWidget_4)
        self.codecLibx264Button.setObjectName(u"codecLibx264Button")

        self.codecRowLayout.addWidget(self.codecLibx264Button)

        self.codecLibx265Button = QPushButton(self.verticalLayoutWidget_4)
        self.codecLibx265Button.setObjectName(u"codecLibx265Button")

        self.codecRowLayout.addWidget(self.codecLibx265Button)

        self.codecCustomButton = QPushButton(self.verticalLayoutWidget_4)
        self.codecCustomButton.setObjectName(u"codecCustomButton")

        self.codecRowLayout.addWidget(self.codecCustomButton)


        self.presetSettingsLayout.addLayout(self.codecRowLayout)

        self.containerRowLayout = QHBoxLayout()
        self.containerRowLayout.setSpacing(5)
        self.containerRowLayout.setObjectName(u"containerRowLayout")
        self.containerLabel = QLabel(self.verticalLayoutWidget_4)
        self.containerLabel.setObjectName(u"containerLabel")

        self.containerRowLayout.addWidget(self.containerLabel)

        self.containerCurrentButton = QPushButton(self.verticalLayoutWidget_4)
        self.containerCurrentButton.setObjectName(u"containerCurrentButton")

        self.containerRowLayout.addWidget(self.containerCurrentButton)

        self.containerMp4Button = QPushButton(self.verticalLayoutWidget_4)
        self.containerMp4Button.setObjectName(u"containerMp4Button")

        self.containerRowLayout.addWidget(self.containerMp4Button)

        self.containerMkvButton = QPushButton(self.verticalLayoutWidget_4)
        self.containerMkvButton.setObjectName(u"containerMkvButton")

        self.containerRowLayout.addWidget(self.containerMkvButton)

        self.containerCustomButton = QPushButton(self.verticalLayoutWidget_4)
        self.containerCustomButton.setObjectName(u"containerCustomButton")

        self.containerRowLayout.addWidget(self.containerCustomButton)


        self.presetSettingsLayout.addLayout(self.containerRowLayout)

        self.resolutionRowLayout = QHBoxLayout()
        self.resolutionRowLayout.setObjectName(u"resolutionRowLayout")
        self.resolutionLabel = QLabel(self.verticalLayoutWidget_4)
        self.resolutionLabel.setObjectName(u"resolutionLabel")

        self.resolutionRowLayout.addWidget(self.resolutionLabel)

        self.resolutionCurrentButton = QPushButton(self.verticalLayoutWidget_4)
        self.resolutionCurrentButton.setObjectName(u"resolutionCurrentButton")

        self.resolutionRowLayout.addWidget(self.resolutionCurrentButton)

        self.resolution480pButton = QPushButton(self.verticalLayoutWidget_4)
        self.resolution480pButton.setObjectName(u"resolution480pButton")

        self.resolutionRowLayout.addWidget(self.resolution480pButton)

        self.resolution720pButton = QPushButton(self.verticalLayoutWidget_4)
        self.resolution720pButton.setObjectName(u"resolution720pButton")

        self.resolutionRowLayout.addWidget(self.resolution720pButton)

        self.resolution1080pButton = QPushButton(self.verticalLayoutWidget_4)
        self.resolution1080pButton.setObjectName(u"resolution1080pButton")

        self.resolutionRowLayout.addWidget(self.resolution1080pButton)

        self.resolutionCustomButton = QPushButton(self.verticalLayoutWidget_4)
        self.resolutionCustomButton.setObjectName(u"resolutionCustomButton")

        self.resolutionRowLayout.addWidget(self.resolutionCustomButton)

        self.resolutionRowLayout.setStretch(0, 2)
        self.resolutionRowLayout.setStretch(1, 1)
        self.resolutionRowLayout.setStretch(2, 1)
        self.resolutionRowLayout.setStretch(3, 1)
        self.resolutionRowLayout.setStretch(4, 1)

        self.presetSettingsLayout.addLayout(self.resolutionRowLayout)

        self.widget = QWidget(self.presetSettingsContainer)
        self.widget.setObjectName(u"widget")
        self.widget.setGeometry(QRect(0, 140, 471, 191))
        self.horizontalLayoutWidget_6 = QWidget(self.widget)
        self.horizontalLayoutWidget_6.setObjectName(u"horizontalLayoutWidget_6")
        self.horizontalLayoutWidget_6.setGeometry(QRect(0, 22, 471, 141))
        self.horizontalLayout_7 = QHBoxLayout(self.horizontalLayoutWidget_6)
        self.horizontalLayout_7.setObjectName(u"horizontalLayout_7")
        self.horizontalLayout_7.setContentsMargins(0, 0, 0, 0)
        self.commandDisplay = QTextEdit(self.horizontalLayoutWidget_6)
        self.commandDisplay.setObjectName(u"commandDisplay")
        self.commandDisplay.setMaximumSize(QSize(16777215, 140))
        self.commandDisplay.setStyleSheet(u"background-color: #f0f0f0; font-family: Consolas;")
        self.commandDisplay.setReadOnly(False)

        self.horizontalLayout_7.addWidget(self.commandDisplay)

        self.copyCmdButton = QPushButton(self.widget)
        self.copyCmdButton.setObjectName(u"copyCmdButton")
        self.copyCmdButton.setGeometry(QRect(380, 10, 91, 21))
        self.label_6 = QLabel(self.widget)
        self.label_6.setObjectName(u"label_6")
        self.label_6.setGeometry(QRect(0, 0, 131, 20))
        self.widget_2 = QWidget(self.centralwidget)
        self.widget_2.setObjectName(u"widget_2")
        self.widget_2.setGeometry(QRect(20, 650, 791, 261))
        self.logDisplay = QTextEdit(self.widget_2)
        self.logDisplay.setObjectName(u"logDisplay")
        self.logDisplay.setGeometry(QRect(0, 30, 771, 221))
        self.logDisplay.setReadOnly(True)
        self.label_7 = QLabel(self.widget_2)
        self.label_7.setObjectName(u"label_7")
        self.label_7.setGeometry(QRect(0, 0, 131, 20))
        self.totalQueueProgressBar = QProgressBar(self.centralwidget)
        self.totalQueueProgressBar.setObjectName(u"totalQueueProgressBar")
        self.totalQueueProgressBar.setGeometry(QRect(460, 600, 331, 21))
        self.totalQueueProgressBar.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.totalQueueProgressBar.setValue(0)
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 1313, 22))
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
        self.runButton.setText(QCoreApplication.translate("MainWindow", u"\u0417\u0430\u043f\u0443\u0441\u0442\u0438\u0442\u044c \u043a\u043e\u0434\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u0435", None))
        self.pauseResumeButton.setText(QCoreApplication.translate("MainWindow", u"\u041f\u0430\u0443\u0437\u0430", None))
        self.showFFmpegLogButton.setText(QCoreApplication.translate("MainWindow", u"\u041f\u043e\u043a\u0430\u0437\u0430\u0442\u044c \u043b\u043e\u0433 ffmpeg", None))
        self.videoPlayButton.setText(QCoreApplication.translate("MainWindow", u"Play", None))
        self.PreviousFrame.setText(QCoreApplication.translate("MainWindow", u"\u2190", None))
        self.NextFrame.setText(QCoreApplication.translate("MainWindow", u"\u2192", None))
        self.videoTimeLabel.setText(QCoreApplication.translate("MainWindow", u"00:00 / 00:00", None))
        self.AddKeepArea.setText(QCoreApplication.translate("MainWindow", u"+", None))
        self.SetInPoint.setText(QCoreApplication.translate("MainWindow", u"in", None))
        self.SetOutPoint.setText(QCoreApplication.translate("MainWindow", u"out", None))
        self.videoMuteButton.setText(QCoreApplication.translate("MainWindow", u"\U0000200b\U0001f50a", None))
        ___qtablewidgetitem = self.queueTableWidget.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("MainWindow", u"\u0412\u0445\u043e\u0434\u043d\u043e\u0439 \u0444\u0430\u0439\u043b", None));
        ___qtablewidgetitem1 = self.queueTableWidget.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("MainWindow", u"\u0412\u044b\u0445\u043e\u0434\u043d\u043e\u0439 \u0444\u0430\u0439\u043b", None));
        ___qtablewidgetitem2 = self.queueTableWidget.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("MainWindow", u"\u041f\u0440\u0435\u0441\u0435\u0442", None));
        ___qtablewidgetitem3 = self.queueTableWidget.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("MainWindow", u"\u0421\u0442\u0430\u0442\u0443\u0441", None));
        ___qtablewidgetitem4 = self.queueTableWidget.horizontalHeaderItem(4)
        ___qtablewidgetitem4.setText(QCoreApplication.translate("MainWindow", u"\u041f\u0440\u043e\u0433\u0440\u0435\u0441\u0441", None));
        ___qtablewidgetitem5 = self.queueTableWidget.horizontalHeaderItem(5)
        ___qtablewidgetitem5.setText(QCoreApplication.translate("MainWindow", u"\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u043f\u0430\u043f\u043a\u0443", None));
        self.addFilesButton.setText(QCoreApplication.translate("MainWindow", u"\u0414\u043e\u0431\u0430\u0432\u0438\u0442\u044c \u0444\u0430\u0439\u043b\u044b...", None))
        self.removeFromQueueButton.setText(QCoreApplication.translate("MainWindow", u"\u0423\u0434\u0430\u043b\u0438\u0442\u044c \u0438\u0437 \u043e\u0447\u0435\u0440\u0435\u0434\u0438", None))
        self.QueueUp.setText(QCoreApplication.translate("MainWindow", u"\u2191", None))
        self.QueueDown.setText(QCoreApplication.translate("MainWindow", u"\u2193", None))
        self.queueLabel.setText(QCoreApplication.translate("MainWindow", u"\u041e\u0447\u0435\u0440\u0435\u0434\u044c \u0444\u0430\u0439\u043b\u043e\u0432:", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0430 \u043f\u0440\u0435\u0441\u0435\u0442\u043e\u0432", None))
        self.presetExportButton.setText(QCoreApplication.translate("MainWindow", u"\u042d\u043a\u0441\u043f\u043e\u0440\u0442 \u043f\u0440\u0435\u0441\u0435\u0442\u043e\u0432", None))
        self.presetImportButton.setText(QCoreApplication.translate("MainWindow", u"\u0418\u043c\u043f\u043e\u0440\u0442 \u043f\u0440\u0435\u0441\u0435\u0442\u043e\u0432", None))
        ___qtablewidgetitem6 = self.presetsTableWidget.horizontalHeaderItem(0)
        ___qtablewidgetitem6.setText(QCoreApplication.translate("MainWindow", u"\u041d\u0430\u0437\u0432\u0430\u043d\u0438\u0435", None));
        ___qtablewidgetitem7 = self.presetsTableWidget.horizontalHeaderItem(1)
        ___qtablewidgetitem7.setText(QCoreApplication.translate("MainWindow", u"\u041e\u043f\u0438\u0441\u0430\u043d\u0438\u0435", None));
        ___qtablewidgetitem8 = self.presetsTableWidget.horizontalHeaderItem(2)
        ___qtablewidgetitem8.setText(QCoreApplication.translate("MainWindow", u"\u0423\u0434\u0430\u043b\u0438\u0442\u044c", None));
        ___qtablewidgetitem9 = self.presetsTableWidget.horizontalHeaderItem(3)
        ___qtablewidgetitem9.setText(QCoreApplication.translate("MainWindow", u"\u041f\u0440\u0438\u043c\u0435\u043d\u0438\u0442\u044c \u043a \u0432\u044b\u0431\u0440\u0430\u043d\u043d\u043e\u043c\u0443 \u0444\u0430\u0439\u043b\u0443", None));
        self.createPresetButton.setText(QCoreApplication.translate("MainWindow", u"\u0421\u043e\u0437\u0434\u0430\u0442\u044c \u043f\u0440\u0435\u0441\u0435\u0442", None))
        self.savePresetChangesButton.setText(QCoreApplication.translate("MainWindow", u"\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c \u043f\u0440\u0435\u0441\u0435\u0442", None))
        self.codecLabel.setText(QCoreApplication.translate("MainWindow", u"\u041a\u043e\u0434\u0435\u043a", None))
        self.codecCurrentButton.setText(QCoreApplication.translate("MainWindow", u"current", None))
        self.codecLibx264Button.setText(QCoreApplication.translate("MainWindow", u"libx264", None))
        self.codecLibx265Button.setText(QCoreApplication.translate("MainWindow", u"libx265", None))
        self.codecCustomButton.setText(QCoreApplication.translate("MainWindow", u"custom", None))
        self.containerLabel.setText(QCoreApplication.translate("MainWindow", u"\u041a\u043e\u043d\u0442\u0435\u0439\u043d\u0435\u0440", None))
        self.containerCurrentButton.setText(QCoreApplication.translate("MainWindow", u"current", None))
        self.containerMp4Button.setText(QCoreApplication.translate("MainWindow", u"mp4", None))
        self.containerMkvButton.setText(QCoreApplication.translate("MainWindow", u"mkv", None))
        self.containerCustomButton.setText(QCoreApplication.translate("MainWindow", u"custom", None))
        self.resolutionLabel.setText(QCoreApplication.translate("MainWindow", u"\u0420\u0430\u0437\u0440\u0435\u0448\u0435\u043d\u0438\u0435 ", None))
        self.resolutionCurrentButton.setText(QCoreApplication.translate("MainWindow", u"current", None))
        self.resolution480pButton.setText(QCoreApplication.translate("MainWindow", u"480p", None))
        self.resolution720pButton.setText(QCoreApplication.translate("MainWindow", u"720p", None))
        self.resolution1080pButton.setText(QCoreApplication.translate("MainWindow", u"1080p", None))
        self.resolutionCustomButton.setText(QCoreApplication.translate("MainWindow", u"custom", None))
        self.copyCmdButton.setText(QCoreApplication.translate("MainWindow", u"\u041a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c", None))
        self.label_6.setText(QCoreApplication.translate("MainWindow", u"\u041a\u043e\u043c\u0430\u043d\u0434\u0430 FFmpeg:", None))
        self.label_7.setText(QCoreApplication.translate("MainWindow", u"\u041b\u043e\u0433 \u0432\u044b\u043f\u043e\u043b\u043d\u0435\u043d\u0438\u044f:", None))
        self.menumainwindow.setTitle(QCoreApplication.translate("MainWindow", u"mainwindow", None))
    # retranslateUi

