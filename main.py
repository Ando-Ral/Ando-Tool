import sys
import json
import os
import time
import threading
from pathlib import Path

import pyperclip
from pynput import keyboard
from PySide6.QtCore import Qt, Signal, QObject, QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QLineEdit, QComboBox, QDialog, QFormLayout, QDialogButtonBox,
    QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView, QStackedWidget,
    QSystemTrayIcon, QMenu, QCheckBox
)

APP_NAME = "Ando Tool Carnet"
AUTHOR = "Ralambomanana Ando"
BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"

DEFAULT_SHORTCUTS = {
    "simple": {
        "anarana": "ctrl+alt+1",
        "fanampiny": "ctrl+alt+2",
        "daty_nahaterahana": "ctrl+alt+3",
        "nee_vers": "ctrl+alt+4",
        "toerana_nahaterahana": "ctrl+alt+5",
        "ray": "ctrl+alt+6",
        "reny": "ctrl+alt+7",
        "adiresy": "ctrl+alt+8",
        "secteur": "ctrl+alt+9",
        "asa": "ctrl+alt+0",
        "cin": "ctrl+alt+a",
        "daty_karatra": "ctrl+alt+z",
        "toerana_karatra": "ctrl+alt+e",
        "numero_serie": "ctrl+alt+r",
        "lettre_serie": "ctrl+alt+t",
        "daty": "ctrl+alt+y",
    },
    "rapid": "ctrl+alt+1",
    "previous": "ctrl+alt+o",
    "next": "ctrl+alt+p",
}

FIELDS = [
    ("anarana", "Anarana"),
    ("fanampiny", "Fanampiny"),
    ("daty_nahaterahana", "Daty nahaterahana"),
    ("nee_vers", "Né(e) vers"),
    ("toerana_nahaterahana", "Toerana nahaterahana"),
    ("ray", "Ray"),
    ("reny", "Reny"),
    ("adiresy", "Adiresy mazava na toerana"),
    ("secteur", "Secteur / Carreau / Parcelle / Quartier / Hameaux / Vohitra"),
    ("asa", "Asa atao"),
    ("cin", "Laharan'ny karapanondro"),
    ("daty_karatra", "Daty nanomezana ny karatra"),
    ("toerana_karatra", "Toerana nanomezana ny karatra"),
    ("numero_serie", "Laharan'ny andiany"),
    ("lettre_serie", "Lettre de série"),
    ("daty", "Daty"),
]

def load_config():
    data = {}
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    shortcuts = DEFAULT_SHORTCUTS.copy()
    shortcuts["simple"] = DEFAULT_SHORTCUTS["simple"].copy()
    shortcuts.update(data.get("shortcuts", {}))
    shortcuts["simple"] = {**DEFAULT_SHORTCUTS["simple"], **data.get("shortcuts", {}).get("simple", {})}
    return {
        "shortcuts": shortcuts,
        "global_hotkeys": data.get("global_hotkeys", True),
        "restore_clipboard": data.get("restore_clipboard", False),
        "start_minimized": data.get("start_minimized", False),
    }

def save_config(config):
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

def normalize_key(k):
    return k.lower().replace(" ", "")

def hotkey_to_pynput(combo):
    parts = [p.strip().lower() for p in combo.split("+") if p.strip()]
    mapped = []
    for p in parts:
        if p == "ctrl":
            mapped.append("<ctrl>")
        elif p == "alt":
            mapped.append("<alt>")
        elif p == "shift":
            mapped.append("<shift>")
        elif p == "win":
            mapped.append("<cmd>")
        elif len(p) == 1:
            mapped.append(p)
        else:
            mapped.append(f"<{p}>")
    return "+".join(mapped)

def get_info(page):
    info = page.get("informations")
    if isinstance(info, dict):
        merged = dict(page)
        merged.update(info)
        return merged
    return page

def value_for(page, key):
    info = get_info(page)
    aliases = {
        "toerana_karatra": ["toerana_nanomezana_ny_karatra", "toerana_karatra"],
        "numero_serie": ["laharan_andiany", "numero_serie", "laharan'ny andiany"],
        "lettre_serie": ["lettre_serie", "lettre_de_serie"],
        "cin": ["laharan_karapanondro", "laharan'ny karapanondro", "cin"],
        "daty_karatra": ["daty_nanomezana_ny_karatra", "daty_karatra"],
        "daty_nahaterahana": ["daty_naterahana", "daty_nahaterahana"],
        "nee_vers": ["nee_vers", "ne_vers", "née_vers"],
        "toerana_nahaterahana": ["toerana_nahaterahana"],
        "secteur": ["secteur", "carreau", "parcelle", "quartier", "hameaux", "vohitra"],
        "asa": ["asa", "asa_atao", "asa atao"],
        "anarana": ["anarana"],
        "fanampiny": ["fanampiny"],
        "ray": ["ray"],
        "reny": ["reny"],
        "daty": ["daty"],
    }
    candidates = aliases.get(key, [key])
    for c in candidates:
        if c in info and info[c] is not None:
            v = info[c]
            if isinstance(v, dict):
                # For unusual structured values, keep useful textual content.
                return " ".join(str(x) for x in v.values() if x not in (None, ""))
            return str(v)
    return ""

def load_pages(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("pages", "carnets", "feuillets", "data", "results"):
            if isinstance(data.get(key), list):
                return data[key]
        # Accept a single page object.
        if any(k in data for k in ("informations", "anarana", "numero_carnet", "fichier")):
            return [data]
    raise ValueError("Format JSON non reconnu. Le fichier doit contenir une liste de pages/feuillets.")

class HotkeySignals(QObject):
    field = Signal(str)
    navigation = Signal(str)
    rapid = Signal()

class GlobalHotkeyManager:
    def __init__(self, config, signals):
        self.config = config
        self.signals = signals
        self.listener = None
        self.lock = threading.Lock()

    def stop(self):
        with self.lock:
            if self.listener:
                try:
                    self.listener.stop()
                except Exception:
                    pass
                self.listener = None

    def start(self):
        self.stop()
        if not self.config.get("global_hotkeys", True):
            return
        mapping = {}
        simple = self.config["shortcuts"]["simple"]
        for key, combo in simple.items():
            if combo:
                mapping[hotkey_to_pynput(combo)] = (lambda k=key: self.signals.field.emit(k))
        mapping[hotkey_to_pynput(self.config["shortcuts"]["previous"])] = lambda: self.signals.navigation.emit("previous")
        mapping[hotkey_to_pynput(self.config["shortcuts"]["next"])] = lambda: self.signals.navigation.emit("next")
        rapid = self.config["shortcuts"].get("rapid", "ctrl+alt+1")
        if rapid:
            mapping[hotkey_to_pynput(rapid)] = lambda: self.signals.rapid.emit()
        try:
            self.listener = keyboard.GlobalHotKeys(mapping)
            self.listener.start()
        except Exception as e:
            self.listener = None
            print("Erreur raccourcis globaux:", e)

class ShortcutDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Paramètres des raccourcis")
        self.resize(650, 650)
        self.config = config
        self.edits = {}
        layout = QVBoxLayout(self)
        note = QLabel("Utilise par exemple : Ctrl+Alt+1, Ctrl+Shift+A, F8.")
        note.setWordWrap(True)
        layout.addWidget(note)

        table = QTableWidget(len(FIELDS) + 3, 2)
        table.setHorizontalHeaderLabels(["Fonction", "Raccourci"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        row = 0
        for key, label in FIELDS:
            table.setItem(row, 0, QTableWidgetItem(label))
            e = QLineEdit(config["shortcuts"]["simple"].get(key, ""))
            table.setCellWidget(row, 1, e)
            self.edits[("simple", key)] = e
            row += 1
        for key, label in [("rapid", "Mode Rapide"), ("previous", "Carnet précédent"), ("next", "Carnet suivant")]:
            table.setItem(row, 0, QTableWidgetItem(label))
            e = QLineEdit(config["shortcuts"].get(key, ""))
            table.setCellWidget(row, 1, e)
            self.edits[(key, None)] = e
            row += 1
        layout.addWidget(table)

        self.restore = QCheckBox("Restaurer le presse-papiers après le collage")
        self.restore.setChecked(config.get("restore_clipboard", False))
        layout.addWidget(self.restore)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        for (group, key), edit in self.edits.items():
            val = normalize_key(edit.text())
            if group == "simple":
                self.config["shortcuts"]["simple"][key] = val
            else:
                self.config["shortcuts"][group] = val
        self.config["restore_clipboard"] = self.restore.isChecked()
        super().accept()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1180, 760)
        self.config = load_config()
        self.pages = []
        self.current_index = -1
        self.json_path = None
        self.mode = "simple"
        self.rapid_index = 0
        self.hotkey_signals = HotkeySignals()
        self.hotkey_signals.field.connect(self.on_global_field)
        self.hotkey_signals.navigation.connect(self.navigate)
        self.hotkey_signals.rapid.connect(self.on_rapid)
        self.hotkeys = GlobalHotkeyManager(self.config, self.hotkey_signals)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.build_home()
        self.build_mode()
        self.build_instructions()
        self.build_about()

        self.tray = None
        self.create_tray()
        self.statusBar().showMessage("Prêt")
        self.apply_style()
        if self.config.get("global_hotkeys", True):
            self.hotkeys.start()

    def apply_style(self):
        self.setStyleSheet("""
        QMainWindow, QWidget { background:#17181c; color:#eeeeee; }
        QGroupBox { border:1px solid #3a3d45; border-radius:12px; margin-top:12px; padding:12px; }
        QGroupBox::title { subcontrol-origin:margin; left:14px; padding:0 6px; }
        QPushButton { background:#292c33; border:1px solid #454954; border-radius:10px; padding:10px 16px; }
        QPushButton:hover { background:#353944; }
        QLineEdit, QComboBox, QListWidget, QTableWidget {
            background:#202228; border:1px solid #3b3e47; border-radius:9px; padding:7px;
        }
        QLabel#title { font-size:26px; font-weight:700; }
        QLabel#value { font-size:18px; }
        """)

    def create_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(self)
        self.tray.setToolTip(APP_NAME)
        menu = QMenu()
        show_action = QAction("Afficher", self)
        show_action.triggered.connect(self.showNormal)
        menu.addAction(show_action)
        menu.addSeparator()
        quit_action = QAction("Quitter", self)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.showNormal() if reason == QSystemTrayIcon.Trigger else None)
        self.tray.show()

    def closeEvent(self, event):
        if self.tray and self.tray.isVisible():
            self.hide()
            self.tray.showMessage(APP_NAME, "L'application reste active en arrière-plan.", QSystemTrayIcon.Information, 2000)
            event.ignore()
        else:
            self.quit_app()
            event.accept()

    def quit_app(self):
        self.hotkeys.stop()
        if self.tray:
            self.tray.hide()
        QApplication.quit()

    def build_home(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        title = QLabel(APP_NAME)
        title.setObjectName("title")
        lay.addWidget(title)
        sub = QLabel("Gestion et remplissage rapide des carnets à partir d'un JSON.")
        lay.addWidget(sub)

        box = QGroupBox("1 — Choisir le JSON")
        bl = QVBoxLayout(box)
        row = QHBoxLayout()
        self.json_edit = QLineEdit()
        self.json_edit.setReadOnly(True)
        browse = QPushButton("Parcourir…")
        browse.clicked.connect(self.select_json)
        row.addWidget(self.json_edit)
        row.addWidget(browse)
        bl.addLayout(row)
        self.json_info = QLabel("Aucun fichier chargé.")
        bl.addWidget(self.json_info)
        lay.addWidget(box)

        modebox = QGroupBox("2 — Choisir le mode")
        ml = QHBoxLayout(modebox)
        simple = QPushButton("Mode Simple")
        rapid = QPushButton("Mode Rapide")
        simple.clicked.connect(lambda: self.start_mode("simple"))
        rapid.clicked.connect(lambda: self.start_mode("rapid"))
        ml.addWidget(simple)
        ml.addWidget(rapid)
        lay.addWidget(modebox)

        nav = QHBoxLayout()
        instructions = QPushButton("Instructions")
        instructions.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        settings = QPushButton("Paramètres des raccourcis")
        settings.clicked.connect(self.open_settings)
        about = QPushButton("À propos")
        about.clicked.connect(lambda: self.stack.setCurrentIndex(3))
        nav.addWidget(instructions)
        nav.addWidget(settings)
        nav.addWidget(about)
        lay.addLayout(nav)
        lay.addStretch()
        self.stack.addWidget(w)

    def build_mode(self):
        w = QWidget()
        root = QVBoxLayout(w)
        top = QHBoxLayout()
        back = QPushButton("← Accueil")
        back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        top.addWidget(back)
        self.mode_label = QLabel("Mode Simple")
        self.mode_label.setObjectName("title")
        top.addWidget(self.mode_label)
        top.addStretch()
        self.hotkey_toggle = QCheckBox("Raccourcis globaux")
        self.hotkey_toggle.setChecked(self.config.get("global_hotkeys", True))
        self.hotkey_toggle.stateChanged.connect(self.toggle_hotkeys)
        top.addWidget(self.hotkey_toggle)
        root.addLayout(top)

        nav = QHBoxLayout()
        self.prev_btn = QPushButton("← Précédent")
        self.next_btn = QPushButton("Suivant →")
        self.prev_btn.clicked.connect(lambda: self.navigate("previous"))
        self.next_btn.clicked.connect(lambda: self.navigate("next"))
        self.page_selector = QComboBox()
        self.page_selector.currentIndexChanged.connect(self.select_page)
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.page_selector, 1)
        nav.addWidget(self.next_btn)
        root.addLayout(nav)

        content = QHBoxLayout()
        left = QVBoxLayout()
        self.page_title = QLabel("Aucun carnet")
        self.page_title.setObjectName("title")
        left.addWidget(self.page_title)
        self.file_label = QLabel("")
        left.addWidget(self.file_label)

        self.image_path = QLineEdit()
        self.image_path.setReadOnly(True)
        left.addWidget(QLabel("Image / fichier :"))
        left.addWidget(self.image_path)

        self.values = QListWidget()
        left.addWidget(self.values, 1)
        content.addLayout(left, 1)

        rightbox = QGroupBox("Mode Rapide")
        rr = QVBoxLayout(rightbox)
        self.rapid_status = QLabel("Mode rapide inactif")
        self.rapid_status.setObjectName("value")
        self.rapid_hint = QLabel("Le raccourci du mode rapide colle le champ suivant à chaque pression.")
        self.rapid_hint.setWordWrap(True)
        rr.addWidget(self.rapid_status)
        rr.addWidget(self.rapid_hint)
        rr.addStretch()
        content.addWidget(rightbox, 1)
        root.addLayout(content, 1)

        self.stack.addWidget(w)

    def build_instructions(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        title = QLabel("Instructions")
        title.setObjectName("title")
        lay.addWidget(title)
        self.help_text = QLabel()
        self.help_text.setWordWrap(True)
        lay.addWidget(self.help_text)
        back = QPushButton("← Retour")
        back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        lay.addWidget(back)
        self.stack.addWidget(w)
        self.update_help()

    def update_help(self):
        s = self.config["shortcuts"]["simple"]
        lines = [
            "<b>Mode Simple</b>",
            *[f"{label} : <b>{s.get(key,'')}</b>" for key, label in FIELDS],
            "",
            f"<b>Mode Rapide</b> : {self.config['shortcuts'].get('rapid','')}",
            f"<b>Précédent</b> : {self.config['shortcuts'].get('previous','')}",
            f"<b>Suivant</b> : {self.config['shortcuts'].get('next','')}",
            "",
            "Les raccourcis sont globaux : ils peuvent fonctionner même lorsque la fenêtre d'Ando Tool Carnet est derrière une autre application.",
            "Le collage utilise le presse-papiers Windows puis Ctrl+V.",
            "Fermer la fenêtre la réduit dans la zone de notification si celle-ci est disponible."
        ]
        self.help_text.setText("<br>".join(lines))

    def build_about(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        title = QLabel("À propos")
        title.setObjectName("title")
        lay.addWidget(title)
        text = QLabel(f"<b>{APP_NAME}</b><br><br>Auteur : <b>{AUTHOR}</b><br><br>Outil de consultation et de remplissage rapide des données de carnets.")
        text.setWordWrap(True)
        lay.addWidget(text)
        lay.addStretch()
        back = QPushButton("← Retour")
        back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        lay.addWidget(back)
        self.stack.addWidget(w)

    def select_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choisir un fichier JSON", "", "JSON (*.json)")
        if not path:
            return
        try:
            pages = load_pages(path)
        except Exception as e:
            QMessageBox.critical(self, "JSON invalide", str(e))
            return
        self.json_path = path
        self.pages = pages
        self.current_index = -1
        self.json_edit.setText(path)
        self.json_info.setText(f"{len(pages)} carnet(s)/feuillet(s) chargé(s).")
        self.page_selector.blockSignals(True)
        self.page_selector.clear()
        for i, p in enumerate(pages):
            info = get_info(p)
            num = info.get("numero_carnet", info.get("numero_feuillet", info.get("numero", str(i+1))))
            self.page_selector.addItem(f"{num}", i)
        self.page_selector.blockSignals(False)
        if pages:
            self.set_page(0)

    def start_mode(self, mode):
        if not self.pages:
            QMessageBox.warning(self, "Aucun JSON", "Choisis d'abord un fichier JSON.")
            return
        self.mode = mode
        self.mode_label.setText("Mode Simple" if mode == "simple" else "Mode Rapide")
        self.rapid_index = 0
        self.stack.setCurrentIndex(1)
        if self.current_index < 0:
            self.set_page(0)
        self.update_rapid_status()

    def set_page(self, index):
        if not self.pages:
            return
        index = max(0, min(index, len(self.pages)-1))
        self.current_index = index
        self.page_selector.blockSignals(True)
        self.page_selector.setCurrentIndex(index)
        self.page_selector.blockSignals(False)
        page = self.pages[index]
        info = get_info(page)
        carnet = info.get("numero_carnet", info.get("numero_feuillet", info.get("numero", str(index+1))))
        self.page_title.setText(f"Carnet / Feuillet : {carnet}")
        self.file_label.setText(f"Fichier : {info.get('fichier', info.get('filename', ''))}")
        path = info.get("image", info.get("image_path", info.get("path", info.get("fichier", ""))))
        self.image_path.setText(str(path))
        self.values.clear()
        for key, label in FIELDS:
            val = value_for(page, key)
            shown = val if val else "—"
            item = QListWidgetItem(f"{label} : {shown}")
            item.setData(Qt.UserRole, key)
            self.values.addItem(item)
        self.rapid_index = 0
        self.update_rapid_status()

    def select_page(self, idx):
        if idx >= 0 and idx < len(self.pages):
            self.set_page(idx)

    def navigate(self, direction):
        if not self.pages:
            return
        if direction == "previous":
            self.set_page(max(0, self.current_index - 1))
        else:
            self.set_page(min(len(self.pages)-1, self.current_index + 1))

    def copy_paste(self, text):
        old = None
        if self.config.get("restore_clipboard", False):
            try:
                old = pyperclip.paste()
            except Exception:
                old = None
        try:
            pyperclip.copy(text)
            time.sleep(0.06)
            controller = keyboard.Controller()
            with controller.pressed(keyboard.Key.ctrl):
                controller.press("v")
                controller.release("v")
            if old is not None:
                time.sleep(0.15)
                pyperclip.copy(old)
        except Exception as e:
            self.statusBar().showMessage(f"Erreur collage : {e}", 4000)

    def paste_field(self, key):
        if self.current_index < 0:
            return
        text = value_for(self.pages[self.current_index], key)
        threading.Thread(target=self.copy_paste, args=(text,), daemon=True).start()
        label = dict(FIELDS).get(key, key)
        self.statusBar().showMessage(f"Collé : {label}", 2500)

    def on_global_field(self, key):
        if self.mode != "simple":
            return
        self.paste_field(key)

    def on_rapid(self):
        if self.mode != "rapid" or self.current_index < 0:
            return
        key, label = FIELDS[self.rapid_index]
        self.paste_field(key)
        self.rapid_index += 1
        if self.rapid_index >= len(FIELDS):
            self.rapid_index = 0
            if self.current_index < len(self.pages) - 1:
                self.set_page(self.current_index + 1)
        self.update_rapid_status()

    def update_rapid_status(self):
        if self.mode != "rapid":
            self.rapid_status.setText("Mode rapide : sélectionne le mode Rapide pour commencer.")
            return
        key, label = FIELDS[self.rapid_index]
        self.rapid_status.setText(f"Champ suivant : {self.rapid_index+1}/{len(FIELDS)} — {label}\nRaccourci : {self.config['shortcuts'].get('rapid','')}")

    def toggle_hotkeys(self, state):
        self.config["global_hotkeys"] = bool(state)
        save_config(self.config)
        if state:
            self.hotkeys.start()
        else:
            self.hotkeys.stop()
        self.statusBar().showMessage("Raccourcis globaux " + ("activés" if state else "désactivés"), 2500)

    def open_settings(self):
        dlg = ShortcutDialog(self.config, self)
        if dlg.exec():
            save_config(self.config)
            self.hotkeys.start()
            self.update_help()
            self.update_rapid_status()
            self.statusBar().showMessage("Paramètres enregistrés.", 2500)

def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow()
    if window.config.get("start_minimized", False):
        window.hide()
    else:
        window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
