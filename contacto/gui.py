"""A Qt5 frontend for Contacto

For now it it read-only.
"""
from PyQt5 import QtWidgets, uic
import sys
import pkgutil
import io
from .storage import Storage
from .serial import Serial
from .helpers import DType, attr_val_str, print_error


MAIN_UI = 'resources/mainwindow.ui'
ABOUT_HTML = 'resources/about.html'


class GUI:
    """Wrapper for all GUI logic
    """
    def __init__(self):
        """GUI initializer

        Allows passing DB name from args
        """
        self.app = QtWidgets.QApplication(sys.argv)
        self.app.setApplicationName("Contacto")

        # initialize from args
        if len(sys.argv) > 1:
            fname = sys.argv[1]
        else:
            fname = ':memory:'
        self.open(fname)

        script = pkgutil.get_data(__name__, MAIN_UI).decode('utf-8')
        sio = io.StringIO(script)

        # load main window
        self.window = QtWidgets.QMainWindow()
        uic.loadUi(sio, self.window)

        # load main UI areas
        self.tree = self.window.findChild(QtWidgets.QTreeWidget, 'treeWidget')
        self.tree.setColumnWidth(0, 200)
        self.init_tree()

        # actions
        act = self.window.findChild(QtWidgets.QAction, 'actionOpen')
        act.triggered.connect(self.action_open)
        act = self.window.findChild(QtWidgets.QAction, 'actionAbout')
        act.triggered.connect(self.action_about)
        act = self.window.findChild(QtWidgets.QAction, 'actionImport_from')
        act.triggered.connect(self.action_import)
        act = self.window.findChild(QtWidgets.QAction, 'actionExport_to')
        act.triggered.connect(self.action_export)

    @staticmethod
    def __type_to_str(dtype):
        """Returns a string representation of attribute type

        :param dtype: attribute data type
        :type dtype:  class:`contacto.helpers.DType`
        :return: string representation
        :rtype:  str
        """
        tstr = '???'
        if dtype is DType.BIN:
            tstr = "binary"
        elif dtype is DType.TEXT:
            tstr = "text"
        elif dtype is DType.AXREF:
            tstr = "-> attr"
        elif dtype is DType.EXREF:
            tstr = "-> entity"
        return f"Attr ({tstr})"

    def open(self, dbname):
        """Open a new Storage around a filename

        :param dbname: name of database holding raw data
        :type  dbname: str
        """
        self.storage = Storage(dbname)
        self.serial = Serial(self.storage)
        self.filename = dbname

    def init_tree(self):
        """Loads contact data into the tree widget
        """
        for gname, group in sorted(self.storage.groups.items()):
            gitem = QtWidgets.QTreeWidgetItem(self.tree)
            gitem.setText(0, gname)
            gitem.setText(1, "Group")
            for ename, entity in sorted(group.entities.items()):
                eitem = QtWidgets.QTreeWidgetItem(gitem)
                eitem.setText(0, ename)
                eitem.setText(1, "Entity")
                for aname, attr in sorted(entity.attributes.items()):
                    aitem = QtWidgets.QTreeWidgetItem(eitem)
                    aitem.setText(0, aname)
                    aitem.setText(1, self.__type_to_str(attr.type))
                    aitem.setText(2, attr_val_str(attr, False))

    def action_open(self):
        """Qt action: open new DB
        """
        fname = QtWidgets.QFileDialog.getOpenFileName()[0]
        if not fname:
            return
        try:
            self.open(fname)
            self.init_tree()
        except Exception as e:
            print_error(str(e))
            QtWidgets.QMessageBox.critical(self.window, 'Load error', str(e))

    def action_about(self):
        """Qt action: display About dialog
        """
        about_str = pkgutil.get_data(__name__, ABOUT_HTML).decode('utf-8')
        QtWidgets.QMessageBox.about(self.window, 'About Contacto', about_str)

    def action_import(self):
        """Qt action: import a YAML file
        """
        yml_filt = "YAML files (*.yml)"
        fname = QtWidgets.QFileDialog.getOpenFileName(filter=yml_filt)[0]
        if not fname:
            return
        try:
            serial = Serial(self.storage)
            with open(fname, 'r') as f:
                if not serial.import_yaml(f):
                    raise Exception("YAML import failed")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self.window, 'Import error', str(e))

    def action_export(self):
        """Qt action: export DB into a YAML file
        """
        yml_filt = "YAML files (*.yml)"
        fname = QtWidgets.QFileDialog.getSaveFileName(filter=yml_filt)[0]
        if not fname:
            return
        try:
            serial = Serial(self.storage)
            with open(fname, 'w') as f:
                if not serial.export_yaml(f):
                    raise Exception("YAML export failed")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self.window, 'Export error', str(e))

    def run(self):
        """Object entry-point (open and run)
        """
        self.window.show()
        return self.app.exec()


def main():
    """GUI entry-point
    """
    gui = GUI()
    gui.run()


# allow running GUI directly via "python -m contacto.gui"
if __name__ == '__main__':
    main()
