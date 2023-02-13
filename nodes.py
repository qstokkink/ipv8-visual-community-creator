from functools import reduce

import PySide2
from PySide2.QtCore import Signal, Qt
from PySide2.QtGui import QDoubleValidator, QValidator
from PySide2.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QComboBox, QHBoxLayout
from ryven import init_node_env, export_nodes
from ryven.NWENV import export_widgets, init_node_widget_env
from ryvencore_qt import Node, NodeInputBP, NodeOutputBP

init_node_env()
init_node_widget_env()


class QClickableLabel(QLabel):
    clicked=Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)

        self.setAlignment(Qt.AlignHCenter)

    def mousePressEvent(self, ev):
        self.clicked.emit()


class CustomWidgetBase(QWidget):

    def get_state(self):
        return None

    def set_state(self, state):
        pass

    def remove_event(self):
        pass

    def log_error(self, text):
        self.node.script.logs_manager.default_loggers["errors"].error(text)

    def log_info(self, text):
        self.node.script.logs_manager.default_loggers["global"].info(text)


class LogInParentMixIn:

    def find_parent(self):
        parent = self.parent()
        while parent is not None and not isinstance(parent, CustomWidgetBase):
            parent = parent.parent()
        return parent

    def log_error(self, text):
        parent = self.find_parent()
        if parent is None:
            raise RuntimeError("Unable to log without proper chain of parent widgets!")
        else:
            parent.log_error(text)

    def log_info(self, text):
        parent = self.find_parent()
        if parent is None:
            raise RuntimeError("Unable to log without proper chain of parent widgets!")
        else:
            parent.log_info(text)


class FieldNameValidator(QValidator, LogInParentMixIn):

    def _fix_next(self, current, element):
        if not current:
            return element if element.isidentifier() else ""
        proposed = current + element
        return proposed if proposed.isidentifier() else current

    def fixup(self, arg__1: str) -> None:
        reduce(self._fix_next, arg__1, "")
        super().fixup(arg__1)

    def validate(self, arg__1: str, arg__2: int) -> PySide2.QtGui.QValidator.State:
        if arg__1.isidentifier():
            return QValidator.Acceptable
        self.log_error(f"\"{arg__1}\" cannot be used as a field name!")
        return QValidator.Invalid


class DataTypeRowWidget(QWidget):

    def __init__(self, parent=None, field_name=None, field_type=None):
        super().__init__(parent=parent)

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setLayout(QHBoxLayout())

        self.line_edit = QLineEdit()
        self.line_edit.setValidator(FieldNameValidator(parent=self))
        self.line_edit.setPlaceholderText('field name')

        self.type_edit = QComboBox()
        self.type_edit.addItem("str")
        self.type_edit.addItem("int")
        self.type_edit.addItem("float")
        self.type_edit.addItem("object")
        self.type_edit.setMinimumContentsLength(7)

        if field_name is not None:
            self.line_edit.setText(field_name)
        if field_type is not None:
            self.type_edit.setCurrentIndex(self.type_edit.findText(field_type))

        self.layout().addWidget(self.line_edit)
        self.layout().addWidget(self.type_edit)

        self.setMinimumWidth(200)
        self.line_edit.show()
        self.type_edit.show()

        self.last_field_value = ""
        self.last_type_value = "str"

        self.line_edit.editingFinished.connect(self.field_updated)
        self.type_edit.currentIndexChanged.connect(self.field_updated)

    def field_updated(self):
        node = self.parent().parent().node
        field_dict: dict = node.custom_fields_dict
        # 1. Remove previous entry from node, if it exists
        if self.last_field_value in field_dict:
            field_dict.pop(self.last_field_value)
        # 2. Add new entry
        new_field_value = self.line_edit.text()
        new_type_value = self.type_edit.itemText(self.type_edit.currentIndex())
        field_dict[new_field_value] = new_type_value
        # 3. Update new last values
        self.last_field_value = new_field_value
        self.last_type_value = new_type_value


class DataTypeTableWidget(QWidget):

    def __init__(self, parent=None, field_items=[]):
        super().__init__(parent=parent)

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setLayout(QVBoxLayout())

        self.rows = []

        self.expansion_pane = QWidget(parent=self)
        self.expansion_pane.setAttribute(Qt.WA_TranslucentBackground, True)
        self.expansion_pane.setAttribute(Qt.WA_NoSystemBackground, True)
        self.expansion_pane.setLayout(QHBoxLayout())
        self.add_button = QClickableLabel("+", parent=self)
        self.add_button.clicked.connect(self.add_row)
        self.remove_button = QClickableLabel("-", parent=self)
        self.remove_button.clicked.connect(self.remove_row)
        self.remove_button.hide()
        self.expansion_pane.layout().addWidget(self.add_button)
        self.expansion_pane.layout().addWidget(self.remove_button)

        for item in field_items:
            field_name, field_type = item
            self.add_row(field_name, field_type)

        self.layout().addWidget(self.expansion_pane)

    def refresh(self):
        self.parent().node_item.update_shape()

    def add_row(self, field_name=None, field_type=None):
        line_pane = DataTypeRowWidget(parent=self, field_name=field_name, field_type=field_type)
        if self.rows:
            self.layout().insertWidget(len(self.rows), line_pane)
        else:
            self.layout().insertWidget(0, line_pane)
            self.remove_button.show()
        self.rows.append(line_pane)
        line_pane.show()
        self.refresh()

    def remove_row(self):
        if self.rows:
            to_remove = self.rows.pop(len(self.rows)-1)
            self.layout().removeWidget(to_remove)
            if len(self.rows) == 0:
                self.remove_button.hide()
            to_remove.deleteLater()
            self.refresh()


class MessageWidget(CustomWidgetBase):
    def __init__(self, params):
        super().__init__()

        self.node, self.node_item = params

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)

        self.setLayout(QVBoxLayout())
        self.fields_table = DataTypeTableWidget(parent=self)
        self.layout().addWidget(self.fields_table)

    def get_state(self):
        return self.node.custom_fields_dict

    def set_state(self, state):
        self.node.custom_fields_dict = state
        for item in state.items():
            field_name, field_type = item
            self.fields_table.add_row(field_name, field_type)


class MessageNode(Node):
    title = 'Message'
    init_inputs = [
        NodeInputBP("received_by", type_="peer"),
        NodeInputBP("retrieve_cache", type_="cache")
    ]
    init_outputs = [
        NodeOutputBP("response", type_="peer"),
        NodeOutputBP("create_cache", type_="message")
    ]
    singleton_ports = [
        "received_by",
        "retrieve_cache",
        "response",
        "create_cache"
    ]
    color = '#A9D5EF'
    __class_codes__ = None
    main_widget_class = MessageWidget

    unique_message_num = 0

    def __init__(self, params):
        super().__init__(params)
        self.set_display_title(f"{MessageNode.title}{MessageNode.unique_message_num}")
        MessageNode.unique_message_num += 1

        self.custom_fields_dict = {}

    def init_default_actions(self) -> dict:
        actions = {
            'update shape': {'method': self.update_shape},
            'hide unconnected ports': {'method': self.hide_unconnected_ports},
            'change Message name': {'method': self.change_title}
        }
        return actions

    def additional_data(self) -> dict:
        out = super().additional_data()
        out["custom_fields_dict"] = self.custom_fields_dict
        return out

    def load_additional_data(self, data):
        super().load_additional_data(data)

        self.custom_fields_dict = data["custom_fields_dict"]


class CacheWidget(CustomWidgetBase):
    def __init__(self, params):
        super().__init__()

        self.node, self.node_item = params

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)

        self.setLayout(QVBoxLayout())
        self.fields_table = DataTypeTableWidget(parent=self)
        self.layout().addWidget(self.fields_table)

    def get_state(self):
        return self.node.custom_fields_dict

    def set_state(self, state):
        self.node.custom_fields_dict = state
        for item in state.items():
            field_name, field_type = item
            self.fields_table.add_row(field_name, field_type)


class CacheNode(Node):
    title = 'Cache'
    init_inputs = [
        NodeInputBP("belongs_to", type_="message"),
    ]
    init_outputs = [
        NodeOutputBP("received_by", type_="cache")
    ]
    singleton_ports = [
        "belongs_to",
        "received_by"
    ]
    color = '#448aff'
    __class_codes__ = None
    main_widget_class = CacheWidget

    unique_cache_num = 0

    def __init__(self, params):
        super().__init__(params)
        self.set_display_title(f"{CacheNode.title}{CacheNode.unique_cache_num}")
        CacheNode.unique_cache_num += 1

        self.custom_fields_dict = {}

    def init_default_actions(self) -> dict:
        actions = {
            'update shape': {'method': self.update_shape},
            'hide unconnected ports': {'method': self.hide_unconnected_ports},
            'change Cache name': {'method': self.change_title}
        }
        return actions

    def additional_data(self) -> dict:
        out = super().additional_data()
        out["custom_fields_dict"] = self.custom_fields_dict
        return out

    def load_additional_data(self, data):
        super().load_additional_data(data)

        self.custom_fields_dict = data["custom_fields_dict"]


class AllPeersNode(Node):
    title = 'AllPeers'
    init_inputs = [
        NodeInputBP("select", type_="task"),
    ]
    init_outputs = [
        NodeOutputBP("message", type_="peer")
    ]
    singleton_ports = [
    ]
    color = '#8aff44'
    __class_codes__ = None

    def init_default_actions(self) -> dict:
        actions = {
            'update shape': {'method': self.update_shape},
            'hide unconnected ports': {'method': self.hide_unconnected_ports}
        }
        return actions


class RandomPeerNode(Node):
    title = 'RandomPeer'
    init_inputs = [
        NodeInputBP("select", type_="task"),
    ]
    init_outputs = [
        NodeOutputBP("message", type_="peer")
    ]
    singleton_ports = [
    ]
    color = '#8aff44'
    __class_codes__ = None

    def init_default_actions(self) -> dict:
        actions = {
            'update shape': {'method': self.update_shape},
            'hide unconnected ports': {'method': self.hide_unconnected_ports}
        }
        return actions


class LoggingDoubleValidator(QDoubleValidator, LogInParentMixIn):

    def validate(self, arg__1:str, arg__2:int) -> PySide2.QtGui.QValidator.State:
        out = super().validate(arg__1, arg__2)
        if isinstance(out, tuple) and out[0] == QValidator.Invalid:
            self.log_error(f"\"{arg__1}\" is not a valid Double value!")
        return out


class PeriodicTaskWidget(CustomWidgetBase):
    def __init__(self, params):
        super().__init__()

        self.node, self.node_item = params

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)

        self.setLayout(QVBoxLayout())
        validator = LoggingDoubleValidator(parent=self)
        line_edit = QLineEdit()
        line_edit.setValidator(validator)
        line_edit.setPlaceholderText('1.0')
        line_edit.editingFinished.connect(self.interval_updated)
        self.editor = line_edit
        self.layout().addWidget(line_edit)

    def interval_updated(self):
        self.node.set_interval(float(self.editor.text()))

    def get_state(self):
        return self.editor.text()

    def set_state(self, state):
        self.editor.setText(state)


class PeriodicTaskNode(Node):
    title = 'PeriodicTask'
    init_inputs = [
    ]
    init_outputs = [
        NodeOutputBP("on_timer_fire", type_="task")
    ]
    color = '#ff448a'
    __class_codes__ = None
    main_widget_class = PeriodicTaskWidget

    def __init__(self, params):
        super().__init__(params)

        self.interval = 1.0

    def additional_data(self) -> dict:
        out = super().additional_data()
        out["interval"] = self.interval
        return out

    def load_additional_data(self, data):
        super().load_additional_data(data)

        self.interval = data["interval"]

    def set_interval(self, value):
        self.interval = value

    def init_default_actions(self) -> dict:
        actions = {
            'update shape': {'method': self.update_shape},
            'hide unconnected ports': {'method': self.hide_unconnected_ports}
        }
        return actions


nodes = [AllPeersNode, CacheNode, MessageNode, PeriodicTaskNode, RandomPeerNode]
widgets = [CacheWidget, MessageWidget, PeriodicTaskWidget]
export_nodes(*nodes)
export_widgets(*widgets)
