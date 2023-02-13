import sys
from functools import wraps

from PySide2.QtWidgets import QFileDialog
from qtpy.QtGui import QFontDatabase
from qtpy.QtWidgets import QApplication
from ryven import NodesPackage
from ryven.gui.main_console import init_main_console, MainConsole
from ryven.gui.main_window import MainWindow
from ryven.gui.styling.window_theme import apply_stylesheet
from ryven.main.utils import abs_path_from_package_dir
from ryvencore.NodePort import NodePort
from ryvencore_qt.src.flows.connections.ConnectionItem import ConnectionItem
from shiboken2 import shiboken2

from exporter import Exporter
from nodes import nodes


class IPv8VisualProgrammer(MainWindow):
    """
    This class hot-patches the Ryven MainWindow to remove elements that are not needed for IPv8 Community design.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        MainConsole.instance.deleteLater()

    def import_nodes(self, package: NodesPackage = None, path: str = None):
        self.session.register_nodes(nodes)

        for n in nodes:
            self.node_packages[n] = NodesPackage(".")

        self.nodes_list_widget.update_list(self.session.nodes)

    def setup_menu_actions(self):
        super().setup_menu_actions()

        self.ui.actionImport_Nodes.setText("Load Project")
        self.ui.actionImport_Example_Nodes.setText("Export as IPv8 Code")
        self.ui.menuDebugging.deleteLater()
        self.ui.menuScripts.deleteLater()
        self.ui.scripts_groupBox.deleteLater()

        self.session.create_script("workspace")

    def remove_workspace_garbage(self):
        for workspace_pane in list(self.script_UIs.values()):
            if shiboken2.isValid(workspace_pane.ui.contents_widget):
                # Removals
                workspace_pane.ui.contents_widget.deleteLater()
                workspace_pane.ui.source_code_groupBox.deleteLater()
                workspace_pane.flow_view._stylus_modes_widget.deleteLater()
                workspace_pane.flow_view.set_stylus_proxy_pos = lambda: None

                # Overwrites
                @wraps(workspace_pane.flow_view._add_connection_item)
                def connection_item_added_overwrite(item: ConnectionItem):
                    nonlocal workspace_pane
                    connection_item_added_overwrite.__wrapped__(item)

                    def remove_on_click(event):
                        nonlocal item
                        nonlocal workspace_pane
                        workspace_pane.flow_view.flow.remove_connection(item.connection)

                    item.mousePressEvent = remove_on_click

                workspace_pane.flow_view._add_connection_item = connection_item_added_overwrite

                @wraps(workspace_pane.flow_view.flow.check_connection_validity)
                def check_connection_validity_overwrite(p1: NodePort, p2: NodePort):
                    nonlocal workspace_pane
                    valid = True

                    # Custom checks
                    p1_is_single = p1.label_str in getattr(p1.node, "singleton_ports", [])
                    p2_is_single = p2.label_str in getattr(p2.node, "singleton_ports", [])
                    if p1_is_single and len(p1.connections) > 0:
                        valid = False
                    if p2_is_single and len(p2.connections) > 0:
                        valid = False

                    if valid:
                        return check_connection_validity_overwrite.__wrapped__(p1, p2)
                    else:
                        return False


                workspace_pane.flow_view.flow.check_connection_validity = check_connection_validity_overwrite

    def on_import_nodes_triggered(self):
        """
        Overwritten -> now "Load Project" action.
        """
        file_path = QFileDialog.getOpenFileName(self, 'select nodes file', '.', '(*.json)', )[0]
        if file_path != '':
            self.ui.scripts_tab_widget.removeTab(0)
            import json
            with open(file_path, 'r') as fp:
                self.session.load(json.load(fp))

    def on_import_example_nodes_triggered(self):
        """
        Overwritten -> now "Export" action.
        """
        # Dialog to select save file
        file_path = QFileDialog.getSaveFileName(self, 'select file name', '', 'PY(*.py)')[0]
        if file_path != '':
            exporter = Exporter(self.session.all_node_objects())
            exporter.export(file_path)

    def script_created(self, script, flow_view):
        super().script_created(script, flow_view)
        self.remove_workspace_garbage()


def run():
    app = QApplication(sys.argv)
    db = QFontDatabase()
    db.addApplicationFont(abs_path_from_package_dir('resources/fonts/poppins/Poppins-Medium.ttf'))
    db.addApplicationFont(abs_path_from_package_dir('resources/fonts/source_code_pro/SourceCodePro-Regular.ttf'))
    db.addApplicationFont(abs_path_from_package_dir('resources/fonts/asap/Asap-Regular.ttf'))

    window_theme_name='dark'
    window_theme = apply_stylesheet(window_theme_name)
    editor_init_config = {'action': None}
    flow_theme = 'pure dark' if window_theme.name == 'dark' else 'pure light'

    init_main_console(window_theme)

    editor = IPv8VisualProgrammer(editor_init_config, "IPv8 Visual Community Creator", window_theme, flow_theme)
    editor.show()
    sys.exit(app.exec_())
