"""MOTD Builder tab."""
from __future__ import annotations

import html
import json
import os
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QScrollArea, QSplitter,
    QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from .motd import (COLORS, FONTS, FRAMES, ICONS, INFO_FIELDS, LEGAL_EN, LEGAL_IT, PREVIEW_COLORS,
                   TARGETS, MotdConfig, build)


def mono():
    return QFontDatabase.systemFont(QFontDatabase.FixedFont)


class MotdTab(QWidget):
    def __init__(self, settings: QSettings):
        super().__init__()
        self.settings = settings
        self.result = None
        self._loading = True

        split = QSplitter(Qt.Horizontal)
        root = QHBoxLayout(self)
        root.addWidget(split)

        # ------------------------------------------------------------ controls (left)
        controls = QWidget()
        cl = QVBoxLayout(controls)

        banner = QGroupBox("Banner")
        bf = QFormLayout(banner)
        self.ed_banner = QLineEdit()
        self.ed_banner.setPlaceholderText("e.g. the server name")
        self.cmb_font = QComboBox()
        self.cmb_font.addItems(FONTS)
        self.cmb_color = self._color_combo()
        self.cmb_icon = QComboBox()
        self.cmb_icon.addItems(list(ICONS))
        self.cmb_frame = QComboBox()
        self.cmb_frame.addItems(list(FRAMES))
        self.cb_center = QCheckBox("Center")
        bf.addRow("Text", self.ed_banner)
        bf.addRow("ASCII font", self.cmb_font)
        bf.addRow("Color", self.cmb_color)
        bf.addRow("Icon", self.cmb_icon)
        frame_row = QHBoxLayout()
        frame_row.addWidget(self.cmb_frame, stretch=1)
        frame_row.addWidget(self.cb_center)
        bf.addRow("Frame", frame_row)
        cl.addWidget(banner)

        msg = QGroupBox("Message")
        ml = QVBoxLayout(msg)
        self.ed_message = QPlainTextEdit()
        self.ed_message.setPlaceholderText("Free text shown under the banner (optional)")
        self.ed_message.setMaximumHeight(90)
        ml.addWidget(self.ed_message)
        mrow = QHBoxLayout()
        mrow.addWidget(QLabel("Color"))
        self.cmb_msg_color = self._color_combo()
        mrow.addWidget(self.cmb_msg_color, stretch=1)
        b_en = QPushButton("Legal warning EN")
        b_en.clicked.connect(lambda: self.ed_message.setPlainText(LEGAL_EN))
        b_it = QPushButton("Legal warning IT")
        b_it.clicked.connect(lambda: self.ed_message.setPlainText(LEGAL_IT))
        mrow.addWidget(b_en)
        mrow.addWidget(b_it)
        ml.addLayout(mrow)
        cl.addWidget(msg)

        info = QGroupBox("System information (dynamic scripts only)")
        il = QVBoxLayout(info)
        grid = QGridLayout()
        self.cb_info = {}
        for n, (key, (label, _, _)) in enumerate(INFO_FIELDS.items()):
            cb = QCheckBox(label)
            self.cb_info[key] = cb
            grid.addWidget(cb, n // 3, n % 3)
        il.addLayout(grid)
        irow = QHBoxLayout()
        irow.addWidget(QLabel("Color"))
        self.cmb_info_color = self._color_combo()
        irow.addWidget(self.cmb_info_color, stretch=1)
        il.addLayout(irow)
        self.info_box = info
        cl.addWidget(info)

        out = QGroupBox("Output")
        of = QFormLayout(out)
        self.cmb_target = QComboBox()
        for key, (label, _) in TARGETS.items():
            self.cmb_target.addItem(label, key)
        of.addRow("Type", self.cmb_target)
        cl.addWidget(out)
        cl.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(controls)
        scroll.setMinimumWidth(380)
        split.addWidget(scroll)

        # ------------------------------------------------------------ preview (right)
        right = QWidget()
        rl = QVBoxLayout(right)
        self.views = QTabWidget()
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QTextEdit.NoWrap)
        self.preview.setStyleSheet("QTextEdit { background: #1e1e1e; color: #d0d0d0; }")
        self.preview.setFont(mono())
        self.source = QPlainTextEdit()
        self.source.setReadOnly(True)
        self.source.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.source.setFont(mono())
        self.views.addTab(self.preview, "Terminal preview")
        self.views.addTab(self.source, "File content")
        rl.addWidget(self.views, stretch=3)

        self.lbl_warn = QLabel()
        self.lbl_warn.setWordWrap(True)
        self.lbl_warn.setStyleSheet("color: #c98a00;")
        rl.addWidget(self.lbl_warn)

        inst = QGroupBox("How to install it")
        il2 = QVBoxLayout(inst)
        self.install = QPlainTextEdit()
        self.install.setReadOnly(True)
        self.install.setFont(mono())
        self.install.setMaximumHeight(110)
        il2.addWidget(self.install)
        rl.addWidget(inst)

        brow = QHBoxLayout()
        brow.addStretch()
        self.btn_copy = QPushButton("Copy file content")
        self.btn_copy.clicked.connect(self.copy)
        self.btn_save = QPushButton("Save\u2026")
        self.btn_save.clicked.connect(self.save)
        brow.addWidget(self.btn_copy)
        brow.addWidget(self.btn_save)
        rl.addLayout(brow)
        split.addWidget(right)
        split.setStretchFactor(1, 1)

        # ------------------------------------------------------------ signals + state
        self.load_state()
        for w in (self.ed_banner,):
            w.textChanged.connect(self.refresh_motd)
        self.ed_message.textChanged.connect(self.refresh_motd)
        for w in (self.cmb_font, self.cmb_color, self.cmb_icon, self.cmb_frame, self.cmb_msg_color,
                  self.cmb_info_color, self.cmb_target):
            w.currentIndexChanged.connect(self.refresh_motd)
        self.cb_center.toggled.connect(self.refresh_motd)
        for cb in self.cb_info.values():
            cb.toggled.connect(self.refresh_motd)
        self._loading = False
        self.refresh_motd()

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _color_combo():
        c = QComboBox()
        c.addItems(list(COLORS))
        return c

    def config(self) -> MotdConfig:
        return MotdConfig(
            banner=self.ed_banner.text(),
            font=self.cmb_font.currentText(),
            banner_color=self.cmb_color.currentText(),
            icon=self.cmb_icon.currentText(),
            frame=self.cmb_frame.currentText(),
            center=self.cb_center.isChecked(),
            message=self.ed_message.toPlainText(),
            message_color=self.cmb_msg_color.currentText(),
            info=[k for k, cb in self.cb_info.items() if cb.isChecked()],
            info_color=self.cmb_info_color.currentText(),
            target=self.cmb_target.currentData(),
        )

    def refresh_motd(self, *_):
        if self._loading:
            return
        cfg = self.config()
        dynamic = cfg.target != "static"
        self.info_box.setEnabled(dynamic)
        if not dynamic:
            cfg.info = []
        res = build(cfg)
        self.result = res

        rows = []
        for segs in res.preview:
            row = "".join(
                f"<span style='color:{PREVIEW_COLORS.get(c or None, '#d0d0d0')}'>"
                f"{html.escape(t)}</span>" for t, c in segs)
            rows.append(row or "&nbsp;")
        self.preview.setHtml(
            "<pre style='font-family: monospace; margin: 8px'>" + "\n".join(rows) + "</pre>")
        self.source.setPlainText(res.content.replace("\x1b", "\\e") if not dynamic else res.content)
        self.install.setPlainText(res.install)
        self.lbl_warn.setText("\n".join(res.warnings))
        self.lbl_warn.setVisible(bool(res.warnings))
        self.save_state()

    def copy(self):
        if self.result:
            QApplication.clipboard().setText(self.result.content)

    def save(self):
        if not self.result:
            return
        start = str(Path.home() / self.result.filename)
        path, _ = QFileDialog.getSaveFileName(self, "Save MOTD", start)
        if not path:
            return
        Path(path).write_text(self.result.content, encoding="utf-8", newline="\n")
        if self.result.content.startswith("#!"):
            try:
                os.chmod(path, 0o755)
            except OSError:
                pass

    # ---------------------------------------------------------------- persistence
    def save_state(self):
        if self._loading:
            return
        cfg = self.config()
        self.settings.setValue("motd/config", json.dumps(cfg.__dict__))

    def load_state(self):
        try:
            data = json.loads(self.settings.value("motd/config", "") or "{}")
        except ValueError:
            data = {}
        cfg = MotdConfig(**{k: v for k, v in data.items() if k in MotdConfig.__dataclass_fields__})
        self.ed_banner.setText(cfg.banner)
        for combo, value in ((self.cmb_font, cfg.font), (self.cmb_color, cfg.banner_color),
                             (self.cmb_icon, cfg.icon), (self.cmb_frame, cfg.frame),
                             (self.cmb_msg_color, cfg.message_color),
                             (self.cmb_info_color, cfg.info_color)):
            i = combo.findText(value)
            if i >= 0:
                combo.setCurrentIndex(i)
        self.cb_center.setChecked(cfg.center)
        self.ed_message.setPlainText(cfg.message)
        for k, cb in self.cb_info.items():
            cb.setChecked(k in cfg.info)
        i = self.cmb_target.findData(cfg.target)
        if i >= 0:
            self.cmb_target.setCurrentIndex(i)
