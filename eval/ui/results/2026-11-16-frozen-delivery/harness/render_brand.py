import os,sys
from pathlib import Path
qa=Path(__file__).resolve().parent;repo=Path('C:/Users/tanzir/Desktop/voice_tray');sys.path.insert(0,str(repo))
os.environ['QT_QPA_PLATFORM']='offscreen'
from tools.public_file_guard import install
install(qa/'brand-render-final.guard.json')
from PySide6 import QtCore,QtGui,QtWidgets
app=QtWidgets.QApplication([])
from saydraft.ui.fonts import install_bundled_fonts
install_bundled_fonts(app)
image=QtGui.QImage(720,240,QtGui.QImage.Format_ARGB32);image.fill('#F5F2E9')
painter=QtGui.QPainter(image)
painter.setFont(QtGui.QFont('Geist',10))
for row,state in enumerate(('idle','recording','processing')):
 painter.setPen(QtGui.QColor('#141414'));painter.drawText(10,40+80*row,state)
 icon=QtGui.QIcon(str(repo/'assets/tray'/('mic_'+state+'.ico')))
 painter.fillRect(420,80*row,300,80,QtGui.QColor('#121211'))
 for offset in (100,440):
  for col,size in enumerate((16,24,32,64)):
   icon.paint(painter,QtCore.QRect(offset+col*65,8+80*row,size,size))
painter.end();assert image.save(str(qa/'brand-icons-final.png'))
