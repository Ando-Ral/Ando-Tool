
import sys,json,time
from pathlib import Path
from PySide6.QtCore import Qt,Signal,QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QComboBox,QLineEdit,QTextEdit,QTabWidget,QTableWidget,QTableWidgetItem,QHeaderView,QMessageBox,QCheckBox,QDialog,QDialogButtonBox,QFormLayout
from pynput import keyboard
import pyperclip

APP="Ando Tool Carnet"; AUTHOR="Ralambomanana Ando"
FIELDS=[("anarana","Anarana"),("fanampiny","Fanampiny"),("daty_nahaterahana","Daty nahaterahana"),("nee_vers","Né(e) vers"),("toerana_nahaterahana","Toerana nahaterahana"),("ray","Ray"),("reny","Reny"),("adiresy","Adiresy mazava / toerana"),("secteur","Secteur / Carreau / Parcelle / Quartier / Hameaux / Vohitra"),("asa","Asa atao"),("karapanondro","Laharan'ny karapanondro"),("daty_carte","Daty nanomezana ny karatra"),("toerana_carte","Toerana nanomezana ny karatra"),("laharan_andiany","Laharan'ny andiany"),("lettre_serie","Lettre de série"),("daty","Daty")]
ALIASES={k:[k] for k,_ in FIELDS}
ALIASES.update({"anarana":["anarana","nom"],"fanampiny":["fanampiny","prenom","prénom"],"daty_nahaterahana":["daty_nahaterahana","date_naissance","daty nahaterahana"],"nee_vers":["nee_vers","né(e)_vers","ne_vers"],"toerana_nahaterahana":["toerana_nahaterahana","lieu_naissance"],"ray":["ray","pere","père"],"reny":["reny","mere","mère"],"adiresy":["adiresy","adresse","adiresy_mazava"],"asa":["asa","asa_atao","profession"],"karapanondro":["karapanondro","laharan_karapanondro","cin","numero_cin"],"daty_carte":["daty_carte","daty_nanomezana_ny_karatra"],"toerana_carte":["toerana_carte","toerana_nanomezana_ny_karatra"],"laharan_andiany":["laharan_andiany","numero_serie"],"lettre_serie":["lettre_serie","lettre de serie"],"daty":["daty","date"]})
DEFAULT={"simple_shortcuts":{k:f"ctrl+alt+{k}" for k,_ in []},"rapid_shortcut":"ctrl+alt+1","previous_shortcut":"ctrl+alt+o","next_shortcut":"ctrl+alt+p","pause_shortcut":"ctrl+alt+h","global_hotkeys":True,"restore_clipboard":False,"paste_delay_ms":80,"start_minimized":False}
DEFAULT["simple_shortcuts"]={k:("ctrl+alt+"+str(i+1) if i<10 else {"karapanondro":"ctrl+alt+a","daty_carte":"ctrl+alt+z","toerana_carte":"ctrl+alt+e","laharan_andiany":"ctrl+alt+r","lettre_serie":"ctrl+alt+t","daty":"ctrl+alt+y"}[k]) for i,(k,_) in enumerate(FIELDS[:10])}
DEFAULT["simple_shortcuts"].update({"karapanondro":"ctrl+alt+a","daty_carte":"ctrl+alt+z","toerana_carte":"ctrl+alt+e","laharan_andiany":"ctrl+alt+r","lettre_serie":"ctrl+alt+t","daty":"ctrl+alt+y"})

def norm(s): return str(s).strip().lower().replace(" ","")
def pp(s):
    return "+".join("<ctrl>" if x=="ctrl" else "<alt>" if x=="alt" else "<shift>" if x=="shift" else x for x in norm(s).split("+"))
def val(info,k):
    for a in ALIASES.get(k,[k]):
        if info.get(a) not in (None,""):
            v=str(info[a]).strip()
            if k in ("daty_nahaterahana","daty_carte","daty"):
                d="".join(c for c in v if c.isdigit()); return d if len(d)==8 else v
            return v
    if k=="secteur":
        return " / ".join(dict.fromkeys(str(info[a]).strip() for a in ["secteur","carreau","parcelle","quartier","hameaux","vohitra"] if info.get(a) not in (None,"")))
    return ""

class Bridge(QObject): hit=Signal(str)

class HK:
    def __init__(self,b): self.b=b; self.l=None; self.running=False
    def stop(self):
        if self.l:
            try:self.l.stop()
            except:pass
        self.l=None; self.running=False
    def start(self,m):
        self.stop(); mp={}
        for name,c in m.items():
            c=norm(c)
            if c: mp.setdefault(c,[]).append(name)
        try:
            self.l=keyboard.GlobalHotKeys({pp(c):self.cb(names) for c,names in mp.items()})
            self.l.start(); self.running=True; return True,""
        except Exception as e:return False,str(e)
    def cb(self,names):
        return lambda:[self.b.hit.emit(n) for n in names]

class Shortcuts(QDialog):
    def __init__(self,c,parent=None):
        super().__init__(parent); self.setWindowTitle("Paramètres des raccourcis"); self.resize(650,650); self.e={}
        f=QFormLayout(self)
        for k,l in FIELDS:
            x=QLineEdit(c["simple_shortcuts"].get(k,"")); f.addRow("Simple — "+l,x); self.e["s:"+k]=x
        for k,l in [("rapid","Mode Rapide"),("previous","Précédent"),("next","Suivant"),("pause","Pause/Reprise")]:
            x=QLineEdit(c[k+"_shortcut"]); f.addRow(l,x); self.e[k]=x
        b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.accepted.connect(self.accept); b.rejected.connect(self.reject); f.addRow(b)
    def get(self,c):
        n=json.loads(json.dumps(c))
        for k,x in self.e.items():
            if k.startswith("s:"): n["simple_shortcuts"][k[2:]]=norm(x.text())
            else:n[k+"_shortcut"]=norm(x.text())
        return n

class Win(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle(APP); self.resize(1100,760)
        self.cp=Path(__file__).with_name("config.json"); self.c=self.loadc(); self.pages=[]; self.i=0; self.mode="simple"; self.ri=0; self.paused=False
        self.br=Bridge(); self.br.hit.connect(self.hot); self.hk=HK(self.br); self.ui(); self.restart()
    def loadc(self):
        try:
            c=json.loads(self.cp.read_text(encoding="utf8")); d=json.loads(json.dumps(DEFAULT)); d.update(c); d["simple_shortcuts"].update(c.get("simple_shortcuts",{})); return d
        except:return json.loads(json.dumps(DEFAULT))
    def save(self): self.cp.write_text(json.dumps(self.c,ensure_ascii=False,indent=2),encoding="utf8")
    def ui(self):
        w=QWidget(); self.setCentralWidget(w); q=QVBoxLayout(w)
        t=QLabel("ANDO TOOL CARNET"); t.setObjectName("title"); q.addWidget(t)
        r=QHBoxLayout(); self.path=QComboBox(); b=QPushButton("📂 Charger JSON"); b.clicked.connect(self.open); r.addWidget(self.path,1); r.addWidget(b); q.addLayout(r)
        r=QHBoxLayout(); a=QPushButton("Mode Simple"); z=QPushButton("Mode Rapide"); a.clicked.connect(lambda:self.setmode("simple")); z.clicked.connect(lambda:self.setmode("rapid")); self.st=QLabel(); r.addWidget(a); r.addWidget(z); r.addStretch(); r.addWidget(self.st); q.addLayout(r)
        r=QHBoxLayout(); p=QPushButton("◀ Précédent"); n=QPushButton("Suivant ▶"); p.clicked.connect(self.prev); n.clicked.connect(self.next); self.box=QComboBox(); self.box.currentIndexChanged.connect(self.select); r.addWidget(p); r.addWidget(self.box,1); r.addWidget(n); q.addLayout(r)
        self.search=QLineEdit(); self.search.setPlaceholderText("Rechercher un carnet / nom / fichier / CIN…"); self.search.textChanged.connect(self.search_page); q.addWidget(self.search)
        tabs=QTabWidget(); q.addWidget(tabs,1); self.table=QTableWidget(0,2); self.table.setHorizontalHeaderLabels(["Champ","Valeur"]); self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeToContents); self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch); tabs.addTab(self.table,"Informations")
        self.raw=QTextEdit(); self.raw.setReadOnly(True); tabs.addTab(self.raw,"JSON")
        s=QWidget(); sl=QVBoxLayout(s); self.gc=QCheckBox("Activer les raccourcis globaux"); self.gc.setChecked(self.c["global_hotkeys"]); self.gc.toggled.connect(self.toggle); sb=QPushButton("⚙ Paramètres des raccourcis"); sb.clicked.connect(self.shortcuts); sl.addWidget(self.gc); sl.addWidget(sb); sl.addWidget(QLabel("Ctrl+Alt+H = pause/reprise. Les raccourcis globaux restent actifs même si cette fenêtre est derrière une autre application.")); sl.addStretch(); tabs.addTab(s,"Paramètres")
        h=QTextEdit("<h2>Instructions</h2><p>Charge le JSON, choisis un mode puis ouvre ton logiciel de saisie.</p><p><b>Simple :</b> chaque raccourci colle son champ.</p><p><b>Rapide :</b> Ctrl+Alt+1 avance dans l'ordre des champs.</p><p><b>Navigation :</b> Ctrl+Alt+O/P.</p><p>Si le logiciel cible est lancé en administrateur, lance aussi Ando Tool Carnet au même niveau.</p>"); h.setReadOnly(True); tabs.addTab(h,"Instructions")
        tabs.addTab(QLabel(f"<h2>{APP}</h2><p>Outil de saisie assistée.</p><p><b>Auteur :</b> {AUTHOR}</p>"),"À propos")
        self.setStyleSheet("QWidget{font-size:14px}QMainWindow{background:#17191c}QLabel{color:#eee}#title{font-size:25px;font-weight:700}QPushButton,QComboBox,QLineEdit,QTextEdit,QTableWidget{background:#24272b;color:#eee;border:1px solid #444;border-radius:8px;padding:7px}")
    def open(self):
        from PySide6.QtWidgets import QFileDialog
        p,_=QFileDialog.getOpenFileName(self,"Choisir JSON","","JSON (*.json)")
        if not p:return
        try:
            d=json.loads(Path(p).read_text(encoding="utf8")); self.pages=d.get("pages",d) if isinstance(d,dict) else d
            self.path.clear(); self.path.addItem(p); self.box.clear()
            for i,x in enumerate(self.pages):
                x=x.get("informations",x); self.box.addItem(f'{x.get("numero_carnet",x.get("numero_feuillet",i+1))} — {x.get("fichier","")}',i)
            if self.pages:self.show(0)
        except Exception as e:QMessageBox.critical(self,"Erreur JSON",str(e))
    def setmode(self,m):self.mode=m;self.ri=0;self.restart();self.refresh()
    def toggle(self,x):self.c["global_hotkeys"]=x;self.save();self.restart()
    def restart(self):
        self.hk.stop()
        if not self.c["global_hotkeys"] or self.paused:self.refresh();return
        m={f"field:{k}":v for k,v in self.c["simple_shortcuts"].items()};m.update({"rapid":self.c["rapid_shortcut"],"previous":self.c["previous_shortcut"],"next":self.c["next_shortcut"],"pause":self.c["pause_shortcut"]})
        ok,e=self.hk.start(m); self.st.setText("🟢 Raccourcis ON" if ok else "🔴 Raccourcis OFF"); self.statusBar().showMessage(e if not ok else "Raccourcis globaux actifs")
    def hot(self,n):
        if n=="pause":self.paused=not self.paused; self.restart(); return
        if self.paused:return
        if n=="previous":self.prev();return
        if n=="next":self.next();return
        if self.mode=="rapid":
            if n=="rapid":self.rapid()
        elif n.startswith("field:"):self.fill(n[6:])
    def info(self): return self.pages[self.i].get("informations",self.pages[self.i]) if self.pages else {}
    def paste(self,s):
        old=None
        if self.c["restore_clipboard"]:
            try:old=pyperclip.paste()
            except:pass
        pyperclip.copy(s); time.sleep(max(0,self.c["paste_delay_ms"])/1000)
        k=keyboard.Controller(); k.press(keyboard.Key.ctrl); k.press("v"); k.release("v"); k.release(keyboard.Key.ctrl)
        if old is not None:
            time.sleep(.05); pyperclip.copy(old)
    def fill(self,k):
        try:self.paste(val(self.info(),k))
        except Exception as e:self.statusBar().showMessage("Erreur collage: "+str(e))
    def rapid(self):
        if self.ri>=len(FIELDS):
            self.next();self.ri=0;return
        self.fill(FIELDS[self.ri][0]);self.ri+=1
    def show(self,i):
        if not self.pages:return
        self.i=i;self.box.blockSignals(True);self.box.setCurrentIndex(i);self.box.blockSignals(False); inf=self.info(); rows=[(l,val(inf,k)) for k,l in FIELDS]; self.table.setRowCount(len(rows))
        for r,(a,b) in enumerate(rows):self.table.setItem(r,0,QTableWidgetItem(a));self.table.setItem(r,1,QTableWidgetItem(b))
        self.raw.setPlainText(json.dumps(inf,ensure_ascii=False,indent=2));self.ri=0;self.refresh()
    def select(self,i):
        if i>=0:self.show(i)
    def prev(self):
        if self.i>0:self.show(self.i-1)
    def next(self):
        if self.i+1<len(self.pages):self.show(self.i+1)
    def search_page(self,s):
        s=s.lower().strip()
        if not s:return
        for i in range(self.box.count()):
            if s in self.box.itemText(i).lower():self.show(i);break
    def refresh(self):self.st.setText(("🟢" if self.hk.running else "🔴")+(" RAPIDE" if self.mode=="rapid" else " SIMPLE"))
    def shortcuts(self):
        d=Shortcuts(self.c,self)
        if d.exec()==QDialog.Accepted:self.c=d.get(self.c);self.save();self.restart()
    def closeEvent(self,e):self.hide();e.ignore()
    def realquit(self):self.hk.stop();QApplication.quit()

app=QApplication(sys.argv); win=Win(); win.show(); sys.exit(app.exec())
