"""Sysadmin Swissknife desktop app (PySide6)."""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QFontDatabase, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QFileDialog, QFormLayout, QFrame, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from . import APP_NAME, __version__
from .subnet import SubnetInfo, SubnetTree, check, parse_network

REPO_URL = "https://github.com/renero82/sysadmin-swissknife"

# (key, header, getter) - optional columns of the splitter table
INFO_COLUMNS = [
    ("netmask", "Netmask", lambda i: i.netmask),
    ("range", "Range of addresses", lambda i: i.address_range),
    ("usable", "Usable IPs", lambda i: i.usable_range),
    ("hosts", "Hosts", lambda i: f"{i.hosts:,}"),
]


def depth_color(depth: int) -> QColor:
    """A distinct, semi-transparent color per level: readable in light and dark mode."""
    hue = (depth * 47 + 200) % 360
    c = QColor.fromHsv(hue, 150, 230)
    c.setAlpha(110)
    return c


def mono_font() -> QFont:
    f = QFontDatabase.systemFont(QFontDatabase.FixedFont)
    return f


# =============================================================================== splitter
class SplitterTab(QWidget):
    def __init__(self, settings: QSettings):
        super().__init__()
        self.settings = settings
        self.tree: SubnetTree | None = None

        root = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel("Network"))
        self.ed_network = QLineEdit()
        self.ed_network.setPlaceholderText("e.g. 192.168.0.0/24  or  10.0.0.0 255.255.0.0")
        self.ed_network.returnPressed.connect(self.update_network)
        top.addWidget(self.ed_network, stretch=1)
        self.btn_update = QPushButton("Update")
        self.btn_update.clicked.connect(self.update_network)
        self.btn_reset = QPushButton("Reset")
        self.btn_reset.setToolTip("Join everything back into the original network")
        self.btn_reset.clicked.connect(self.reset)
        top.addWidget(self.btn_update)
        top.addWidget(self.btn_reset)
        root.addLayout(top)

        opts = QHBoxLayout()
        opts.addWidget(QLabel("Show:"))
        self.cb_columns = {}
        for key, header, _ in INFO_COLUMNS:
            cb = QCheckBox(header)
            cb.setChecked(self.settings.value(f"splitter/show_{key}", "true") == "true")
            cb.toggled.connect(self.refresh)
            self.cb_columns[key] = cb
            opts.addWidget(cb)
        opts.addStretch()
        self.btn_copy = QPushButton("Copy table")
        self.btn_copy.clicked.connect(self.copy_table)
        self.btn_csv = QPushButton("Export CSV\u2026")
        self.btn_csv.clicked.connect(self.export_csv)
        opts.addWidget(self.btn_copy)
        opts.addWidget(self.btn_csv)
        root.addLayout(opts)

        self.lbl_message = QLabel()
        self.lbl_message.setWordWrap(True)
        root.addWidget(self.lbl_message)

        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.cellClicked.connect(self.cell_clicked)
        root.addWidget(self.table, stretch=1)

        self.lbl_summary = QLabel()
        self.lbl_summary.setStyleSheet("color: gray;")
        root.addWidget(self.lbl_summary)

        # restore last session
        net = self.settings.value("splitter/network", "192.168.0.0/24")
        state = self.settings.value("splitter/state", "")
        self.ed_network.setText(net)
        self.load(net, state)

    # ------------------------------------------------------------------ model
    def load(self, net_text: str, state: str = "") -> bool:
        try:
            net, host_bits = parse_network(net_text)
        except ValueError as exc:
            self.show_message(str(exc), error=True)
            return False
        tree = SubnetTree(net)
        if state:
            try:
                from ipaddress import IPv4Network
                tree = SubnetTree.from_leaves(net, [IPv4Network(s) for s in state.split(",")])
            except ValueError:
                tree = SubnetTree(net)
        self.tree = tree
        if host_bits:
            self.show_message(f"Host bits were set: using the network {net}.")
            self.ed_network.setText(str(net))
        else:
            self.show_message("")
        self.refresh()
        return True

    def update_network(self):
        text = self.ed_network.text()
        try:
            net, _ = parse_network(text)
        except ValueError as exc:
            self.show_message(str(exc), error=True)
            return
        if self.tree and self.tree.root.network == net:
            self.show_message("")
            return
        self.load(text)

    def reset(self):
        if self.tree:
            self.tree.root.join()
            self.refresh()

    def show_message(self, text: str, error: bool = False):
        self.lbl_message.setText(text)
        self.lbl_message.setStyleSheet("color: #d64545;" if error else "color: #c98a00;")
        self.lbl_message.setVisible(bool(text))

    # ------------------------------------------------------------------ view
    def visible_columns(self):
        return [(k, h, g) for k, h, g in INFO_COLUMNS if self.cb_columns[k].isChecked()]

    def refresh(self, *_):
        if not self.tree:
            return
        leaves = self.tree.leaves()
        info_cols = self.visible_columns()
        n_join = self.tree.max_depth()
        self.divide_col = 1 + len(info_cols)
        self.join_col0 = self.divide_col + 1
        headers = ["Subnet address"] + [h for _, h, _ in info_cols] + ["Divide"]
        headers += ["Join"] + [""] * (n_join - 1) if n_join else []

        t = self.table
        t.clearSpans()
        t.clear()
        t.setRowCount(len(leaves))
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)
        mono = mono_font()

        for r, leaf in enumerate(leaves):
            info = leaf.info
            item = QTableWidgetItem(info.cidr)
            item.setFont(mono)
            item.setBackground(depth_color(leaf.depth))
            t.setItem(r, 0, item)
            for c, (key, _, getter) in enumerate(info_cols, start=1):
                it = QTableWidgetItem(getter(info))
                it.setFont(mono)
                if key == "hosts":
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                t.setItem(r, c, it)
            btn = QPushButton("Divide")
            btn.setEnabled(leaf.can_divide)
            btn.setToolTip(f"Split {info.cidr} into two /{leaf.network.prefixlen + 1}"
                           if leaf.can_divide else "A /32 cannot be divided")
            btn.clicked.connect(lambda _=False, n=leaf: self.divide(n))
            t.setCellWidget(r, self.divide_col, btn)

        self.join_nodes = {}
        for node, col, first, span in self.tree.join_cells():
            c = self.join_col0 + col
            it = QTableWidgetItem(f"/{node.network.prefixlen}")
            it.setTextAlignment(Qt.AlignCenter)
            it.setBackground(depth_color(node.depth))
            it.setToolTip(f"Click to join back into {node.network}")
            t.setItem(first, c, it)
            if span > 1:
                t.setSpan(first, c, span, 1)
            self.join_nodes[(first, c)] = node

        hh = t.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        for c in range(self.join_col0, t.columnCount()):
            hh.setSectionResizeMode(c, QHeaderView.Fixed)
            t.setColumnWidth(c, 44)

        total_hosts = sum(leaf.info.hosts for leaf in leaves)
        self.lbl_summary.setText(
            f"{self.tree.root.network}  \u2022  {len(leaves)} subnet(s)  \u2022  "
            f"{total_hosts:,} usable hosts in total  \u2022  click a colored Join cell to merge")
        self.save_state()

    def divide(self, node):
        node.divide()
        self.refresh()

    def cell_clicked(self, row, col):
        node = self.join_nodes.get((row, col))
        if node is not None:
            node.join()
            self.refresh()

    # ------------------------------------------------------------------ export
    def table_rows(self):
        cols = self.visible_columns()
        header = ["Subnet address"] + [h for _, h, _ in cols]
        rows = [[leaf.info.cidr] + [g(leaf.info) for _, _, g in cols] for leaf in self.tree.leaves()]
        return header, rows

    def copy_table(self):
        header, rows = self.table_rows()
        text = "\n".join("\t".join(r) for r in [header] + rows)
        QApplication.clipboard().setText(text)
        self.show_message("Table copied to the clipboard (tab separated, ready for Excel/Numbers).")

    def export_csv(self):
        name = f"subnets_{str(self.tree.root.network).replace('/', '_')}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", str(Path.home() / name),
                                              "CSV (*.csv)")
        if not path:
            return
        header, rows = self.table_rows()
        buf = io.StringIO()
        csv.writer(buf).writerows([header] + rows)
        Path(path).write_text(buf.getvalue(), encoding="utf-8")
        self.show_message(f"Exported {len(rows)} rows to {path}")

    def save_state(self):
        if not self.tree:
            return
        s = self.settings
        s.setValue("splitter/network", str(self.tree.root.network))
        s.setValue("splitter/state", self.tree.to_state())
        for key, cb in self.cb_columns.items():
            s.setValue(f"splitter/show_{key}", "true" if cb.isChecked() else "false")


# =============================================================================== checker
class CheckTab(QWidget):
    def __init__(self, settings: QSettings, open_in_splitter):
        super().__init__()
        self.settings = settings
        self.open_in_splitter = open_in_splitter
        root = QVBoxLayout(self)

        form = QFormLayout()
        self.ed_ip = QLineEdit(self.settings.value("check/ip", "192.168.1.10"))
        self.ed_ip.setPlaceholderText("e.g. 192.168.1.10  or  192.168.1.10/32  (a network works too)")
        self.ed_subnet = QLineEdit(self.settings.value("check/subnet", "192.168.1.0/24"))
        self.ed_subnet.setPlaceholderText("e.g. 192.168.1.0/24  or  192.168.1.0 255.255.255.0")
        for ed in (self.ed_ip, self.ed_subnet):
            ed.setFont(mono_font())
            ed.textChanged.connect(self.evaluate)
        form.addRow("IP address", self.ed_ip)
        form.addRow("Subnet", self.ed_subnet)
        root.addLayout(form)

        self.lbl_result = QLabel()
        self.lbl_result.setAlignment(Qt.AlignCenter)
        f = self.lbl_result.font()
        f.setPointSize(f.pointSize() + 10)
        f.setBold(True)
        self.lbl_result.setFont(f)
        self.lbl_result.setMinimumHeight(70)
        root.addWidget(self.lbl_result)

        self.lbl_notes = QLabel()
        self.lbl_notes.setWordWrap(True)
        self.lbl_notes.setAlignment(Qt.AlignCenter)
        root.addWidget(self.lbl_notes)

        box = QGroupBox("Subnet details")
        self.details = QFormLayout(box)
        self.detail_labels = {}
        for key in ("Subnet", "Netmask", "Wildcard", "Network address", "Broadcast address",
                    "Usable range", "Usable hosts", "IP in binary", "Subnet in binary"):
            lbl = QLabel()
            lbl.setFont(mono_font())
            lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            lbl.setTextFormat(Qt.RichText)
            self.detail_labels[key] = lbl
            self.details.addRow(key, lbl)
        root.addWidget(box)

        row = QHBoxLayout()
        row.addStretch()
        self.btn_open = QPushButton("Open this subnet in the Splitter")
        self.btn_open.clicked.connect(self.open_subnet)
        row.addWidget(self.btn_open)
        root.addLayout(row)
        root.addStretch()

        self.result = None
        self.evaluate()

    @staticmethod
    def binary(addr, prefix: int) -> str:
        bits = f"{int(addr):032b}"
        octets = [bits[i:i + 8] for i in range(0, 32, 8)]
        out, n = [], 0
        for o in octets:
            chars = []
            for b in o:
                chars.append(f"<b>{b}</b>" if n < prefix else f"<span style='color:gray'>{b}</span>")
                n += 1
            out.append("".join(chars))
        return ".".join(out)

    def set_banner(self, text: str, color: str):
        self.lbl_result.setText(text)
        self.lbl_result.setStyleSheet(
            f"background-color: {color}; color: white; border-radius: 10px; padding: 8px;")

    def evaluate(self, *_):
        self.settings.setValue("check/ip", self.ed_ip.text())
        self.settings.setValue("check/subnet", self.ed_subnet.text())
        try:
            res = check(self.ed_ip.text(), self.ed_subnet.text())
        except ValueError as exc:
            self.result = None
            self.set_banner("\u2014", "#8a8a8a")
            self.lbl_notes.setText(str(exc))
            for lbl in self.detail_labels.values():
                lbl.setText("")
            self.btn_open.setEnabled(False)
            return
        self.result = res
        if res.status == "inside":
            self.set_banner("\u2713  INSIDE the subnet", "#2e9d4f")
        elif res.status == "partial":
            self.set_banner("\u25d0  PARTIALLY inside", "#c98a00")
        else:
            self.set_banner("\u2717  OUTSIDE the subnet", "#d64545")
        self.lbl_notes.setText("\n".join(n[0].upper() + n[1:] for n in res.notes))

        i = SubnetInfo(res.subnet)
        d = self.detail_labels
        d["Subnet"].setText(i.cidr)
        d["Netmask"].setText(i.netmask)
        d["Wildcard"].setText(i.wildcard)
        d["Network address"].setText(str(i.first))
        d["Broadcast address"].setText(str(i.last))
        d["Usable range"].setText(i.usable_range)
        d["Usable hosts"].setText(f"{i.hosts:,}")
        p = res.subnet.prefixlen
        d["IP in binary"].setText(self.binary(res.candidate.network_address, p))
        d["Subnet in binary"].setText(self.binary(res.subnet.network_address, p))
        self.btn_open.setEnabled(True)

    def open_subnet(self):
        if self.result:
            self.open_in_splitter(str(self.result.subnet))


# =============================================================================== window
class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings | None = None):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(980, 640)
        self.settings = settings or QSettings("renero82", "sysadmin-swissknife")

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.splitter = SplitterTab(self.settings)
        self.checker = CheckTab(self.settings, self.open_in_splitter)
        self.tabs.addTab(self.splitter, "Subnet Splitter")
        self.tabs.addTab(self.checker, "IP in Subnet?")
        self.tabs.setCurrentIndex(int(self.settings.value("window/tab", 0)))
        self.setCentralWidget(self.tabs)

        help_menu = self.menuBar().addMenu("Help")
        about = QAction(f"About {APP_NAME}", self)
        about.setMenuRole(QAction.AboutRole)
        about.triggered.connect(self.about)
        help_menu.addAction(about)
        site = QAction("Project page on GitHub", self)
        site.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(REPO_URL)))
        help_menu.addAction(site)

        quit_action = QAction(self)
        quit_action.setShortcut(QKeySequence.Quit)
        quit_action.triggered.connect(self.close)
        self.addAction(quit_action)

        geom = self.settings.value("window/geometry")
        if geom is not None:
            self.restoreGeometry(geom)

    def open_in_splitter(self, cidr: str):
        self.splitter.ed_network.setText(cidr)
        self.splitter.load(cidr)
        self.tabs.setCurrentWidget(self.splitter)

    def about(self):
        QMessageBox.about(
            self, f"About {APP_NAME}",
            f"<h3>{APP_NAME} {__version__}</h3>"
            "<p>Small network tools for system administrators.</p>"
            f"<p><a href='{REPO_URL}'>{REPO_URL}</a><br>MIT License</p>")

    def closeEvent(self, event):
        self.settings.setValue("window/geometry", self.saveGeometry())
        self.settings.setValue("window/tab", self.tabs.currentIndex())
        self.splitter.save_state()
        event.accept()


# =============================================================================== entry points
def _icon_path() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "assets" / "icon.png"


def selftest(report: str | None = None) -> int:
    """Checks the packaged app. Used by the release workflow: ``--selftest [report.txt]``."""
    import tempfile
    import traceback
    lines = [f"{APP_NAME} {__version__} selftest"]
    code = 0
    tmp = tempfile.TemporaryDirectory()
    try:
        app = QApplication.instance() or QApplication(sys.argv[:1])
        # throw-away settings file: the user's saved layout is never touched
        settings = QSettings(str(Path(tmp.name) / "selftest.ini"), QSettings.IniFormat)
        win = MainWindow(settings)
        sp = win.splitter
        assert sp.load("192.168.0.0/24")
        sp.tree.root.join()
        sp.divide(sp.tree.root)
        sp.divide(sp.tree.root.children[0])
        assert sp.table.rowCount() == 3, sp.table.rowCount()
        assert sp.table.item(0, 0).text() == "192.168.0.0/26"
        sp.cell_clicked(0, sp.join_col0)                  # join the /25 back
        assert sp.table.rowCount() == 2
        lines.append("splitter ok")
        ck = win.checker
        ck.ed_ip.setText("192.168.1.10")
        ck.ed_subnet.setText("192.168.1.0/24")
        assert ck.result and ck.result.status == "inside"
        ck.ed_ip.setText("192.168.2.10")
        assert ck.result.status == "outside"
        lines.append("checker ok")
        win.close()
        lines.append("SELFTEST PASSED")
    except Exception:
        lines.append(traceback.format_exc())
        lines.append("SELFTEST FAILED")
        code = 1
    tmp.cleanup()
    text = "\n".join(lines)
    print(text)
    if report:
        Path(report).write_text(text, encoding="utf-8")
    return code


def main() -> int:
    if "--selftest" in sys.argv:
        i = sys.argv.index("--selftest")
        return selftest(sys.argv[i + 1] if len(sys.argv) > i + 1 else None)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    if _icon_path().exists():
        from PySide6.QtGui import QIcon
        app.setWindowIcon(QIcon(str(_icon_path())))
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
