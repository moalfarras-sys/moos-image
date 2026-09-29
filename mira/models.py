"""Small list models that QML views bind to."""
from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, Qt, Signal, Property


class DictListModel(QAbstractListModel):
    """A list of plain dicts; each key is a QML role. Rows keep their identity by `key`."""
    countChanged = Signal()

    def __init__(self, roles, key=None, parent=None):
        super().__init__(parent)
        self._roles = list(roles)
        self._key = key
        self._rows = []

    def roleNames(self):
        return {Qt.UserRole + i: QByteArray(name.encode()) for i, name in enumerate(self._roles)}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        name = self._roles[role - Qt.UserRole] if role >= Qt.UserRole else None
        if name is None:
            return None
        return self._rows[index.row()].get(name)

    def _count(self):
        return len(self._rows)

    count = Property(int, _count, notify=countChanged)

    def rows(self):
        return list(self._rows)

    def get(self, row):
        return dict(self._rows[row]) if 0 <= row < len(self._rows) else {}

    def append(self, item):
        self.beginInsertRows(QModelIndex(), len(self._rows), len(self._rows))
        self._rows.append(dict(item))
        self.endInsertRows()
        self.countChanged.emit()

    def update_last(self, **fields):
        if not self._rows:
            return
        self._rows[-1].update(fields)
        index = self.index(len(self._rows) - 1)
        self.dataChanged.emit(index, index)

    def find(self, value):
        """Row index of the item whose `key` equals value, else -1."""
        return next((i for i, row in enumerate(self._rows) if row.get(self._key) == value), -1)

    def update_key(self, value, **fields):
        row = self.find(value)
        if row < 0:
            return False
        self._rows[row].update(fields)
        index = self.index(row)
        self.dataChanged.emit(index, index)
        return True

    def insert_first(self, item):
        self.beginInsertRows(QModelIndex(), 0, 0)
        self._rows.insert(0, dict(item))
        self.endInsertRows()
        self.countChanged.emit()

    def remove_key(self, value):
        row = self.find(value)
        if row < 0:
            return False
        self.beginRemoveRows(QModelIndex(), row, row)
        del self._rows[row]
        self.endRemoveRows()
        self.countChanged.emit()
        return True

    def remove_first(self, n):
        n = min(n, len(self._rows))
        if n <= 0:
            return
        self.beginRemoveRows(QModelIndex(), 0, n - 1)
        del self._rows[:n]
        self.endRemoveRows()
        self.countChanged.emit()

    def clear(self):
        self.set_rows([])

    def set_rows(self, rows):
        """Replace content; keeps delegates when the identities are unchanged."""
        rows = [dict(r) for r in rows]
        if self._key and len(rows) == len(self._rows) and all(
                a.get(self._key) == b.get(self._key) for a, b in zip(rows, self._rows)):
            for i, row in enumerate(rows):
                if row != self._rows[i]:
                    self._rows[i] = row
                    index = self.index(i)
                    self.dataChanged.emit(index, index)
            return
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()
        self.countChanged.emit()
