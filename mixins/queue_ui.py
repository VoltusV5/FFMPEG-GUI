"""Миксин: таблица очереди, добавление/удаление/перемещение, drag-and-drop, выделение."""

import os
from PySide6.QtWidgets import (
    QFileDialog, QMessageBox, QTableWidgetItem, QPushButton,
    QHeaderView, QAbstractItemView,
)
from PySide6.QtCore import Qt

from app.constants import (
    QUEUE_TABLE_COLUMN_COUNT,
    QUEUE_TABLE_COLUMN_WIDTHS_WITH_ROWS,
    QUEUE_TABLE_COLUMN_WIDTHS_EMPTY,
    MAX_DISPLAY_NAME_LENGTH,
)
from models.queueitem import QueueItem


class QueueUIMixin:
    """Миксин: инициализация таблицы очереди, добавление/удаление/перемещение файлов, выделение, отображение."""

    def initQueue(self):
        """Инициализирует таблицу очереди"""
        if not hasattr(self.ui, 'queueTableWidget'):
            return
        table = self.ui.queueTableWidget
        table.setColumnCount(QUEUE_TABLE_COLUMN_COUNT)
        table.setHorizontalHeaderLabels([
            "Входной файл", "Выходной файл", "Пресет", "Статус", "Прогресс", "Открыть"
        ])
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._applyQueueTableColumnWidths()
        table.setAcceptDrops(True)
        table.setDragDropMode(QAbstractItemView.DropOnly)
        table.setDefaultDropAction(Qt.CopyAction)
        table.itemSelectionChanged.connect(self.onQueueItemSelected)
        table.cellDoubleClicked.connect(self.onQueueCellDoubleClicked)
        table.itemChanged.connect(self.onQueueItemChanged)
        table.setAcceptDrops(True)
        self.setupDragAndDrop()

    def _applyQueueTableColumnWidths(self):
        """Ширины колонок таблицы очереди."""
        if not hasattr(self.ui, 'queueTableWidget'):
            return
        table = self.ui.queueTableWidget
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        has_rows = table.rowCount() > 0
        if has_rows:
            table.verticalHeader().setVisible(True)
            widths = QUEUE_TABLE_COLUMN_WIDTHS_WITH_ROWS
        else:
            table.verticalHeader().setVisible(False)
            widths = QUEUE_TABLE_COLUMN_WIDTHS_EMPTY
        for col, w in enumerate(widths):
            header.setSectionResizeMode(col, QHeaderView.Fixed)
            table.setColumnWidth(col, w)

    def setupDragAndDrop(self):
        """Настраивает drag-and-drop для таблицы очереди."""
        if not hasattr(self.ui, 'queueTableWidget'):
            return
        table = self.ui.queueTableWidget

        class DragDropTable:
            def __init__(self, main_window, table):
                self.main_window = main_window
                self.table = table

            def dragEnterEvent(self, event):
                if event.mimeData().hasUrls():
                    event.acceptProposedAction()
                else:
                    event.ignore()

            def dragMoveEvent(self, event):
                if event.mimeData().hasUrls():
                    event.acceptProposedAction()
                else:
                    event.ignore()

            def dropEvent(self, event):
                if event.mimeData().hasUrls():
                    event.acceptProposedAction()
                    urls = event.mimeData().urls()
                    for url in urls:
                        file_path = url.toLocalFile()
                        if os.path.isfile(file_path):
                            ext = os.path.splitext(file_path)[1].lower()
                            if ext in ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv']:
                                self.main_window.addFileToQueue(file_path)
                else:
                    event.ignore()

        wrapper = DragDropTable(self, table)
        table.dragEnterEvent = wrapper.dragEnterEvent
        table.dragMoveEvent = wrapper.dragMoveEvent
        table.dropEvent = wrapper.dropEvent

    def addFilesToQueue(self):
        """Добавляет файлы в очередь через диалог выбора"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите видео файлы",
            "",
            "Видео (*.mp4 *.mkv *.avi *.mov *.flv *.wmv)"
        )
        for file_path in files:
            self.addFileToQueue(file_path)

    def addFileToQueue(self, file_path):
        """Добавляет один файл в очередь"""
        if not file_path or not os.path.exists(file_path):
            return
        for item in self.queue:
            if item.file_path == file_path:
                QMessageBox.information(self, "Информация", f"Файл уже в очереди:\n{file_path}")
                return
        queue_item = QueueItem(file_path)
        self.queue.append(queue_item)
        self._generateOutputFileForItem(queue_item)
        self.updateQueueTable()
        self.updateTotalQueueProgress()
        self.selectQueueItem(len(self.queue) - 1)

    def removeSelectedFromQueue(self):
        """Удаляет выделенный файл из очереди"""
        if self.selectedQueueIndex < 0 or self.selectedQueueIndex >= len(self.queue):
            return
        if self.currentQueueIndex >= 0 and not self.isPaused:
            QMessageBox.warning(
                self,
                "Предупреждение",
                "Нельзя удалять файлы из очереди во время кодирования.\n"
                "Нажмите «Пауза» или «Завершить кодирование»."
            )
            return
        if self.currentQueueIndex >= 0 and self.isPaused:
            item = self.queue[self.selectedQueueIndex]
            if item.status == QueueItem.STATUS_SUCCESS:
                QMessageBox.warning(
                    self,
                    "Предупреждение",
                    "Нельзя удалить перекодированный файл до завершения кодирования всей очереди."
                )
                return
        removed_index = self.selectedQueueIndex
        del self.queue[self.selectedQueueIndex]
        if self.currentQueueIndex > self.selectedQueueIndex:
            self.currentQueueIndex -= 1
        table = self.ui.queueTableWidget if hasattr(self.ui, 'queueTableWidget') else None
        if table:
            table.blockSignals(True)
            self.updateQueueTable()
            if self.queue:
                new_index = min(removed_index, len(self.queue) - 1)
                self.selectedQueueIndex = new_index
                table.clearSelection()
                table.selectRow(new_index)
                table.blockSignals(False)
                self.selectQueueItem(new_index)
            else:
                self.selectedQueueIndex = -1
                table.clearSelection()
                self.inputFile = ""
                if hasattr(self.ui, 'commandDisplay'):
                    self.ui.commandDisplay.clear()
                table.blockSignals(False)
        else:
            self.updateQueueTable()

    def updateQueueTable(self):
        """Обновляет отображение таблицы очереди"""
        if not hasattr(self.ui, 'queueTableWidget'):
            return
        table = self.ui.queueTableWidget
        table.blockSignals(True)
        table.setRowCount(len(self.queue))
        for row, item in enumerate(self.queue):
            full_input_name = os.path.basename(item.file_path) if item.file_path else ""
            input_name = self._truncateNameForDisplay(full_input_name, MAX_DISPLAY_NAME_LENGTH)
            file_item = QTableWidgetItem(input_name)
            file_item.setFlags(file_item.flags() & ~Qt.ItemIsEditable)
            file_item.setToolTip(item.file_path)
            table.setItem(row, 0, file_item)
            output_file_path = item.output_file if item.output_file else ""
            if output_file_path:
                full_output_name = os.path.basename(output_file_path)
                display_output = self._truncateNameForDisplay(full_output_name, MAX_DISPLAY_NAME_LENGTH)
            else:
                display_output = ""
            output_item = QTableWidgetItem(display_output)
            output_item.setToolTip(output_file_path)
            output_item.setFlags(output_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row, 1, output_item)
            preset_text = item.preset_name if item.preset_name else "default"
            if isinstance(preset_text, str) and preset_text.startswith("cmd:"):
                preset_text = f"cmd + {preset_text[4:]}"
            preset_item = QTableWidgetItem(preset_text)
            preset_item.setFlags(preset_item.flags() & ~Qt.ItemIsEditable)
            preset_item.setToolTip(preset_text)
            table.setItem(row, 2, preset_item)
            status_item = QTableWidgetItem(item.getStatusText())
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row, 3, status_item)
            progress_text = f"{item.progress}%"
            progress_item = QTableWidgetItem(progress_text)
            progress_item.setFlags(progress_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row, 4, progress_item)
            if item.status == QueueItem.STATUS_SUCCESS and item.output_file:
                open_btn = QPushButton("Открыть")
                open_btn.setMaximumHeight(22)
                open_btn.setStyleSheet("padding: 2px 4px; font-size: 10px; min-height: 0;")
                open_btn.clicked.connect(lambda _, path=item.output_file: self.openFileLocation(path))
                table.setCellWidget(row, 5, open_btn)
            else:
                empty_item = QTableWidgetItem("")
                empty_item.setFlags(empty_item.flags() & ~Qt.ItemIsEditable)
                table.setItem(row, 5, empty_item)
        table.blockSignals(False)
        self._applyQueueTableColumnWidths()

    def selectQueueItem(self, index):
        """Выделяет элемент очереди по индексу"""
        if not hasattr(self.ui, 'queueTableWidget') or index < 0 or index >= len(self.queue):
            return
        if self.selectedQueueIndex == index:
            return
        table = self.ui.queueTableWidget
        table.blockSignals(True)
        table.selectRow(index)
        table.blockSignals(False)
        self.selectedQueueIndex = index
        item = self.queue[index]
        self.inputFile = item.file_path
        if not item.output_file:
            self._generateOutputFileForItem(item)
        self.videoDuration = 0
        self._getVideoDurationForItem(item)
        if getattr(item, "video_duration", 0) > 0:
            self.videoDuration = item.video_duration
        self.loadVideoForPreview()
        if getattr(item, "command_manually_edited", False) and getattr(item, "command", ""):
            if isinstance(item.preset_name, str) and item.preset_name.startswith("cmd:"):
                self._applyPathsToSavedCommand(item)
            self.commandManuallyEdited = True
            self.lastGeneratedCommand = getattr(item, "last_generated_command", "")
            self.ui.commandDisplay.setPlainText(item.command)
        else:
            self.commandManuallyEdited = False
            self.updateCommandFromGUI()
        self.syncPresetEditorWithQueueItem(item)
        self._updateTrimSegmentBar()

    def onQueueItemSelected(self):
        """Обработчик выделения элемента в таблице"""
        table = self.ui.queueTableWidget
        selected_rows = table.selectionModel().selectedRows()
        indices = sorted([r.row() for r in selected_rows])
        if not indices:
            self.selectedQueueIndex = -1
            if hasattr(self.ui, 'commandDisplay'):
                self.ui.commandDisplay.clear()
                self.ui.commandDisplay.setReadOnly(True)
            if hasattr(self, 'mediaPlayer') and self.mediaPlayer:
                self.mediaPlayer.stop()
            self._updateTrimSegmentBar()
            return
        if len(indices) == 1:
            row = indices[0]
            if 0 <= row < len(self.queue) and row != self.selectedQueueIndex:
                if hasattr(self.ui, 'commandDisplay'):
                    self.ui.commandDisplay.setReadOnly(False)
                self.selectQueueItem(row)
        else:
            self.selectedQueueIndex = -1
            if hasattr(self.ui, 'commandDisplay'):
                self.ui.commandDisplay.clear()
                self.ui.commandDisplay.setReadOnly(True)
            if hasattr(self, 'mediaPlayer') and self.mediaPlayer:
                self.mediaPlayer.stop()
            self._updateTrimSegmentBar()

    def onQueueCellDoubleClicked(self, row, column):
        """Обработчик двойного клика по ячейке таблицы"""
        if column == 1:
            self.selectOutputFileForQueueItem(row)

    def selectOutputFileForQueueItem(self, row):
        """Открывает диалог выбора выходного файла для элемента очереди"""
        if row < 0 or row >= len(self.queue):
            return
        item = self.queue[row]
        if item.output_file:
            initial_dir = os.path.dirname(item.output_file)
            initial_name = os.path.splitext(os.path.basename(item.output_file))[0]
        else:
            initial_dir = os.path.dirname(item.file_path)
            input_base = os.path.splitext(os.path.basename(item.file_path))[0]
            initial_name = input_base + "_converted"
        container = item.container or "current"
        if container in ("default", "current", "", None):
            container_ext = os.path.splitext(item.file_path)[1].lstrip(".")
        else:
            container_ext = container
        if container_ext:
            file_filter = f"{container_ext.upper()} файлы (*.{container_ext});;Все файлы (*.*)"
        else:
            file_filter = "Все файлы (*.*)"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Выберите выходной файл",
            os.path.join(initial_dir, initial_name),
            file_filter
        )
        if file_path:
            item.output_file = file_path
            item.output_chosen_by_user = True
            self.updateQueueTable()
            if row == self.selectedQueueIndex:
                if isinstance(item.preset_name, str) and item.preset_name.startswith("cmd:"):
                    self._applyPathsToSavedCommand(item, update_display=True)
                else:
                    self.updateCommandFromGUI()

    def onQueueItemChanged(self, item):
        """Обработчик изменения ячейки в таблице очереди."""
        pass

    def getSelectedQueueItem(self):
        """Возвращает выделенный элемент очереди или None."""
        if self.selectedQueueIndex < 0 or self.selectedQueueIndex >= len(self.queue):
            return None
        return self.queue[self.selectedQueueIndex]

    def _truncateNameForDisplay(self, name, max_length=MAX_DISPLAY_NAME_LENGTH):
        """Возвращает первые max_length символов имени файла + '...' если оно длиннее."""
        if not name:
            return ""
        if len(name) <= max_length:
            return name
        return name[:max_length] + "..."

    def _moveQueueItem(self, from_index, to_index):
        """Перемещает элемент очереди и обновляет таблицу/выделение."""
        if from_index == to_index:
            return
        if from_index < 0 or from_index >= len(self.queue):
            return
        if to_index < 0 or to_index >= len(self.queue):
            return
        self.queue.insert(to_index, self.queue.pop(from_index))
        if self.currentQueueIndex == from_index:
            self.currentQueueIndex = to_index
        elif from_index < self.currentQueueIndex <= to_index:
            self.currentQueueIndex -= 1
        elif to_index <= self.currentQueueIndex < from_index:
            self.currentQueueIndex += 1
        self.updateQueueTable()
        if hasattr(self.ui, 'queueTableWidget'):
            table = self.ui.queueTableWidget
            table.blockSignals(True)
            table.clearSelection()
            table.selectRow(to_index)
            table.blockSignals(False)
        self.selectedQueueIndex = to_index

    def moveQueueItemUp(self):
        """Поднять выделенный файл в очереди выше."""
        table = self.ui.queueTableWidget if hasattr(self.ui, 'queueTableWidget') else None
        if not table:
            return
        selected_rows = table.selectionModel().selectedRows()
        if len(selected_rows) != 1:
            return
        row = selected_rows[0].row()
        if row <= 0:
            return
        self._moveQueueItem(row, row - 1)

    def moveQueueItemDown(self):
        """Опустить выделенный файл в очереди ниже."""
        table = self.ui.queueTableWidget if hasattr(self.ui, 'queueTableWidget') else None
        if not table:
            return
        selected_rows = table.selectionModel().selectedRows()
        if len(selected_rows) != 1:
            return
        row = selected_rows[0].row()
        if row >= len(self.queue) - 1:
            return
        self._moveQueueItem(row, row + 1)
