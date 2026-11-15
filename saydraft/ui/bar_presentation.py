"""Graphite Bar drawing. All live behavior remains in bar_widget.py."""
import math
from PySide6 import QtCore, QtGui
from .theme.style import bar_color, role_font
from .icons import svg_icon


def pill(painter, widget, rect, radius):
    # Soft shadows stay in the owned window's transparent margin.
    for spread in range(12, 0, -1):
        alpha = .009 * (1 - spread / 18)
        shadow = QtGui.QColor(0, 0, 0)
        shadow.setAlphaF(alpha)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(shadow)
        painter.drawRoundedRect(QtCore.QRectF(rect).adjusted(-spread, -spread+5, spread, spread+5), radius+spread, radius+spread)
    painter.setPen(QtGui.QPen(bar_color(widget, "hairline"), 1))
    painter.setBrush(bar_color(widget, "bg"))
    painter.drawRoundedRect(QtCore.QRectF(rect).adjusted(.5,.5,-.5,-.5), radius, radius)


def icon(painter, widget, name, rect, tone="fg"):
    # SVG rendering uses the same bundled icon assets; palette is scoped to Bar.
    palette = QtGui.QPalette(widget.palette())
    palette.setColor(QtGui.QPalette.WindowText, bar_color(widget, tone))
    image = svg_icon(name, palette, size=int(rect.width()), tone="palette")
    image.paint(painter, rect.toRect())


def keycaps(painter, widget, keys, start, y, height=24):
    painter.setFont(widget.caption_font)
    x = start
    for key in keys.split("+"):
        width = painter.fontMetrics().horizontalAdvance(key) + 14
        rect = QtCore.QRectF(x, y, width, height)
        painter.setPen(QtGui.QPen(bar_color(widget, "hairline"), 1))
        painter.setBrush(bar_color(widget, "raised"))
        painter.drawRoundedRect(rect, 5, 5)
        painter.setPen(bar_color(widget, "fg"))
        painter.drawText(rect, QtCore.Qt.AlignCenter, key)
        x += width + 5
    return x


def paint_target(target):
    bar = target.bar
    p = QtGui.QPainter(target)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.fillRect(target.rect(), QtGui.QColor(0, 0, 0, 1))
    if target.kind == "expand":
        if bar.state.value == "idle":
            p.setPen(QtGui.QPen(bar_color(bar, "hairline"), 1))
            p.setBrush(bar_color(bar, "bg"))
            p.drawRoundedRect(QtCore.QRectF(6, 8, 44, 8), 4, 4)
        else:
            rect = QtCore.QRectF(target.rect())
            p.setPen(QtGui.QPen(bar_color(bar, "hairline"), 1))
            p.setBrush(bar_color(bar, "bg"))
            p.drawRoundedRect(rect.adjusted(.5,.5,-.5,-.5),18,18)
            p.setFont(bar.caption_font)
            p.setPen(bar_color(bar, "fgMuted"))
            p.drawText(QtCore.QRectF(12,0,30,36),QtCore.Qt.AlignVCenter,"Hold")
            end = keycaps(p,bar,bar.hotkey_hint,44,6)
            p.setPen(bar_color(bar,"fgMuted"))
            p.drawText(QtCore.QRectF(end+4,0,74,36),QtCore.Qt.AlignVCenter,"to dictate")
    elif target.kind == "stop":
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(bar_color(bar,"raised"))
        p.drawEllipse(QtCore.QRectF(0,0,28,28))
        p.setBrush(bar_color(bar,"fg"))
        p.drawRoundedRect(QtCore.QRectF(9,9,10,10),2,2)
    elif target.kind == "fix":
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(bar_color(bar,"fg"))
        p.drawRoundedRect(QtCore.QRectF(target.rect()),14,14)
        p.setFont(bar.caption_font)
        p.setPen(bar_color(bar,"bg"))
        p.drawText(target.rect(),QtCore.Qt.AlignCenter,"Fix" if bar.fix_page == "microphone" else "Open")
    elif target.kind == "dismiss":
        icon(p,bar,"x",QtCore.QRectF(6,6,16,16),"fgMuted")


def paint_bar(bar):
    if bar.state.value in ("hidden","idle","hover"):
        return
    p = QtGui.QPainter(bar)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    rect = QtCore.QRectF(bar.capsule_rect)
    state = bar.state.value
    alert = state in ("error","warning")
    pill(p,bar,rect,16 if alert else 20)
    if bar.preview_label.isVisible():
        pill(p,bar,QtCore.QRectF(bar.preview_label.geometry()),12)
    circle = QtCore.QRectF(rect.x()+ (10 if alert else 6),rect.y()+(12 if alert else 6),32 if alert else 28,32 if alert else 28)
    p.setPen(QtCore.Qt.NoPen)
    tone = "dangerTint" if state == "error" else "warnTint" if state == "warning" else "signal" if state == "recording" else "fg" if state == "command" else "raised"
    p.setBrush(bar_color(bar,tone))
    p.drawEllipse(circle)
    glyph = "alert" if state == "error" else "info" if state == "warning" else "command" if state == "command" else "lock" if bar.hands_free else "sparkle" if state == "processing" and bar.clock()-bar.processing_at>1.5 else "check" if state == "delivered" else "mic"
    icon(p,bar,glyph,circle.adjusted(6,6,-6,-6),"danger" if state == "error" else "warn" if state == "warning" else "bg" if state == "command" else "fg" if state == "recording" else "fgMuted")
    p.setFont(bar.message_font)
    p.setPen(bar_color(bar,"fg"))
    if alert:
        bounds = QtCore.QRectF(rect.x()+54,rect.y()+7,rect.width()-(160 if state == "error" else 96),22)
        p.drawText(bounds,QtCore.Qt.AlignVCenter,p.fontMetrics().elidedText(bar.status_label.text(),QtCore.Qt.ElideRight,int(bounds.width())))
        p.setFont(bar.caption_font)
        p.setPen(bar_color(bar,"fgMuted"))
        bounds.translate(0,21)
        p.drawText(bounds,QtCore.Qt.AlignVCenter,p.fontMetrics().elidedText(bar.elapsed_label.text(),QtCore.Qt.ElideRight,int(bounds.width())))
    elif state == "delivered":
        p.drawText(QtCore.QRectF(rect.x()+44,rect.y(),rect.width()-58,40),QtCore.Qt.AlignVCenter,"Inserted")
    elif state in ("preparing","processing"):
        label = "Getting ready" if state == "preparing" else "Tidying up" if bar.clock()-bar.processing_at>1.5 else "Writing it down"
        p.drawText(QtCore.QRectF(rect.x()+44,rect.y(),rect.width()-84,40),QtCore.Qt.AlignVCenter,label)
        dots = 18 if state == "preparing" else 6
        tidying = state == "processing" and bar.clock()-bar.processing_at>1.5
        for index in range(dots):
            alpha = .35+.65*(.5+.5*math.sin(bar.clock()*3-index*.6))
            shade = bar_color(bar,"fgMuted")
            shade.setAlphaF(alpha)
            p.setBrush(shade)
            p.setPen(QtCore.Qt.NoPen)
            p.drawEllipse(QtCore.QPointF(rect.right()-(65 if dots == 18 else 84 if tidying else 37)+index*(3 if dots == 18 else 4),rect.center().y()),1,1)
        if tidying:
            p.setFont(role_font("label",widget=bar))
            p.setPen(bar_color(bar,"fgMuted"))
            p.drawText(QtCore.QRectF(rect.right()-52,rect.y(),40,40),QtCore.Qt.AlignVCenter,"LOCAL")
    else:
        if state == "command":
            p.drawText(QtCore.QRectF(rect.x()+44,rect.y(),80,40),QtCore.Qt.AlignVCenter,"Command")
        font = role_font("mono",widget=bar)
        font.setPixelSize(11)
        p.setFont(font)
        p.setPen(bar_color(bar,"warn" if bar.property("longRecording") else "fgMuted"))
        long = bool(bar.property("longRecording"))
        timer_width = 154 if long else 44
        text = bar.elapsed_label.text().zfill(5)
        if long:
            remaining = bar.remaining_seconds
            text += f" · {remaining//60} min left" if remaining >= 60 else f" · {remaining} sec left"
        p.drawText(QtCore.QRectF(rect.right()-(34 if bar.hands_free else 14)-timer_width,rect.y(),timer_width,40),QtCore.Qt.AlignVCenter|QtCore.Qt.AlignRight,text)
