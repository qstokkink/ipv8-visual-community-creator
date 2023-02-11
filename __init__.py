import os

import PySide2


dir_name = os.path.dirname(PySide2.__file__)
plugin_path = os.path.join(dir_name, 'plugins', 'platforms')
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = plugin_path
os.environ['QT_API'] = 'pyside2'
os.environ['RYVEN_MODE'] = 'gui'


if __name__ == "__main__":
    from window import run
    run()
