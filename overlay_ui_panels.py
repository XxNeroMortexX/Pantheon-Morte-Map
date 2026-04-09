from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QIcon, QFont
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QListWidget,
    QComboBox,
    QSizePolicy,
    QCheckBox,
    QScrollArea,
    QGraphicsDropShadowEffect,
)

from app_settings import (
    DEFAULT_OPACITY,
    LOWER_LAYER_OPACITY,
    MAP_DEFINITIONS,
    PANEL_WIDTH,
    TOP_BAR_HEIGHT,
    WINDOW_ICON_PATH,
    theme_q,
)
from ui_panel import Panel
from ui_canvas import MapCanvas


class OverlayUIPanelsMixin:
    """Mixin class to provide UI panels, top bar, and overlay controls for the map window."""

    # Build UI / top bar / panels
    def _build_ui(self):
        """Construct the main UI including top bar, buttons, coordinate labels, flash label, and panels."""
       
        self.setWindowIcon(QIcon(WINDOW_ICON_PATH))

        root = QWidget(self)
        self.setCentralWidget(root)
        root.setStyleSheet("background: transparent;")

        # Canvas behind everything
        self.canvas = MapCanvas(self)
        self.canvas.setParent(root)
        self.canvas.setGeometry(0, 0, self.width(), self.height())

        # Top bar
        self.top_bar = Panel(root)
        self.top_bar.setFixedHeight(TOP_BAR_HEIGHT)
        main_layout = QVBoxLayout(self.top_bar)
        main_layout.setContentsMargins(6, 4, 6, 4)
        main_layout.setSpacing(0)

        top_row = QHBoxLayout()
        top_row.setSpacing(5)
        top_row.setAlignment(Qt.AlignCenter)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(5)
        bottom_row.setAlignment(Qt.AlignCenter)

        main_layout.addLayout(top_row, 1)
        main_layout.addLayout(bottom_row, 1)

        def mk(text, bg, tip="", w=42):
            b = QPushButton(text)
            b.setFixedSize(w, 26)
            b.setToolTip(tip)
            b.setStyleSheet(
                f"QPushButton{{background:{bg};color:white;border:none;"
                f"font-weight:bold;font-size:12px;border-radius:4px;}}"
                f"QPushButton:hover{{background:#fff;color:#111;}}"
            )
            return b

        # Map selector
        self.map_combo = QComboBox()
        self.map_combo.addItems(list(MAP_DEFINITIONS.keys()))
        self.map_combo.setFixedHeight(26)
        self.map_combo.setMinimumWidth(150)
        self.map_combo.setStyleSheet(
            "QComboBox{background:#1a2030;color:#c8d8f0;border:1px solid rgba(255,255,255,40);"
            "border-radius:4px;font-size:12px;font-weight:bold;padding:0 8px;}"
            "QComboBox:hover{background:#243050;border-color:rgba(255,255,255,80);}"
            "QComboBox::drop-down{border:none;width:20px;}"
            "QComboBox::down-arrow{image:none;}"
            "QComboBox QAbstractItemView{background:#1a2030;color:#c8d8f0;"
            "border:1px solid rgba(255,255,255,40);selection-background-color:#2a4080;}"
        )
        self.map_combo.currentTextChanged.connect(self._on_map_changed)
        top_row.addWidget(self.map_combo)

        sep = QLabel("|")
        sep.setStyleSheet("color:rgba(255,255,255,30);background:transparent;")
        top_row.addWidget(sep)

        # Toolbar buttons
        self.btn_zoom_in = mk("+", "#555", "Zoom in", 30)
        self.btn_zoom_out = mk("−", "#555", "Zoom out", 30)
        self.btn_center = mk("⊙", "#2471a3", "Center on player", 30)
        self.btn_layer_pan = mk("LAYERS", "#1e6e3a", "Show/hide layers panel", 60)
        self.btn_cal_list = mk("CAL", "#c0782a", "Show/hide calibration panel", 46)
        self.btn_pin_list = mk("PINS", "#c0392b", "Show/hide pins panel", 46)
        self.btn_markers = mk("MARK", "#117a65", "Named world-coordinate markers (typed)", 50)
        self.btn_update = mk("UPD", "#884ea0", "Download maps/settings (manifest URL in INI)", 40)
        self.btn_opacity = mk(f"{int(DEFAULT_OPACITY * 100)}%", "#444", "Cycle opacity", 44)
        self.btn_settings = mk("SET", "#2c3e50", "Settings (auto-center, auto-zoom on /loc)", 36)

        for b, fn in [
            (self.btn_zoom_in, self._zoom_in),
            (self.btn_zoom_out, self._zoom_out),
            (self.btn_center, self._center_on_player),
            (self.btn_layer_pan, self._toggle_layer_panel),
            (self.btn_cal_list, self._toggle_calib_panel),
            (self.btn_pin_list, self._toggle_pin_panel),
            (self.btn_markers, self._toggle_markers_panel),
            (self.btn_update, self._run_update_check),
            (self.btn_opacity, self._cycle_opacity),
            (self.btn_settings, self._toggle_settings_panel),
        ]:
            b.clicked.connect(fn)
            top_row.addWidget(b)

        # Coord readout labels
        bottom_row.addStretch()
        self.coord_container = QWidget(self.top_bar)
        coord_layout = QHBoxLayout(self.coord_container)
        coord_layout.setSpacing(12)
        coord_layout.setContentsMargins(0, 0, 0, 0)
        self.coord_container.setLayout(coord_layout)
        self.coord_container.show()

        self.coord_labels = {}

        def make_glow_label(name, color="#00ff9c", text=""):
            lbl = QLabel(text)
            lbl.setStyleSheet(
                f"color:{color};"
                "font-size:11px;"
                "font-weight:bold;"
                "font-family:Consolas,monospace;"
                "background-color: rgba(0, 0, 0, 35);"
                "border:2px solid rgba(0,0,0,190);"
                "border-radius:1px;"
                "padding:2px 6px;"
            )
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(2)
            shadow.setColor(QColor(color).lighter(110))
            shadow.setOffset(0, 0)
            lbl.setGraphicsEffect(shadow)
            self.coord_labels[name] = lbl
            coord_layout.addWidget(lbl)
            return lbl

        for name, color in [
            ("Px", "#ffffff"),
            ("Py", "#ffffff"),
            ("Wx", "#00ff00"),
            ("Wy", "#00ff00"),
            ("PlayerX", "#ffd166"),
            ("PlayerY", "#ffd166"),
            ("Zoom", "#66ccff"),
        ]:
            make_glow_label(name, color, text="0")

        bottom_row.addWidget(self.coord_container)
        bottom_row.addStretch()

        # Flash label
        self.flash_lbl = QLabel("", root)
        self.flash_lbl.setStyleSheet(
            "background:rgba(0,0,0,215);color:#f0c040;padding:7px 16px;"
            "border-radius:7px;font-size:13px;font-weight:bold;font-family:Consolas,monospace;"
        )
        self.flash_lbl.setAlignment(Qt.AlignCenter)
        self.flash_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.flash_lbl.hide()
        self.flash_timer = QTimer(self)
        self.flash_timer.setSingleShot(True)
        self.flash_timer.timeout.connect(self.flash_lbl.hide)

        # Panels
        self.layer_panel = self._make_layer_panel(root)
        self.layer_panel.hide()

        self.calib_panel = self._make_calib_panel(root)
        self.calib_panel.hide()

        self.pin_panel = self._make_pin_panel(root)
        self.pin_panel.hide()

        self.markers_panel = self._make_markers_panel(root)
        self.markers_panel.hide()

        self.settings_panel = self._make_settings_panel(root)
        self.settings_panel.hide()

        self._relayout()

    # Settings panel
    def _make_settings_panel(self, parent):
        """Create the settings panel with checkboxes for auto-center and auto-zoom, and informational hints.

        Args:
            parent (QWidget): The parent widget for the settings panel.

        Returns:
            Panel: A custom Panel widget containing the settings UI elements.
        """
        p = Panel(parent)
        v = QVBoxLayout(p)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(10)

        title = QLabel("Settings")
        title.setStyleSheet(
            "color:#aaddff;font-size:14px;font-weight:bold;"
            "background:transparent;border:none;"
        )
        v.addWidget(title)

        loc_lbl = QLabel("Location Update  ( /loc )")
        loc_lbl.setStyleSheet(
            "color:rgba(180,210,255,200);font-size:11px;font-weight:bold;"
            "background:rgba(0,0,0,80);border-radius:3px;padding:4px 6px;border:none;"
        )
        loc_lbl.setWordWrap(True)
        v.addWidget(loc_lbl)

        cb_style = (
            "QCheckBox{color:#c8d8f0;font-size:12px;font-weight:bold;"
            "background:transparent;border:none;spacing:8px;}"
            "QCheckBox::indicator{width:16px;height:16px;"
            "border:2px solid rgba(100,160,220,120);border-radius:3px;"
            "background:rgba(0,0,0,150);}"
            "QCheckBox::indicator:checked{background:#1a5080;border-color:#40a0d0;}"
            "QCheckBox::indicator:hover{border-color:rgba(100,180,255,200);}"
        )

        self.chk_auto_center = QCheckBox("Auto-Center on /loc")
        self.chk_auto_center.setChecked(self.auto_center)
        self.chk_auto_center.setStyleSheet(cb_style)
        self.chk_auto_center.setToolTip(
            "When you copy /loc in-game the map\n"
            "automatically scrolls to center your\n"
            "player dot in the viewport."
        )
        self.chk_auto_center.stateChanged.connect(self._on_auto_center_changed)
        v.addWidget(self.chk_auto_center)

        self.chk_auto_zoom = QCheckBox("Auto-Zoom to 1.0 on /loc")
        self.chk_auto_zoom.setChecked(self.auto_zoom)
        self.chk_auto_zoom.setStyleSheet(cb_style)
        self.chk_auto_zoom.setToolTip(
            "Resets zoom to 1:1 before centering.\n"
            "Best combined with Auto-Center."
        )
        self.chk_auto_zoom.stateChanged.connect(self._on_auto_zoom_changed)
        v.addWidget(self.chk_auto_zoom)

        hint = QLabel(
            "Z Layer tip:\n"
            "Add [map_z_layers] entries in\n"
            "config.ini to auto-switch layers\n"
            "based on your in-game Z height.\n\n"
            "Format:\n"
            "  mapname_Z_LayerName = min,max\n\n"
            "See config.ini comments for details."
        )
        hint.setStyleSheet(
            "color:rgba(160,200,160,180);font-size:10px;font-family:Consolas,monospace;"
            "background:rgba(0,0,0,80);border-radius:4px;padding:6px;border:none;"
        )
        hint.setWordWrap(True)
        v.addWidget(hint)

        v.addStretch()
        return p

    def _on_auto_center_changed(self, state):
        """Update the auto-center setting based on the QCheckBox state.

        Args:
            state (int): The state of the checkbox (Qt.Checked or Qt.Unchecked).
        """
        self.auto_center = state == Qt.Checked

    def _on_auto_zoom_changed(self, state):
        """Update the auto-zoom setting based on the QCheckBox state.

        Args:
            state (int): The state of the checkbox (Qt.Checked or Qt.Unchecked).
        """
        self.auto_zoom = state == Qt.Checked

    def _toggle_settings_panel(self):
        """Toggle the visibility of the settings panel and hide all other panels."""
        
        vis = not self.settings_panel.isVisible()
        self.layer_panel.hide()
        self.calib_panel.hide()
        self.pin_panel.hide()
        self.markers_panel.hide()
        if vis:
            self.chk_auto_center.setChecked(self.auto_center)
            self.chk_auto_zoom.setChecked(self.auto_zoom)
            self.settings_panel.show()
        else:
            self.settings_panel.hide()

    # Layers panel
    def _make_layer_panel(self, parent):
        """Create the map layers panel with scrollable checkboxes and All On/All Off buttons.

        Args:
            parent (QWidget): The parent widget for the layers panel.

        Returns:
            Panel: A custom Panel widget containing the layers UI elements.
        """
        p = Panel(parent)
        v = QVBoxLayout(p)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)

        lbl = QLabel("Map Layers")
        lbl.setStyleSheet(
            "color:#80e880;font-size:14px;font-weight:bold;background:transparent;border:none;"
        )
        v.addWidget(lbl)

        hint = QLabel(
            "Toggle layers on/off.\n"
            "Top visible layer is fully opaque;\n"
            "layers beneath shown at "
            f"{int(LOWER_LAYER_OPACITY*100)}%.\n"
            "One calibration covers all layers."
        )
        hint.setStyleSheet(
            "color:rgba(180,220,180,180);font-size:11px;font-family:Consolas,monospace;"
            "background:rgba(0,0,0,80);border-radius:4px;padding:6px;border:none;"
        )
        hint.setWordWrap(True)
        v.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignTop)
        scroll.setStyleSheet(
            "QScrollArea{background:rgba(0,0,0,130);border:1px solid rgba(255,255,255,30);"
            "border-radius:4px;}"
            "QScrollBar:vertical{background:rgba(0,0,0,0);width:8px;}"
            "QScrollBar::handle:vertical{background:rgba(255,255,255,60);border-radius:4px;}"
        )
        self._layer_scroll_inner = QWidget()
        self._layer_scroll_inner.setStyleSheet("background:transparent;")
        self._layer_checks_layout = QVBoxLayout(self._layer_scroll_inner)
        self._layer_checks_layout.setContentsMargins(6, 6, 6, 6)
        self._layer_checks_layout.setSpacing(6)
        self._layer_checks_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self._layer_scroll_inner)
        v.addWidget(scroll)
        self._layer_checkboxes = []

        row = QHBoxLayout()
        row.setSpacing(6)
        for text, fn in [("All On", self._layers_all_on), ("All Off", self._layers_all_off)]:
            b = QPushButton(text)
            b.setStyleSheet(
                "QPushButton{background:#1e6e3a;color:white;border:none;"
                "font-size:11px;font-weight:bold;border-radius:4px;padding:5px 10px;}"
                "QPushButton:hover{background:#fff;color:#111;}"
            )
            b.clicked.connect(fn)
            row.addWidget(b)
        v.addLayout(row)

        return p

    def _rebuild_layer_panel_content(self):
        """Rebuild the layer panel content to match the current map's layers.

        Clears existing checkboxes and creates new ones based on MAP_DEFINITIONS and current visibility.
        """
        for cb in self._layer_checkboxes:
            self._layer_checks_layout.removeWidget(cb)
            cb.setParent(None)
            cb.deleteLater()
        self._layer_checkboxes.clear()

        layer_defs = MAP_DEFINITIONS[self.current_map_name]
        for i, ld in enumerate(layer_defs):
            cb = QCheckBox(ld["name"])
            cb.setChecked(self.layer_visible[i] if i < len(self.layer_visible) else True)
            cb.setStyleSheet(
                "QCheckBox{color:#c8e8c8;font-size:12px;font-weight:bold;"
                "background:transparent;border:none;spacing:8px;}"
                "QCheckBox::indicator{width:16px;height:16px;"
                "border:2px solid rgba(100,200,100,120);border-radius:3px;"
                "background:rgba(0,0,0,150);}"
                "QCheckBox::indicator:checked{background:#1e8040;border-color:#40c060;}"
                "QCheckBox::indicator:hover{border-color:rgba(150,255,150,200);}"
            )
            cb.stateChanged.connect(lambda state, idx=i: self._on_layer_toggled(idx, state))
            self._layer_checks_layout.addWidget(cb)
            self._layer_checkboxes.append(cb)

        QTimer.singleShot(
            0,
            lambda: self._layer_scroll_inner.parent().verticalScrollBar().setValue(0)
            if hasattr(self._layer_scroll_inner.parent(), "verticalScrollBar")
            else None,
        )

    def _on_layer_toggled(self, idx, state):
        """Handle a layer checkbox toggle event and update layer visibility on the canvas.

        Args:
            idx (int): The index of the layer.
            state (int): The checkbox state (Qt.Checked or Qt.Unchecked).
        """
        if idx < len(self.layer_visible):
            self.layer_visible[idx] = state == Qt.Checked
            self.canvas.update()

    def _layers_all_on(self):
        """Set all map layers to visible and update the checkboxes and canvas."""
        self.layer_visible = [True] * len(self.map_layers)
        for cb in self._layer_checkboxes:
            cb.blockSignals(True)
            cb.setChecked(True)
            cb.blockSignals(False)
        self.canvas.update()

    def _layers_all_off(self):
        """Set all map layers to hidden and update the checkboxes and canvas."""
        self.layer_visible = [False] * len(self.map_layers)
        for cb in self._layer_checkboxes:
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.blockSignals(False)
        self.canvas.update()

    # Calibration panel
    def _make_calib_panel(self, parent):
        """Create the Calibration panel UI.  
    Includes title, hints, toggle button, calibration list, and action buttons for editing, deleting, clearing, and saving points."""

        p = Panel(parent)
        v = QVBoxLayout(p)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)

        lbl = QLabel(f"Calibration  —  {self.current_map_name}")
        lbl.setObjectName("calib_title")
        lbl.setStyleSheet(
            "color:#f0c040;font-size:14px;font-weight:bold;background:transparent;border:none;"
        )
        v.addWidget(lbl)
        self._calib_title_lbl = lbl

        hint = QLabel(
            "① Enable CAL mode below\n"
            "② Copy /jumploc in-game\n"
            "③ Double-click that spot on the map\n"
            "④ Repeat ≥3 times, then Save\n"
            "  (Calibration applies to all layers)"
        )
        hint.setStyleSheet(
            "color:rgba(200,200,180,180);font-size:11px;font-family:Consolas,monospace;"
            "background:rgba(0,0,0,80);border-radius:4px;padding:6px;border:none;"
        )
        hint.setWordWrap(True)
        v.addWidget(hint)

        self.btn_calib_toggle = QPushButton("▶  Enable Calibration Mode")
        self.btn_calib_toggle.setStyleSheet(
            "QPushButton{background:#c0782a;color:white;border:none;"
            "font-weight:bold;font-size:12px;border-radius:4px;padding:5px;}"
            "QPushButton:hover{background:#fff;color:#111;}"
        )
        self.btn_calib_toggle.setCheckable(True)
        self.btn_calib_toggle.clicked.connect(self._toggle_calib_mode)
        v.addWidget(self.btn_calib_toggle)

        self.calib_list_container = QWidget()
        cl_layout = QVBoxLayout(self.calib_list_container)
        cl_layout.setContentsMargins(0, 0, 0, 0)
        cl_layout.setSpacing(4)

        self.btn_calib_hide = QPushButton("Hide Cal Points on Map")
        self.btn_calib_hide.setStyleSheet(
            "QPushButton{background:#666;color:white;border:none;"
            "font-weight:bold;font-size:11px;border-radius:3px;padding:3px;}"
            "QPushButton:hover{background:#888;color:white;}"
        )
        self.btn_calib_hide.setCheckable(True)
        self.btn_calib_hide.clicked.connect(self._toggle_show_cal_points)
        cl_layout.addWidget(self.btn_calib_hide)

        self.calib_list = QListWidget()
        self.calib_list.setStyleSheet(
            "QListWidget{background:rgba(0,0,0,170);color:white;"
            "border:1px solid rgba(255,255,255,30);border-radius:4px;"
            "font-size:12px;font-family:Consolas,monospace;}"
            "QListWidget::item{padding:3px 5px;}"
            "QListWidget::item:selected{background:rgba(100,100,220,190);}"
            "QListWidget::item:hover{background:rgba(255,255,255,18);}"
        )
        self.calib_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        cl_layout.addWidget(self.calib_list)

        v.addWidget(self.calib_list_container)

        row = QHBoxLayout()
        row.setSpacing(6)
        for text, bg, fn in [
            ("Edit", "#1e6e6e", self._edit_selected_calib),
            ("Delete Selected", "#8B2020", self._delete_selected_calib),
            ("Clear All", "#5a1010", self._clear_all_calib),
            ("Save", "#1e6e3a", self._save_calib),
        ]:
            b = QPushButton(text)
            b.setStyleSheet(
                f"QPushButton{{background:{bg};color:white;border:none;"
                f"font-size:11px;font-weight:bold;border-radius:4px;padding:5px 8px;}}"
                f"QPushButton:hover{{background:#fff;color:#111;}}"
            )
            b.clicked.connect(fn)
            row.addWidget(b)
        v.addLayout(row)
        return p

    # Pin panel
    def _make_pin_panel(self, parent):
        """Create the Pin-Drop panel UI.  
    Contains input for pin names, drop mode toggle, list of placed pins, rename field, and action buttons."""

        p = Panel(parent)
        v = QVBoxLayout(p)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)

        lbl = QLabel("Drop Pins")
        lbl.setStyleSheet(
            "color:#ff6060;font-size:14px;font-weight:bold;background:transparent;border:none;"
        )
        v.addWidget(lbl)

        create_box = QWidget()
        create_box.setStyleSheet(
            "background:rgba(180,30,30,30);border:1px solid rgba(200,80,80,60);border-radius:5px;"
        )
        cv = QVBoxLayout(create_box)
        cv.setContentsMargins(8, 6, 8, 8)
        cv.setSpacing(5)

        create_lbl = QLabel("Create New Pin")
        create_lbl.setStyleSheet(
            "color:#ff9090;font-size:12px;font-weight:bold;background:transparent;border:none;"
        )
        cv.addWidget(create_lbl)

        self.pin_name_edit = QLineEdit()
        self.pin_name_edit.setPlaceholderText("Pin name…")
        self.pin_name_edit.setStyleSheet(
            "QLineEdit{background:rgba(0,0,0,190);color:white;"
            "border:1px solid rgba(255,255,255,50);border-radius:4px;"
            "font-size:12px;padding:4px 7px;}"
            "QLineEdit:focus{border:1px solid rgba(255,100,100,180);}"
        )
        self.pin_name_edit.textChanged.connect(self._on_pin_name_changed)
        cv.addWidget(self.pin_name_edit)

        hint2 = QLabel("Enter a name, then double-click the map to place it.")
        hint2.setStyleSheet(
            "color:rgba(180,180,160,180);font-size:10px;background:transparent;border:none;"
        )
        hint2.setWordWrap(True)
        cv.addWidget(hint2)

        self.btn_pin_mode = QPushButton("▶  Activate Pin-Drop Mode")
        self.btn_pin_mode.setStyleSheet(
            "QPushButton{background:#c0392b;color:white;border:none;"
            "font-weight:bold;font-size:12px;border-radius:4px;padding:5px;}"
            "QPushButton:hover{background:#fff;color:#111;}"
        )
        self.btn_pin_mode.setCheckable(True)
        self.btn_pin_mode.clicked.connect(self._toggle_pin_drop_mode)
        cv.addWidget(self.btn_pin_mode)
        v.addWidget(create_box)

        sep_lbl = QLabel("Placed Pins")
        sep_lbl.setStyleSheet(
            "color:rgba(200,180,180,200);font-size:12px;font-weight:bold;"
            "background:transparent;border:none;margin-top:4px;"
        )
        v.addWidget(sep_lbl)

        self.pin_list_container = QWidget()
        pl_layout = QVBoxLayout(self.pin_list_container)
        pl_layout.setContentsMargins(0, 0, 0, 0)
        pl_layout.setSpacing(4)

        self.btn_pin_hide = QPushButton("Hide Pins on Map")
        self.btn_pin_hide.setStyleSheet(
            "QPushButton{background:#666;color:white;border:none;"
            "font-weight:bold;font-size:11px;border-radius:3px;padding:3px;}"
            "QPushButton:hover{background:#888;color:white;}"
        )
        self.btn_pin_hide.setCheckable(True)
        self.btn_pin_hide.clicked.connect(self._toggle_show_pins)
        pl_layout.addWidget(self.btn_pin_hide)

        self.pin_list = QListWidget()
        self.pin_list.setStyleSheet(
            "QListWidget{background:rgba(0,0,0,170);color:white;"
            "border:1px solid rgba(255,255,255,30);border-radius:4px;"
            "font-size:12px;font-family:Consolas,monospace;}"
            "QListWidget::item{padding:3px 5px;}"
            "QListWidget::item:selected{background:rgba(200,50,50,190);}"
            "QListWidget::item:hover{background:rgba(255,255,255,18);}"
        )
        self.pin_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        pl_layout.addWidget(self.pin_list)
        v.addWidget(self.pin_list_container)

        rrow = QHBoxLayout()
        rrow.setSpacing(5)
        self.pin_rename_edit = QLineEdit()
        self.pin_rename_edit.setPlaceholderText("New name for selected pin…")
        self.pin_rename_edit.setStyleSheet(
            "QLineEdit{background:rgba(0,0,0,190);color:white;"
            "border:1px solid rgba(255,255,255,50);border-radius:4px;"
            "font-size:12px;padding:4px 7px;}"
            "QLineEdit:focus{border:1px solid rgba(255,100,100,180);}"
        )
        self.pin_rename_edit.returnPressed.connect(self._rename_selected_pin)
        btn_rename = QPushButton("Rename")
        btn_rename.setStyleSheet(
            "QPushButton{background:#2471a3;color:white;border:none;"
            "font-size:12px;font-weight:bold;border-radius:4px;padding:4px 9px;}"
            "QPushButton:hover{background:#fff;color:#111;}"
        )
        btn_rename.clicked.connect(self._rename_selected_pin)
        rrow.addWidget(self.pin_rename_edit)
        rrow.addWidget(btn_rename)
        v.addLayout(rrow)

        row = QHBoxLayout()
        row.setSpacing(6)
        for text, bg, fn in [
            ("Edit", "#1e6e6e", self._edit_selected_pin),
            ("Delete Selected", "#8B2020", self._delete_selected_pin),
            ("Clear All", "#5a1010", self._clear_all_pins),
            ("Save Pins", "#1e6e3a", self._save_pins_flash),
        ]:
            b = QPushButton(text)
            b.setStyleSheet(
                f"QPushButton{{background:{bg};color:white;border:none;"
                f"font-size:11px;font-weight:bold;border-radius:4px;padding:5px 8px;}}"
                f"QPushButton:hover{{background:#fff;color:#111;}}"
            )
            b.clicked.connect(fn)
            row.addWidget(b)
        v.addLayout(row)
        return p

    # Markers panel
    def _make_markers_panel(self, parent):
        """Create the World Markers panel UI.  
    Allows manual marker creation with X/Y coordinates, shows a list of markers, and includes buttons to delete, clear, or save."""

        p = Panel(parent)
        v = QVBoxLayout(p)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)

        lbl = QLabel("World markers")
        lbl.setStyleSheet(
            "color:#58d7be;font-size:14px;font-weight:bold;background:transparent;border:none;"
        )
        v.addWidget(lbl)

        hint = QLabel(
            "Map position only: /jumploc token 1 = X, token 3 = Y (same as player dot).\n"
            "Game Z is for default layer selection elsewhere—not stored on markers. Colors: [colors] marker_* in INI."
        )
        hint.setStyleSheet(
            "color:rgba(180,220,210,180);font-size:10px;font-family:Consolas,monospace;"
            "background:rgba(0,0,0,80);border-radius:4px;padding:6px;border:none;"
        )
        hint.setWordWrap(True)
        v.addWidget(hint)

        grid = QWidget()
        gv = QHBoxLayout(grid)
        gv.setContentsMargins(0, 0, 0, 0)
        gv.setSpacing(6)

        self.marker_x_edit = QLineEdit()
        self.marker_x_edit.setPlaceholderText("X (tok 1)")
        self.marker_map_y_edit = QLineEdit()
        self.marker_map_y_edit.setPlaceholderText("Y map (tok 3)")
        for e in (self.marker_x_edit, self.marker_map_y_edit):
            e.setFixedWidth(88)
            e.setStyleSheet(
                "QLineEdit{background:rgba(0,0,0,190);color:white;"
                "border:1px solid rgba(255,255,255,50);border-radius:4px;"
                "font-size:11px;padding:4px;}"
            )
        gv.addWidget(self.marker_x_edit)
        gv.addWidget(self.marker_map_y_edit)
        v.addWidget(grid)

        self.marker_name_edit = QLineEdit()
        self.marker_name_edit.setPlaceholderText("Name (e.g. corpse — PlayerName)")
        self.marker_name_edit.setStyleSheet(
            "QLineEdit{background:rgba(0,0,0,190);color:white;"
            "border:1px solid rgba(255,255,255,50);border-radius:4px;"
            "font-size:12px;padding:4px 7px;}"
        )
        v.addWidget(self.marker_name_edit)

        row = QHBoxLayout()
        add_b = QPushButton("Add marker")
        add_b.setStyleSheet(
            "QPushButton{background:#117a65;color:white;border:none;"
            "font-size:11px;font-weight:bold;border-radius:4px;padding:6px;}"
            "QPushButton:hover{background:#fff;color:#111;}"
        )
        add_b.clicked.connect(self._add_named_marker_from_fields)
        row.addWidget(add_b)
        v.addLayout(row)

        self.markers_list_container = QWidget()
        ml_layout = QVBoxLayout(self.markers_list_container)
        ml_layout.setContentsMargins(0, 0, 0, 0)
        ml_layout.setSpacing(4)

        self.btn_markers_hide = QPushButton("Hide Markers on Map")
        self.btn_markers_hide.setStyleSheet(
            "QPushButton{background:#666;color:white;border:none;"
            "font-weight:bold;font-size:11px;border-radius:3px;padding:3px;}"
            "QPushButton:hover{background:#888;color:white;}"
        )
        self.btn_markers_hide.setCheckable(True)
        self.btn_markers_hide.clicked.connect(self._toggle_show_markers)
        ml_layout.addWidget(self.btn_markers_hide)

        self.markers_list = QListWidget()
        self.markers_list.setStyleSheet(
            "QListWidget{background:rgba(0,0,0,170);color:white;"
            "border:1px solid rgba(255,255,255,30);border-radius:4px;"
            "font-size:12px;font-family:Consolas,monospace;}"
            "QListWidget::item{padding:3px 5px;}"
            "QListWidget::item:selected{background:rgba(20,120,100,190);}"
            "QListWidget::item:hover{background:rgba(255,255,255,18);}"
        )
        self.markers_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        ml_layout.addWidget(self.markers_list)

        v.addWidget(self.markers_list_container)

        brow = QHBoxLayout()
        for text, bg, fn in [
            ("Delete Selected", "#8B2020", self._delete_selected_named_marker),
            ("Clear All", "#5a1010", self._clear_all_named_markers),
            ("Save", "#1e6e3a", self._save_named_markers_flash),
        ]:
            b = QPushButton(text)
            b.setStyleSheet(
                f"QPushButton{{background:{bg};color:white;border:none;"
                f"font-size:11px;font-weight:bold;border-radius:4px;padding:5px 8px;}}"
                f"QPushButton:hover{{background:#fff;color:#111;}}"
            )
            b.clicked.connect(fn)
            brow.addWidget(b)
        v.addLayout(brow)
        return p

    # Panel toggles and layout helpers
    def _toggle_layer_panel(self):
        """Toggle visibility of the Layer panel.  
    Hides other panels when showing, and rebuilds its content if being shown."""
        vis = not self.layer_panel.isVisible()
        self.layer_panel.setVisible(vis)
        if vis:
            self._rebuild_layer_panel_content()
            self.calib_panel.hide()
            self.pin_panel.hide()
            self.markers_panel.hide()

    def _toggle_calib_panel(self):
        """Toggle visibility of the Calibration panel.  
    Updates the title, refreshes the list, hides other panels, and disables pin-drop mode."""
        vis = not self.calib_panel.isVisible()
        self.calib_panel.setVisible(vis)
        if vis:
            self._calib_title_lbl.setText(f"Calibration  —  {self.current_map_name}")
            self._refresh_calib_list()
            self.pin_panel.hide()
            self.layer_panel.hide()
            self.markers_panel.hide()
            self._set_pin_drop_mode(False)

    def _toggle_pin_panel(self):
        """Toggle visibility of the Pin panel.  
    Refreshes pin list, hides other panels, and disables calibration mode."""
        vis = not self.pin_panel.isVisible()
        self.pin_panel.setVisible(vis)
        if vis:
            self._refresh_pin_list()
            self.calib_panel.hide()
            self.layer_panel.hide()
            self.markers_panel.hide()
            self._set_calib_mode(False)

    def _toggle_markers_panel(self):
        """Toggle visibility of the Markers panel.  
    Refreshes marker list, hides other panels, and disables calibration and pin-drop modes."""
        vis = not self.markers_panel.isVisible()
        self.markers_panel.setVisible(vis)
        if vis:
            self._refresh_named_marker_list()
            self.calib_panel.hide()
            self.layer_panel.hide()
            self.pin_panel.hide()
            self._set_calib_mode(False)
            self._set_pin_drop_mode(False)

    def _refresh_named_marker_list(self):
        """Clear and repopulate the marker list widget from saved named markers."""
        self.markers_list.clear()
        for m in self.named_markers:
            if "wy" in m:
                map_y = float(m["wy"])
            elif "wz" in m:
                map_y = float(m["wz"])
            else:
                continue
            self.markers_list.addItem(f"◎ {m['name']}  X={m['wx']:.2f} Y={map_y:.2f}")

    def _add_named_marker_from_fields(self):
        """Add a new marker using current X, Y, and name inputs.  
    Clears inputs, refreshes the list, saves data, and flashes confirmation."""
        try:
            wx = float(self.marker_x_edit.text().strip())
            wmy = float(self.marker_map_y_edit.text().strip())
        except ValueError:
            self._flash("Markers: enter valid X (token 1) and Y map (token 3).")
            return
        name = self.marker_name_edit.text().strip() or "Marker"
        rec = {"name": name, "wx": wx, "wy": wmy}
        self.named_markers.append(rec)
        self.marker_x_edit.clear()
        self.marker_map_y_edit.clear()
        self.marker_name_edit.clear()
        self._refresh_named_marker_list()
        self._save_named_markers()
        self._flash(f"Marker '{name}' added.")
        self.canvas.update()

    def _delete_selected_named_marker(self):
        """Delete the currently selected marker from the list.  
    Updates the UI and saves changes."""
        row = self.markers_list.currentRow()
        if 0 <= row < len(self.named_markers):
            self.named_markers.pop(row)
            self._refresh_named_marker_list()
            self._save_named_markers()
            self._flash("Marker removed.")
            self.canvas.update()
        else:
            self._flash("Select a marker first.")

    def _clear_all_named_markers(self):
        """Remove all markers from memory and refresh the list.  
    Saves changes and updates the UI."""
        if not self.named_markers:
            return
        self.named_markers.clear()
        self._refresh_named_marker_list()
        self._save_named_markers()
        self._flash("All markers cleared.")
        self.canvas.update()

    def _save_named_markers_flash(self):
        """Save all markers to persistent storage and show a confirmation flash."""
        self._save_named_markers()
        self._flash(f"Saved {len(self.named_markers)} markers.")

    # Layout / geometry of panels
    def _relayout(self):
        """Update positions and sizes of canvas, top bar, and all panels.  
    Also repositions the flash label if it is visible."""
        w, h = self.width(), self.height()
        self.canvas.setGeometry(0, 0, w, h)
        self.top_bar.setGeometry(0, 0, w, TOP_BAR_HEIGHT)
        pw = PANEL_WIDTH
        ph = min(h - TOP_BAR_HEIGHT - 8, 600)
        py = TOP_BAR_HEIGHT + 4
        self.layer_panel.setGeometry(w - pw - 6, py, pw, ph)
        self.calib_panel.setGeometry(w - pw - 6, py, pw, ph)
        self.pin_panel.setGeometry(w - pw - 6, py, pw, ph)
        self.markers_panel.setGeometry(w - pw - 6, py, pw, ph)
        self.settings_panel.setGeometry(w - pw - 6, py, pw, ph)
        if not self.flash_lbl.isHidden():
            self.flash_lbl.adjustSize()
            self.flash_lbl.move((w - self.flash_lbl.width()) // 2, h // 2 - 60)

