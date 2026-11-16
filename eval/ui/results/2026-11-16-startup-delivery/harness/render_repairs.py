import os,sys,json,types
from pathlib import Path
repo=Path('C:/Users/tanzir/Desktop/voice_tray');sys.path.insert(0,str(repo))
os.environ.update(QT_QPA_PLATFORM='offscreen',QT_STYLE_OVERRIDE='Fusion')
qa=Path(__file__).resolve().parent
from tools.public_file_guard import install
install(qa/'repair-render-accepted.guard.json')
from saydraft.privacy.netguard import NetworkGuard
NetworkGuard.install()
from PySide6 import QtCore,QtGui,QtWidgets
app=QtWidgets.QApplication([])
from saydraft.ui.fonts import install_bundled_fonts
from saydraft.ui.theme import install_theme
from saydraft.ui.gallery_catalog import Fixtures,Scene,capture
install_bundled_fonts(app)
theme=install_theme(app,mode='light')
logs=types.ModuleType('saydraft.logging_config');logs.log_file_path=lambda:qa/'unused.log'
sys.modules['saydraft.logging_config']=logs
class FakeTray:
 class ActivationReason:
  Trigger=1;DoubleClick=2
 def __init__(self,*_):
  self.activated=types.SimpleNamespace(connect=lambda *_:None)
 def setContextMenu(self,*_):pass
 def setIcon(self,*_):pass
 def setToolTip(self,*_):pass
 def show(self):pass
from saydraft.ui.tray import SaydraftTray
out=qa/'repair-renders-accepted';out.mkdir(exist_ok=False)
for mode in ('light','dark'):
 theme.set_mode(mode)
 tray=SaydraftTray(qt_modules=types.SimpleNamespace(QtWidgets=types.SimpleNamespace(QApplication=QtWidgets.QApplication,QSystemTrayIcon=FakeTray),QtCore=QtCore,QtGui=QtGui))
 tray.set_listening(True)
 tray.menu.show();app.processEvents()
 assert tray.menu.grab().save(str(out/(mode+'-tray-menu.png')))
 tray.menu.close();tray.menu.deleteLater();app.processEvents()
 fixtures=Fixtures()
 scene=Scene('setup','models');wizard=fixtures.scene(scene)
 wizard.models_page.cleanup_setup.enabled.setChecked(True)
 loop=QtCore.QEventLoop();QtCore.QTimer.singleShot(200,loop.quit);loop.exec()
 root=wizard.models_page.scroll.widget();layout=root.layout();card=wizard.models_page.cleanup_setup
 shot=capture(wizard,scene);assert shot.save(str(out/(mode+'-setup-ai.png')))
 card=wizard.models_page.cleanup_setup
 def describe(w):
  return dict(type=type(w).__name__,text=w.text() if isinstance(w,(QtWidgets.QLabel,QtWidgets.QAbstractButton)) else '',hidden=w.isHidden(),visible=w.isVisible(),rect=w.geometry().getRect(),hint=[w.sizeHint().width(),w.sizeHint().height()],minimum=[w.minimumSizeHint().width(),w.minimumSizeHint().height()],min=[w.minimumWidth(),w.minimumHeight()],hfw=w.heightForWidth(w.width()),maximum=[w.maximumWidth(),w.maximumHeight()])
 (out/(mode+'-layout.json')).write_text(json.dumps([describe(w) for w in [card,*card.findChildren(QtWidgets.QWidget)]],indent=2),encoding='utf-8')
 (out/(mode+'-root.json')).write_text(json.dumps([describe(w) for w in [wizard.models_page.scroll,wizard.models_page.scroll.widget(),*wizard.models_page.scroll.widget().findChildren(QtWidgets.QWidget,options=QtCore.Qt.FindDirectChildrenOnly)]],indent=2),encoding='utf-8')
 fixtures.close()
atlas=QtGui.QImage(640,200,QtGui.QImage.Format_ARGB32);atlas.fill('#f4f1e8')
p=QtGui.QPainter(atlas);p.setPen(QtGui.QColor('#111111'))
for row,state in enumerate(('idle','recording','processing')):
 p.drawText(8,32+row*60,state)
 icon=QtGui.QIcon(str(repo/'assets/tray'/('mic_'+state+'.ico')))
 for col,size in enumerate((16,20,24,32,48)):
  icon.paint(p,QtCore.QRect(110+col*70,8+row*60,size,size))
 p.fillRect(470,row*60,160,60,QtGui.QColor('#111111'))
 for col,size in enumerate((16,24,32)):
  icon.paint(p,QtCore.QRect(480+col*45,8+row*60,size,size))
p.end();assert atlas.save(str(out/'tray-icons.png'))
theme.close()
(out/'report.json').write_text(json.dumps(dict(offscreen=True,network_guard=True,native_tray_created=False,owner_io_used=False,files=sorted(p.name for p in out.glob('*.png')))),encoding='utf-8')
