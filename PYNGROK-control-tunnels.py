#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ngrok GUI PRO (PyQt6)
=====================
Полнофункциональный клон ngrok-дашборда:
    • Tunnels  — карточки туннелей, старт/стоп, QR-код, копирование ссылки
    • Requests — живой лог HTTP-запросов (тянется с локального ngrok
                 inspector API http://127.0.0.1:4040/api/requests/http)
    • Serve    — быстрый запуск сохранённых локальных сервисов
    • Settings — язык (RU/EN), тема (тёмная/светлая), authtoken, профиль

Профиль организации: MANGIS TRADE INVST STROY

Установка:
    pip install PyQt6 pyngrok qrcode[pil] pillow requests

Запуск:
    python ngrok_pro.py
"""

import io
import re
import sys
import time
import webbrowser
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
import logging
from concurrent.futures import ThreadPoolExecutor

from PyQt6.QtCore import Qt, QEvent, QTimer, QPropertyAnimation, QEasingCurve, QAbstractAnimation, pyqtSignal, QObject, QSize, QByteArray
from PyQt6.QtGui import QPixmap, QCursor, QColor, QIcon, QPainter, QFont, QFontDatabase
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QFrame, QScrollArea, QProgressBar, QDialog, QLineEdit, QComboBox,
    QMessageBox, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
    QStackedWidget, QSizePolicy, QFileDialog,
)

try:
    from PyQt6.QtSvg import QSvgRenderer
except ImportError:
    QSvgRenderer = None

try:
    from pyngrok import ngrok
except ImportError:
    raise SystemExit("Не найден pyngrok. Установите: pip install pyngrok")

try:
    import qrcode
except ImportError:
    raise SystemExit("Не найден qrcode. Установите: pip install qrcode[pil] pillow")

try:
    import requests
except ImportError:
    requests = None

try:
    import keyring
except Exception:
    keyring = None


# ============================================================== ОРГАНИЗАЦИЯ
ORG_NAME = "GOVPRODE"
ORG_SHORT = "GOVPRODE"
ORG_TAG = "Corporate workspace"


# ============================================================== ТЕМЫ
# Полностью однотонная (монохромная) цветовая схема: один оттенок —
# тёмно-синий (navy, hue ≈ 222°) — на всех уровнях: фон, границы,
# приглушённый текст, акценты. Даже нейтральные "серые" тона на самом
# деле лёгкий navy-тинт, а не ахроматический серый — поэтому в
# интерфейсе буквально нет других цветов, кроме светлого и тёмно-синего.
THEMES = {
    "dark": dict(
        BG_APP="#0B111E", BG_SIDEBAR="#111827", BG_CARD="#161E31",
        BG_CARD_HOVER="#1C273F", BG_ITEM_SELECTED="#203055", BORDER="#323F5D",
        FG_TEXT="#EFF2FB", FG_MUTED="#8F9DBC", FG_FAINT="#5C6A8A",
        ACCENT_GREEN="#4976DF", ACCENT_GREEN_2="#7095EB", ACCENT_RED="#5C6A8A",
        ACCENT_RED_HOVER="#203055", ACCENT_BLUE="#4976DF", ACCENT_BLUE_2="#7095EB",
        ACCENT_VIOLET="#7095EB", BADGE_BG="#0F1524", SCROLLBAR="#323F5D",
        INPUT_BG="#121A2B",
    ),
    "light": dict(
        BG_APP="#F4F6FB", BG_SIDEBAR="#FBFCFD", BG_CARD="#FFFFFF",
        BG_CARD_HOVER="#EDF0F8", BG_ITEM_SELECTED="#E1E7F4", BORDER="#D7DDEA",
        FG_TEXT="#11192C", FG_MUTED="#566381", FG_FAINT="#848DA4",
        ACCENT_GREEN="#1F4293", ACCENT_GREEN_2="#2E57B8", ACCENT_RED="#848DA4",
        ACCENT_RED_HOVER="#E1E7F4", ACCENT_BLUE="#1F4293", ACCENT_BLUE_2="#2E57B8",
        ACCENT_VIOLET="#2E57B8", BADGE_BG="#EDF0F7", SCROLLBAR="#C6CDDD",
        INPUT_BG="#F4F6FA",
    ),
}

TL_RED = "#ff5f57"
TL_YELLOW = "#febc2e"
TL_GREEN = "#28c840"

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
ICON_CACHE: dict[tuple, QIcon] = {}

# ------------------------------------------------------------ built-in icons
# One consistent outline style (24x24, stroke-based) for every icon in the
# app. An assets/<name>.svg or .png next to the script still takes priority
# (see _raw_icon), so custom icon packs keep working — this is purely a
# vector fallback so the UI never ships with missing/blank icons.
_S = 'stroke="#000" stroke-width="2.6" fill="none" stroke-linecap="round" stroke-linejoin="round"'
BUILTIN_ICONS: dict[str, str] = {
    "globe": f'<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" {_S}/><path d="M3 12h18" {_S}/><ellipse cx="12" cy="12" rx="4" ry="9" {_S}/></svg>',
    "link": f'<svg viewBox="0 0 24 24"><path d="M9 15l6-6" {_S}/><path d="M10 7l1.2-1.2a3.5 3.5 0 015 5L15 12" {_S}/><path d="M14 17l-1.2 1.2a3.5 3.5 0 01-5-5L9 12" {_S}/></svg>',
    "copy": f'<svg viewBox="0 0 24 24"><rect x="9" y="9" width="11" height="11" rx="2" {_S}/><path d="M5 15V5a2 2 0 012-2h10" {_S}/></svg>',
    "open": f'<svg viewBox="0 0 24 24"><path d="M9 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-3" {_S}/><path d="M14 4h6v6" {_S}/><path d="M20 4L11 13" {_S}/></svg>',
    "eye": f'<svg viewBox="0 0 24 24"><path d="M2 12C2 12 5.5 5 12 5C18.5 5 22 12 22 12C22 12 18.5 19 12 19C5.5 19 2 12 2 12Z" {_S}/><circle cx="12" cy="12" r="3" {_S}/></svg>',
    "qr": f'<svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1" {_S}/><rect x="14" y="3" width="7" height="7" rx="1" {_S}/><rect x="3" y="14" width="7" height="7" rx="1" {_S}/><rect x="5.5" y="5.5" width="2" height="2" fill="#000"/><rect x="16.5" y="5.5" width="2" height="2" fill="#000"/><rect x="5.5" y="16.5" width="2" height="2" fill="#000"/><path d="M14 14h3v3h-3z" fill="#000"/><path d="M19 14h2v2h-2z" fill="#000"/><path d="M14 19h2v2h-2z" fill="#000"/><path d="M19 19h2v2h-2z" fill="#000"/></svg>',
    "stop": f'<svg viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="2" fill="#000"/></svg>',
    "play": f'<svg viewBox="0 0 24 24"><path d="M7 4.5v15l13-7.5z" fill="#000"/></svg>',
    "settings": f'<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3.2" {_S}/><path d="M12 2.5v3M12 18.5v3M21.5 12h-3M5.5 12h-3M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1M18.4 18.4l-2.1-2.1M7.7 7.7L5.6 5.6" {_S}/></svg>',
    "share": f'<svg viewBox="0 0 24 24"><circle cx="18" cy="5" r="2.6" {_S}/><circle cx="6" cy="12" r="2.6" {_S}/><circle cx="18" cy="19" r="2.6" {_S}/><path d="M8.3 10.7l7.4-4.4M8.3 13.3l7.4 4.4" {_S}/></svg>',
    "message-circle": f'<svg viewBox="0 0 24 24"><path d="M21 11.5a8.5 8.5 0 01-12.9 7.3L3 20l1.3-5A8.5 8.5 0 1121 11.5z" {_S}/></svg>',
    "add": f'<svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14" {_S}/></svg>',
    "remove": f'<svg viewBox="0 0 24 24"><path d="M4 7h16" {_S}/><path d="M9 7V5a1 1 0 011-1h4a1 1 0 011 1v2" {_S}/><path d="M6 7l1 13a2 2 0 002 2h6a2 2 0 002-2l1-13" {_S}/></svg>',
    "language": f'<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" {_S}/><path d="M3 9h18M3 15h18" {_S}/><ellipse cx="12" cy="12" rx="4" ry="9" {_S}/></svg>',
    "theme": f'<svg viewBox="0 0 24 24"><path d="M12 3a9 9 0 109 9 7 7 0 01-9-9z" {_S}/></svg>',
    "server": f'<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="7" rx="2" {_S}/><rect x="3" y="13" width="18" height="7" rx="2" {_S}/><path d="M7 7.5h.01M7 16.5h.01" stroke="#000" stroke-width="2.4" stroke-linecap="round"/></svg>',
    "serve": f'<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="7" rx="2" {_S}/><rect x="3" y="13" width="18" height="7" rx="2" {_S}/><path d="M7 7.5h.01M7 16.5h.01" stroke="#000" stroke-width="2.4" stroke-linecap="round"/></svg>',
    "tunnel": f'<svg viewBox="0 0 24 24"><path d="M4 20v-6a8 8 0 0116 0v6" {_S}/><path d="M4 20h2M18 20h2" {_S}/></svg>',
    "requests": f'<svg viewBox="0 0 24 24"><path d="M4 6h16M4 12h16M4 18h10" {_S}/></svg>',
}


def _svg_to_icon(svg_markup: str, size: int) -> QIcon:
    """Rasterize an inline SVG string (opaque shapes only) into a QIcon.
    Colors in the markup don't matter — load_icon() re-tints every pixel
    for the active theme via _tinted_pixmap()."""
    if QSvgRenderer is None:
        return QIcon()
    render_size = max(size * 8, 96)  # render big, downscale for crisp, fully-opaque edges
    renderer = QSvgRenderer(QByteArray(svg_markup.encode("utf-8")))
    if not renderer.isValid():
        return QIcon()
    pix = QPixmap(render_size, render_size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    renderer.render(painter)
    painter.end()
    return QIcon(pix)

# Current theme's icon colors, kept in sync by MainWindow.apply_theme().
# Icons are tinted against these instead of using whatever color happens to
# be baked into the source SVG/PNG file — otherwise an icon drawn for one
# theme silently disappears (near-invisible against the background) the
# moment the user switches to the other theme.
_ICON_THEME = {"text": THEMES["dark"]["FG_TEXT"], "muted": THEMES["dark"]["FG_MUTED"]}

# Every QLabel/QPushButton that carries an icon registers itself here so it
# can be retinted in place when the theme changes, without needing to be
# rebuilt from scratch.
_ICON_WIDGETS: "list" = []


def _tinted_pixmap(src_icon: QIcon, size: int, color: str) -> QPixmap:
    base = src_icon.pixmap(QSize(size, size))
    tinted = QPixmap(base.size())
    tinted.fill(Qt.GlobalColor.transparent)
    painter = QPainter(tinted)
    painter.drawPixmap(0, 0, base)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), QColor(color))
    painter.end()
    return tinted


def _raw_icon(name: str, size: int = 20) -> QIcon:
    key = ("__raw__", name, size)
    if key in ICON_CACHE:
        return ICON_CACHE[key]
    svg_path = ASSETS_DIR / f"{name}.svg"
    png_path = ASSETS_DIR / f"{name}.png"
    icon = QIcon(str(svg_path)) if svg_path.exists() else QIcon()
    if icon.isNull() and png_path.exists():
        icon = QIcon(str(png_path))
    if icon.isNull() and name in BUILTIN_ICONS:
        icon = _svg_to_icon(BUILTIN_ICONS[name], size)
    ICON_CACHE[key] = icon
    return icon


def load_icon(name: str, size: int = 18, role: str = "text") -> QIcon:
    """Load an icon tinted to match the current theme (role: 'text' or 'muted')."""
    color = _ICON_THEME.get(role, _ICON_THEME["text"])
    key = (name, size, color)
    if key in ICON_CACHE:
        return ICON_CACHE[key]
    raw = _raw_icon(name, size)
    if raw.isNull():
        ICON_CACHE[key] = raw
        return raw
    icon = QIcon(_tinted_pixmap(raw, size, color))
    ICON_CACHE[key] = icon
    return icon


def load_icon_label(name: str, size: int = 18, role: str = "text") -> QLabel:
    label = QLabel()
    label.setFixedSize(size + 10, size + 10)
    label.setProperty("_icon_name", name)
    label.setProperty("_icon_size", size)
    label.setProperty("_icon_role", role)
    icon = load_icon(name, size, role)
    if not icon.isNull():
        label.setPixmap(icon.pixmap(QSize(size, size)))
    _ICON_WIDGETS.append(label)
    return label


def set_button_icon(button: QPushButton, name: str, size: int = 18, role: str = "muted"):
    """Attach a theme-tinted icon to a QPushButton and register it for retinting."""
    button.setProperty("_icon_name", name)
    button.setProperty("_icon_size", size)
    button.setProperty("_icon_role", role)
    button.setIcon(load_icon(name, size, role))
    _ICON_WIDGETS.append(button)


def refresh_icon_theme(theme: dict):
    """Re-tint every registered icon widget for the given theme palette."""
    _ICON_THEME["text"] = theme["FG_TEXT"]
    _ICON_THEME["muted"] = theme["FG_MUTED"]
    alive = []
    for w in _ICON_WIDGETS:
        try:
            name = w.property("_icon_name")
            size = w.property("_icon_size")
            role = w.property("_icon_role") or "text"
            if not name:
                continue
            icon = load_icon(name, size, role)
            if isinstance(w, QLabel):
                if not icon.isNull():
                    w.setPixmap(icon.pixmap(QSize(size, size)))
            elif isinstance(w, QPushButton):
                w.setIcon(icon)
            alive.append(w)
        except RuntimeError:
            # underlying C++ widget was deleted — drop it from the registry
            continue
    _ICON_WIDGETS[:] = alive


class PerformanceOptimizer(QObject):
    def __init__(self, conn_timer: QTimer, request_timer: QTimer):
        super().__init__()
        self.conn_timer = conn_timer
        self.request_timer = request_timer
        self.current_page = 0
        self.window_active = True

    def set_page(self, index: int):
        self.current_page = index
        self._apply_timing_rules()

    def set_window_active(self, active: bool):
        self.window_active = active
        self._apply_timing_rules()

    def _apply_timing_rules(self):
        if not self.window_active:
            self.conn_timer.stop()
            self.request_timer.stop()
            return

        self.conn_timer.setInterval(CONN_POLL_INTERVAL_MS)
        if not self.conn_timer.isActive():
            self.conn_timer.start()

        if self.current_page == 1:
            self.request_timer.setInterval(REQUEST_POLL_INTERVAL_MS)
        else:
            self.request_timer.setInterval(max(REQUEST_POLL_INTERVAL_MS * 2, 3000))

        if not self.request_timer.isActive():
            self.request_timer.start()


# ============================================================== ПЕРЕВОДЫ
STRINGS = {
    "en": dict(
        nav_tunnels="Tunnels", nav_requests="Requests", nav_serve="Serve",
        nav_settings="Settings", active_tunnels="Active Tunnels",
        light_mode="Light Mode", dark_mode="Dark Mode",
        page_tunnels_title="Tunnels", new_tunnel="New Tunnel",
        active_tunnels_sub=lambda n: f"{n} active tunnel{'s' if n != 1 else ''}",
        inactive=lambda n, exp: f"{'⌄' if exp else '›'}  INACTIVE ({n})",
        connections="Connections", stop="Stop", start="Start", qr="QR",
        new_tunnel_title="New Tunnel", local_port="Local Port",
        protocol="Protocol", name_optional="Display Name (optional)",
        port_placeholder="4242", name_placeholder="Webhooks",
        proto_http_title="HTTP", proto_http_sub="Web servers, APIs",
        proto_tcp_title="TCP", proto_tcp_sub="Databases, SSH",
        tcp_badge="PRO",
        tcp_billing_notice="TCP tunnels require a billing method (card) linked to your ngrok account. It won't be charged — it's just identity verification.",
        notice_billing_title="Billing not linked",
        notice_billing_msg="This ngrok account has no card on file, so TCP tunnels are disabled. HTTP tunnels still work — or add a card (won't be charged) at dashboard.ngrok.com/settings#id-verification.",
        notice_generic_error_title="Couldn't start tunnel",
        cancel="Cancel", create="Create", create_tunnel="Create Tunnel", error="Error",
        error_port="Port must be a number", error_port_range="Port must be between 1 and 65535",
        error_duplicate_port=lambda port: f"A tunnel on port {port} is already open",
        error_closed_tunnel_exists=lambda port: f"A closed tunnel on port {port} already exists. Restart it from inactive list.",
        tunnel_error="Tunnel error",
        qr_title="Connection QR code", qr_hint="Scan with your phone camera",
        close="Close",
        req_title="Requests", req_sub="Live HTTP traffic through your tunnels",
        req_clear="Clear", req_empty="No requests captured yet.",
        req_empty_hint="Open one of your tunnel URLs to see traffic here.",
        req_offline="ngrok inspector isn't reachable (127.0.0.1:4040).",
        req_col_method="METHOD", req_col_path="PATH", req_col_status="STATUS",
        req_col_time="TIME",
        serve_title="Serve", serve_sub="Quick-launch your saved local services",
        serve_add="Add service", serve_empty="No saved services yet.",
        serve_empty_hint="Add a local port to launch it in one click.",
        serve_launch="Launch", serve_remove="Remove", serve_running="Running",
        set_title="Settings", set_sub="Preferences for this workspace",
        set_general="General", set_language="Language", set_theme="Theme",
        set_ngrok="ngrok", set_authtoken="Authtoken",
        set_authtoken_ph="Paste your ngrok authtoken",
        set_save="Save", set_saved="Saved ✓",
        set_profile="Profile", set_org="Organization", set_plan="Plan",
        set_plan_value="Business",
        set_about="About", set_version="Version", set_status="All systems operational",
        comments_label="Comments", share_label="Share",
        copy_link="Copy link", open_link="Open link", remove_service="Remove service",
        max_tunnels_reached="Maximum active tunnels reached",
        theme_dark="Dark", theme_light="Light",
        link_copied_title="Copied", link_copied_msg="Link copied to clipboard",
        share_toast_title="Ready to share", share_toast_msg="Link copied — paste it anywhere to share.",
        qr_copy_url="Copy URL", qr_save_png="Save PNG", qr_copied_btn="Copied ✓",
        qr_saved_title="QR saved", qr_saved_msg=lambda path: f"Saved to {path}",
        qr_save_failed_title="Save failed",
    ),
    "ru": dict(
        nav_tunnels="Туннели", nav_requests="Запросы", nav_serve="Серверы",
        nav_settings="Настройки", active_tunnels="Активные туннели",
        light_mode="Светлая тема", dark_mode="Тёмная тема",
        page_tunnels_title="Туннели", new_tunnel="Новый туннель",
        active_tunnels_sub=lambda n: f"{n} активных туннел{'ей' if n != 1 else 'ь'}",
        inactive=lambda n, exp: f"{'⌄' if exp else '›'}  НЕАКТИВНЫЕ ({n})",
        connections="Подключения", stop="Стоп", start="Старт", qr="QR",
        new_tunnel_title="Новый туннель", local_port="Локальный порт",
        protocol="Протокол", name_optional="Отображаемое имя (необязательно)",
        port_placeholder="4242", name_placeholder="Webhooks",
        proto_http_title="HTTP", proto_http_sub="Веб-серверы, API",
        proto_tcp_title="TCP", proto_tcp_sub="Базы данных, SSH",
        tcp_badge="PRO",
        tcp_billing_notice="TCP-туннель работает только у аккаунтов с привязанным способом оплаты (картой). Списаний не будет — это только верификация.",
        notice_billing_title="Биллинг не привязан",
        notice_billing_msg="У этого ngrok-аккаунта не привязана карта, поэтому TCP-туннели недоступны. HTTP всё ещё работает — или привяжите карту (списаний не будет) на dashboard.ngrok.com/settings#id-verification.",
        notice_generic_error_title="Не удалось запустить туннель",
        cancel="Отмена", create="Создать", create_tunnel="Создать туннель", error="Ошибка",
        error_port="Порт должен быть числом", error_port_range="Порт должен быть между 1 и 65535",
        error_duplicate_port=lambda port: f"Туннель на порту {port} уже открыт",
        error_closed_tunnel_exists=lambda port: f"Закрытый туннель на порту {port} уже существует. Перезапустите его из списка неактивных.",
        tunnel_error="Ошибка туннеля",
        qr_title="QR-код подключения", qr_hint="Отсканируйте камерой телефона",
        close="Закрыть",
        req_title="Запросы", req_sub="Живой HTTP-трафик через ваши туннели",
        req_clear="Очистить", req_empty="Запросов пока нет.",
        req_empty_hint="Откройте один из адресов туннеля, чтобы увидеть трафик.",
        req_offline="Инспектор ngrok недоступен (127.0.0.1:4040).",
        req_col_method="МЕТОД", req_col_path="ПУТЬ", req_col_status="СТАТУС",
        req_col_time="ВРЕМЯ",
        serve_title="Серверы", serve_sub="Быстрый запуск сохранённых локальных сервисов",
        serve_add="Добавить сервис", serve_empty="Сохранённых сервисов пока нет.",
        serve_empty_hint="Добавьте локальный порт, чтобы запускать его в один клик.",
        serve_launch="Запустить", serve_remove="Удалить", serve_running="Запущен",
        set_title="Настройки", set_sub="Параметры этого рабочего пространства",
        set_general="Основные", set_language="Язык", set_theme="Тема",
        set_ngrok="ngrok", set_authtoken="Authtoken",
        set_authtoken_ph="Вставьте ваш ngrok authtoken",
        set_save="Сохранить", set_saved="Сохранено ✓",
        set_profile="Профиль", set_org="Организация", set_plan="Тариф",
        set_plan_value="Business",
        set_about="О программе", set_version="Версия", set_status="Все системы работают",
        comments_label="Комментарии", share_label="Поделиться",
        copy_link="Копировать ссылку", open_link="Открыть ссылку", remove_service="Удалить сервис",
        max_tunnels_reached="Достигнуто максимальное количество туннелей",
        theme_dark="Тёмная", theme_light="Светлая",
        link_copied_title="Скопировано", link_copied_msg="Ссылка скопирована в буфер обмена",
        share_toast_title="Готово к отправке", share_toast_msg="Ссылка скопирована — вставьте её куда угодно.",
        qr_copy_url="Копировать URL", qr_save_png="Сохранить PNG", qr_copied_btn="Скопировано ✓",
        qr_saved_title="QR сохранён", qr_saved_msg=lambda path: f"Сохранено: {path}",
        qr_save_failed_title="Не удалось сохранить",
    ),
}


class Translator:
    """Глобальный переключатель языка. t(key) достаёт строку текущего языка."""

    def __init__(self, lang="en"):
        self.lang = lang

    def t(self, key, *args):
        val = STRINGS[self.lang][key]
        return val(*args) if callable(val) else val

    def toggle(self):
        self.lang = "ru" if self.lang == "en" else "en"


TR = Translator("en")

# logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# configuration constants
REQUEST_TIMEOUT = 3.0
CONN_POLL_INTERVAL_MS = 1000
REQUEST_POLL_INTERVAL_MS = 1500
MAX_REQUEST_ROWS = 500
MAX_TUNNELS_SLOTS = 4


def is_ngrok_billing_error(err) -> bool:
    """True if this is ngrok's 'you must add a card for TCP endpoints' error
    (ERR_NGROK_8013) rather than some other failure."""
    text = str(err)
    markers = ("ERR_NGROK_8013", "credit or debit card", "id-verification")
    return any(mk.lower() in text.lower() for mk in markers)


def clean_error_text(text: str, limit: int = 240) -> str:
    """Collapse a raw (often multi-line, log-prefixed) exception message into
    something short enough to show in a toast instead of a wall of text."""
    text = re.sub(r"\s+", " ", str(text)).strip()
    if len(text) > limit:
        text = text[:limit].rstrip() + "…"
    return text


# ------------------------------------------------------------ neon glow
# Primary action buttons get a soft blue glow (drop shadow with no offset)
# to read as "neon". Registered so the glow color can be re-tinted whenever
# the theme changes, the same way icons are.
_GLOW_WIDGETS: list = []


def apply_neon_glow(widget: QWidget, blur: int = 26) -> QGraphicsDropShadowEffect:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, 0)
    widget.setGraphicsEffect(effect)
    _GLOW_WIDGETS.append((widget, effect))
    return effect


def refresh_glow_theme(theme: dict):
    color = QColor(theme["ACCENT_BLUE"])
    color.setAlpha(210)
    alive = []
    for widget, effect in _GLOW_WIDGETS:
        try:
            effect.setColor(color)
            alive.append((widget, effect))
        except RuntimeError:
            continue
    _GLOW_WIDGETS[:] = alive


class WorkerSignals(QObject):
    tunnel_opened = pyqtSignal(object, object)  # (info, error)
    tunnel_closed = pyqtSignal(str, object)     # (public_url, error)
    conn_count = pyqtSignal(str, int)           # (public_url, count)
    requests_fetched = pyqtSignal(object)       # (list or None)
    authtoken_validated = pyqtSignal(str, bool, object)  # (token, success, error)


class MainController:
    """Контроллер фоновых задач и взаимодействия с NgrokManager.
    Все длительные операции выполняются здесь, а результаты эмитятся через сигналы.
    """

    def __init__(self, manager, max_workers: int = 4):
        self.manager = manager
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.signals = WorkerSignals()

    def open_tunnel_async(self, port: int, proto: str = "http", name: str | None = None):
        def task():
            try:
                info = self.manager.open_tunnel(port, proto=proto, name=name or None)
                return (info, None)
            except Exception as e:
                return (None, e)
        fut = self.executor.submit(task)
        def done(f):
            try:
                info, err = f.result()
            except Exception as e:
                info, err = None, e
            try:
                self.signals.tunnel_opened.emit(info, err)
            except RuntimeError:
                logger.debug("Signal tunnel_opened not emitted: WorkerSignals deleted")
        fut.add_done_callback(done)
        return fut

    def close_tunnel_async(self, public_url: str):
        def task():
            try:
                self.manager.close_tunnel(public_url)
                return (public_url, None)
            except Exception as e:
                return (public_url, e)
        fut = self.executor.submit(task)
        def done(f):
            try:
                public_url, err = f.result()
            except Exception as e:
                public_url, err = public_url, e
            try:
                self.signals.tunnel_closed.emit(public_url, err)
            except RuntimeError:
                logger.debug("Signal tunnel_closed not emitted: WorkerSignals deleted")
        fut.add_done_callback(done)
        return fut

    def restart_tunnel_async(self, old_info):
        # reuse open_tunnel_async by extracting port
        try:
            port = int(old_info.local_addr.split(":")[1])
        except Exception:
            # emit error through tunnel_opened
            try:
                self.signals.tunnel_opened.emit(None, RuntimeError("Invalid local_addr"))
            except RuntimeError:
                logger.debug("Signal tunnel_opened not emitted: WorkerSignals deleted")
            return None
        return self.open_tunnel_async(port, proto=old_info.proto, name=old_info.name)

    def fetch_connection_count_async(self, public_url: str):
        def task():
            try:
                cnt = self.manager.fetch_connection_count(public_url)
                return cnt
            except Exception as e:
                logger.exception("Background fetch_connection_count failed for %s", public_url)
                return 0
        fut = self.executor.submit(task)
        def done(f):
            try:
                cnt = f.result()
            except Exception:
                cnt = 0
            try:
                self.signals.conn_count.emit(public_url, cnt)
            except RuntimeError:
                logger.debug("Signal conn_count not emitted: WorkerSignals deleted")
        fut.add_done_callback(done)
        return fut

    def fetch_http_requests_async(self, limit: int = 25):
        def task():
            try:
                return self.manager.fetch_http_requests(limit=limit)
            except Exception as e:
                logger.exception("Background fetch_http_requests failed")
                return None
        fut = self.executor.submit(task)
        def done(f):
            try:
                data = f.result()
            except Exception:
                data = None
            try:
                self.signals.requests_fetched.emit(data)
            except RuntimeError:
                logger.debug("Signal requests_fetched not emitted: WorkerSignals deleted")
        fut.add_done_callback(done)
        return fut

    def validate_authtoken_async(self, token: str):
        def task():
            try:
                self.manager.set_authtoken(token)
                return (token, True, None)
            except Exception as e:
                return (token, False, e)
        fut = self.executor.submit(task)
        def done(f):
            try:
                token, success, error = f.result()
            except Exception as e:
                token, success, error = token, False, e
            try:
                self.signals.authtoken_validated.emit(token, success, error)
            except RuntimeError:
                logger.debug("Signal authtoken_validated not emitted: WorkerSignals deleted")
        fut.add_done_callback(done)
        return fut

    def shutdown(self, wait: bool = False):
        try:
            self.executor.shutdown(wait=wait)
        except Exception:
            pass



# ============================================================== МОДЕЛЬ
@dataclass
class TunnelInfo:
    name: str
    public_url: str
    local_addr: str
    proto: str
    started_at: float = field(default_factory=time.time)
    connections: int = 0
    active: bool = True


@dataclass
class SavedService:
    name: str
    port: int
    proto: str = "http"


class NgrokManager:
    def __init__(self):
        self.tunnels: dict[str, TunnelInfo] = {}
        self.authtoken: str = ""

    def set_authtoken(self, token: str):
        if token:
            ngrok.set_auth_token(token)
            self.authtoken = token
        else:
            self.authtoken = ""

    def open_tunnel(self, port: int, proto: str = "http", name: str | None = None) -> TunnelInfo:
        t = ngrok.connect(addr=port, proto=proto)
        info = TunnelInfo(
            name=name or f"localhost:{port}",
            public_url=t.public_url,
            local_addr=f"localhost:{port}",
            proto=proto,
        )
        self.tunnels[t.public_url] = info
        return info

    def close_tunnel(self, public_url: str):
        ngrok.disconnect(public_url)
        self.tunnels.pop(public_url, None)

    def close_all(self):
        for url in list(self.tunnels.keys()):
            try:
                ngrok.disconnect(url)
            except Exception:
                pass
        self.tunnels.clear()

    def fetch_connection_count(self, public_url: str) -> int:
        if requests is None:
            return 0
        try:
            r = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            for t in data.get("tunnels", []):
                if t.get("public_url") == public_url:
                    return t.get("metrics", {}).get("conns", {}).get("count", 0)
        except Exception as e:
            logger.exception("fetch_connection_count failed for %s", public_url)
        return 0

    def fetch_http_requests(self, limit: int = 25):
        """Живой лог HTTP-запросов из локального ngrok inspector API."""
        if requests is None:
            return None
        try:
            r = requests.get(f"http://127.0.0.1:4040/api/requests/http?limit={limit}", timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            return data.get("requests", [])
        except Exception as e:
            # inspector may be temporarily unavailable (don't spam traceback)
            logger.debug("fetch_http_requests failed: %s", e)
            return None


def elapsed_str(started_at: float) -> str:
    secs = int(time.time() - started_at)
    if secs < 60:
        return f"{secs}s"
    mins = secs // 60
    if mins < 60:
        return f"{mins}m"
    hours = mins // 60
    return f"{hours}h {mins % 60}m"


# ============================================================== QSS
def build_stylesheet(p: dict) -> str:
    return f"""
QWidget {{
    font-family: "Poppins", "Manrope", "Inter", -apple-system, "Segoe UI Variable",
                 "Segoe UI", "SF Pro Display", "Helvetica Neue", Arial, sans-serif;
    color: {p['FG_TEXT']};
}}
/* Default button style to make controls vibrant and clickable */
QPushButton {{
    background-color: {p['BG_CARD']};
    color: {p['FG_TEXT']};
    border: 1px solid transparent;
    padding: 6px 10px;
    border-radius: 10px;
}}
QPushButton:hover {{
    background-color: {p['BG_CARD_HOVER']};
}}
/* Primary buttons (new/create) */
#NewTunnelBtn, #PrimaryBtn {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {p['ACCENT_BLUE']}, stop:1 {p['ACCENT_BLUE_2']});
    color: {p['FG_TEXT']};
    border: none;
    border-radius: 10px;
    padding: 8px 18px;
    font-weight: 700;
    font-size: 13px;
}}
#NewTunnelBtn:hover, #PrimaryBtn:hover {{ background-color: {p['ACCENT_BLUE_2']}; }}
/* Icon-style ghost buttons (small icon-only controls) */
#IconGhost {{
    background: transparent;
    border: none;
    color: {p['FG_MUTED']};
    font-size: 13px;
}}
#IconGhost:hover {{ color: {p['ACCENT_BLUE']}; background: transparent; }}

#AppRoot {{
    background-color: {p['BG_APP']};
    border-radius: 12px;
}}
#AppHeader {{
    background-color: {p['BG_CARD']};
    border-bottom: 1px solid {p['BORDER']};
}}
#HeaderTitle {{
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 0.2px;
    color: {p['FG_TEXT']};
}}
#HeaderStatus {{
    color: {p['FG_MUTED']};
    font-size: 12px;
}}
#StatusBar {{
    background-color: {p['BG_CARD']};
    border-top: 1px solid {p['BORDER']};
}}
#StatusText {{
    color: {p['FG_MUTED']};
    font-size: 12px;
}}
#StatusBadge {{
    color: {p['FG_TEXT']};
    background-color: {p['BADGE_BG']};
    border: 1px solid {p['BORDER']};
    border-radius: 10px;
    padding: 4px 10px;
    font-size: 11px;
}}
#Sidebar {{
    background-color: {p['BG_SIDEBAR']};
    border-right: 1px solid {p['BORDER']};
}}
#NavItem {{
    background: transparent;
    border-radius: 8px;
    padding: 8px 12px;
    text-align: left;
    font-size: 13px;
    color: {p['FG_MUTED']};
}}
#NavItem:hover {{
    background-color: {p['BG_CARD_HOVER']};
    color: {p['FG_TEXT']};
}}
#NavItem[selected="true"] {{
    background-color: {p['BG_ITEM_SELECTED']};
    color: {p['FG_TEXT']};
    font-weight: 600;
}}
#PageTitle {{
    font-size: 22px;
    font-weight: 800;
    letter-spacing: 0.2px;
    color: {p['FG_TEXT']};
}}
#SubHeader {{
    color: {p['FG_MUTED']};
    font-size: 12px;
}}
#Card {{
    background-color: {p['BG_CARD']};
    border: 1px solid {p['BORDER']};
    border-radius: 12px;
}}
#Card:hover {{ background-color: {p['BG_CARD_HOVER']}; }}
#Card[hovered="true"] {{ border: 1px solid {p['ACCENT_BLUE']}; }}
#TunnelName {{
    font-size: 15px;
    font-weight: 700;
    color: {p['FG_TEXT']};
}}
#Badge {{
    background-color: {p['BADGE_BG']};
    color: {p['FG_MUTED']};
    font-size: 10px;
    font-weight: 700;
    border-radius: 5px;
    padding: 2px 6px;
}}
#UrlLabel {{
    color: {p['ACCENT_BLUE']};
    font-size: 13px;
}}
#MutedSmall {{
    color: {p['FG_MUTED']};
    font-size: 12px;
}}
#FaintSmall {{
    color: {p['FG_FAINT']};
    font-size: 12px;
}}
#StopBtn {{
    background-color: {p['ACCENT_RED']};
    color: {p['FG_TEXT']};
    border: none;
    border-radius: 10px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 700;
}}
#StopBtn:hover {{ background-color: {p['ACCENT_RED_HOVER']}; }}
#StartBtn {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {p['ACCENT_GREEN']}, stop:1 {p['ACCENT_GREEN_2']});
    color: #FFFFFF;
    border: none;
    border-radius: 10px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 700;
}}
#QrBtn {{
    background-color: {p['BADGE_BG']};
    color: {p['ACCENT_BLUE']};
    border: none;
    border-radius: 14px;
    padding: 5px 14px;
    font-size: 11px;
    font-weight: 700;
}}
#QrBtn:hover {{ background-color: {p['BG_CARD_HOVER']}; }}
#IconGhost {{
    background: transparent;
    border: none;
    color: {p['FG_MUTED']};
    font-size: 13px;
}}
#IconGhost:hover {{ color: {p['ACCENT_BLUE']}; }}
#InactiveHeader {{
    color: {p['FG_MUTED']};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QProgressBar {{
    background-color: {p['BADGE_BG']};
    border: none;
    border-radius: 2px;
    max-height: 4px;
    min-height: 4px;
}}
QProgressBar::chunk {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {p['ACCENT_BLUE']}, stop:1 {p['ACCENT_BLUE_2']});
    border-radius: 2px;
}}
#GlobeAvatar {{
    background-color: {p['BADGE_BG']};
    border-radius: 16px;
}}
#StatusDot {{
    background-color: {p['ACCENT_GREEN']};
    border-radius: 5px;
}}
#UserRow {{
    background: transparent;
    border-top: 1px solid {p['BORDER']};
}}
#UserRow:hover {{ background-color: {p['BG_CARD_HOVER']}; border-radius: 8px; }}
#UserName {{
    font-size: 12px;
    font-weight: 700;
    color: {p['FG_TEXT']};
}}
#UserEmail {{
    font-size: 9px;
    color: {p['FG_MUTED']};
}}
#Avatar {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {p['ACCENT_VIOLET']}, stop:1 {p['ACCENT_BLUE_2']});
    border-radius: 15px;
    color: white;
    font-weight: 700;
    font-size: 12px;
}}
#SectionCard {{
    background-color: {p['BG_CARD']};
    border: 1px solid {p['BORDER']};
    border-radius: 12px;
}}
#SectionLabel {{
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1px;
    color: {p['FG_MUTED']};
}}
#RowLabel {{ font-size: 12px; color: {p['FG_TEXT']}; font-weight: 600; }}
#TableHeader {{
    color: {p['FG_FAINT']};
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1px;
}}
#MethodBadge {{
    background-color: {p['BADGE_BG']};
    color: {p['ACCENT_BLUE']};
    font-weight: 800;
    font-size: 10px;
    border-radius: 4px;
    padding: 2px 6px;
}}
#StatusOk {{ color: {p['ACCENT_GREEN']}; font-weight: 700; font-size: 11px; }}
#StatusErr {{ color: {p['ACCENT_RED']}; font-weight: 700; font-size: 11px; }}
#EmptyTitle {{ color: {p['FG_TEXT']}; font-size: 14px; font-weight: 700; }}
#EmptyHint {{ color: {p['FG_MUTED']}; font-size: 12px; }}
QDialog {{
    background-color: {p['BG_CARD']};
}}
QLineEdit, QComboBox {{
    background-color: {p['INPUT_BG']};
    border: 1px solid {p['BORDER']};
    border-radius: 8px;
    padding: 6px 10px;
    color: {p['FG_TEXT']};
    font-size: 12px;
}}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {p['ACCENT_BLUE']}; }}
QLabel#DialogLabel {{
    color: {p['FG_MUTED']};
    font-size: 11px;
}}
QPushButton#DialogCreate {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {p['ACCENT_GREEN']}, stop:1 {p['ACCENT_GREEN_2']});
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 700;
}}
QPushButton#DialogCancel {{
    background-color: {p['BG_CARD']};
    border: 1px solid {p['BORDER']};
    border-radius: 8px;
    padding: 8px 16px;
    color: {p['FG_TEXT']};
}}
#DialogPanel {{
    background-color: {p['BG_CARD']};
    border: 1px solid {p['BORDER']};
    border-radius: 16px;
}}
#DialogTitle {{
    font-size: 17px;
    font-weight: 700;
    color: {p['FG_TEXT']};
}}
#DialogCloseBtn {{
    background-color: {p['BG_APP']};
    border: none;
    border-radius: 13px;
    color: {p['FG_MUTED']};
    font-size: 12px;
}}
#DialogCloseBtn:hover {{ color: {p['FG_TEXT']}; background-color: {p['BG_CARD_HOVER']}; }}
#DialogSectionLabel {{
    color: {p['FG_MUTED']};
    font-size: 12px;
    font-weight: 500;
}}
#ProtocolCard {{
    background-color: {p['BG_APP']};
    border: 1px solid {p['BORDER']};
    border-radius: 12px;
    text-align: left;
    padding: 0px;
}}
#ProtocolCard:hover {{ border: 1px solid {p['FG_FAINT']}; }}
#ProtocolCard[selected="true"] {{
    background-color: {p['BG_CARD_HOVER']};
    border: 1.5px solid {p['FG_TEXT']};
}}
#ProtocolTitle {{
    font-size: 13px;
    font-weight: 700;
    color: {p['FG_TEXT']};
}}
#ProtocolSubtitle {{
    font-size: 11px;
    color: {p['FG_MUTED']};
}}
#ProtocolBadge {{
    background-color: {p['ACCENT_BLUE']};
    color: #FFFFFF;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.5px;
    border-radius: 6px;
    padding: 2px 6px;
}}
#QrImageFrame {{
    background-color: #FFFFFF;
    border-radius: 14px;
}}
#QrActionBtn {{
    background-color: {p['BADGE_BG']};
    color: {p['FG_TEXT']};
    border: 1px solid {p['BORDER']};
    border-radius: 9px;
    padding: 9px 12px;
    font-size: 12px;
    font-weight: 600;
}}
#QrActionBtn:hover {{ background-color: {p['BG_CARD_HOVER']}; border-color: {p['ACCENT_BLUE']}; }}
#TcpNotice {{
    background-color: {p['BADGE_BG']};
    border: 1px solid {p['BORDER']};
    border-radius: 10px;
    color: {p['FG_MUTED']};
    font-size: 11px;
    padding: 10px 12px;
}}
#Toast {{
    background-color: {p['BG_CARD']};
    border: 1px solid {p['ACCENT_BLUE']};
    border-radius: 12px;
}}
#Toast[kind="error"] {{ border: 1.5px solid {p['ACCENT_BLUE']}; }}
#Toast[kind="success"] {{ border: 1.5px solid {p['ACCENT_GREEN']}; }}
#ToastTitle {{
    font-size: 13px;
    font-weight: 700;
    color: {p['FG_TEXT']};
}}
#ToastMessage {{
    font-size: 11.5px;
    color: {p['FG_MUTED']};
}}
#ToastClose {{
    background-color: transparent;
    border: none;
    color: {p['FG_MUTED']};
    border-radius: 10px;
    font-size: 11px;
}}
#ToastClose:hover {{ color: {p['FG_TEXT']}; background-color: {p['BG_CARD_HOVER']}; }}
#DialogBigInput {{
    background-color: {p['BG_APP']};
    border: 1px solid {p['BORDER']};
    border-radius: 10px;
    padding: 10px 12px;
    color: {p['FG_TEXT']};
    font-size: 13px;
}}
#DialogBigInput:focus {{ border: 1px solid {p['FG_TEXT']}; }}
#DialogCancel2 {{
    background-color: transparent;
    border: none;
    color: {p['FG_MUTED']};
    padding: 9px 16px;
    font-size: 13px;
    font-weight: 600;
}}
#DialogCancel2:hover {{ color: {p['FG_TEXT']}; }}
#CreateTunnelBtn {{
    background-color: {p['FG_TEXT']};
    color: {p['BG_APP']};
    border: none;
    border-radius: 10px;
    padding: 9px 18px;
    font-size: 13px;
    font-weight: 700;
}}
#CreateTunnelBtn:hover {{ background-color: {p['FG_MUTED']}; }}
#ToggleBtn {{
    background-color: {p['BADGE_BG']};
    color: {p['FG_TEXT']};
    border: 1px solid {p['BORDER']};
    border-radius: 14px;
    padding: 5px 14px;
    font-size: 11px;
    font-weight: 700;
}}
#ToggleBtn:hover {{ border: 1px solid {p['ACCENT_BLUE']}; color: {p['ACCENT_BLUE']}; }}
QScrollArea {{ border: none; background-color: {p['BG_APP']}; }}
QScrollArea > QWidget > QWidget {{ background-color: {p['BG_APP']}; }}
#ListContainer {{ background-color: {p['BG_APP']}; }}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
}}
QScrollBar::handle:vertical {{
    background: {p['SCROLLBAR']};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""


# ============================================================== ВИДЖЕТЫ
class PulsingDot(QLabel):
    """Мигающая зелёная точка — статус 'live'."""

    def __init__(self, size=10):
        super().__init__()
        self.setObjectName("StatusDot")
        self.setFixedSize(size, size)
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._anim = QPropertyAnimation(self._effect, b"opacity")
        self._anim.setDuration(1600)
        self._anim.setStartValue(1.0)
        self._anim.setKeyValueAt(0.5, 0.25)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._anim.setLoopCount(-1)
        self._anim.start()

    def stop(self):
        try:
            self._anim.stop()
        except Exception:
            pass
        try:
            self._effect.deleteLater()
        except Exception:
            pass


class AnimatedIconButton(QPushButton):
    REST_BLUR = 14
    HOVER_BLUR = 26

    def __init__(self, icon: str | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("IconGhost")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedSize(34, 34)
        if icon:
            set_button_icon(self, icon, size=20, role="text")
            self.setIconSize(QSize(20, 20))
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(self.REST_BLUR)
        self._shadow.setColor(QColor(59, 130, 246, 130))
        self._shadow.setOffset(0, 0)
        self.setGraphicsEffect(self._shadow)
        self._hover_anim = QPropertyAnimation(self._shadow, b"blurRadius", self)
        self._hover_anim.setDuration(180)
        self._hover_anim.setStartValue(self.REST_BLUR)
        self._hover_anim.setEndValue(self.HOVER_BLUR)
        self._leave_anim = QPropertyAnimation(self._shadow, b"blurRadius", self)
        self._leave_anim.setDuration(180)
        self._leave_anim.setStartValue(self.HOVER_BLUR)
        self._leave_anim.setEndValue(self.REST_BLUR)

    def enterEvent(self, event):
        self._leave_anim.stop()
        self._hover_anim.setStartValue(self._shadow.blurRadius())
        self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_anim.stop()
        self._leave_anim.setStartValue(self._shadow.blurRadius())
        self._leave_anim.start()
        super().leaveEvent(event)


class AnimatedStackedWidget(QStackedWidget):
    """Switches pages instantly.

    NOTE: this used to wrap the incoming page in a QGraphicsOpacityEffect to
    fade it in. Every page here contains a QScrollArea, and Qt does not
    reliably composite QGraphicsOpacityEffect on top of a QAbstractScrollArea
    descendant — the scroll viewport's backing store gets corrupted, which
    showed up as a black rectangle with the *previous* page's widgets still
    visible underneath (e.g. Serve's rows bleeding into the Tunnels page).
    A plain setCurrentIndex() has none of that risk, so we use that.
    """

    def fade_to_index(self, index: int):
        if index == self.currentIndex():
            return
        self.setCurrentIndex(index)


class Toast(QFrame):
    """Small, non-modal, self-dismissing notification card.

    Used instead of QMessageBox for tunnel/ngrok errors: a native modal
    dialog popping up on top of a frameless, translucent main window is a
    known source of geometry glitches on some platforms/window managers
    (the parent window can end up resized/repositioned when the modal
    closes). A plain overlay widget has none of that risk.
    """

    def __init__(self, parent: QWidget, kind: str, title: str, message: str):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setProperty("kind", kind)
        self.setFixedWidth(360)
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(8)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("ToastTitle")
        title_lbl.setWordWrap(True)
        top.addWidget(title_lbl, 1)
        close_btn = QPushButton("✕")
        close_btn.setObjectName("ToastClose")
        close_btn.setFixedSize(20, 20)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.clicked.connect(self.dismiss)
        top.addWidget(close_btn)
        lay.addLayout(top)

        msg_lbl = QLabel(message)
        msg_lbl.setObjectName("ToastMessage")
        msg_lbl.setWordWrap(True)
        lay.addWidget(msg_lbl)

        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._effect.setOpacity(0.0)
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(200)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.dismiss)
        self._dismissed = False

    def show_animated(self, autohide_ms: int = 7000):
        self.adjustSize()
        self.show()
        self.raise_()
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        if autohide_ms:
            self._timer.start(autohide_ms)

    def dismiss(self):
        if self._dismissed:
            return
        self._dismissed = True
        self._timer.stop()
        self._anim.stop()
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(0.0)
        try:
            self._anim.finished.connect(self.deleteLater)
        except Exception:
            pass
        self._anim.start()


class TrafficLights(QWidget):
    def __init__(self, window: QWidget):
        super().__init__()
        self._win = window
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 0, 4)
        layout.setSpacing(8)

        layout.addWidget(self._dot(TL_RED, self._win.close))
        layout.addWidget(self._dot(TL_YELLOW, self._win.showMinimized))
        layout.addWidget(self._dot(TL_GREEN, self._toggle_max))
        layout.addStretch()

    def _dot(self, color: str, on_click) -> QPushButton:
        b = QPushButton()
        b.setFixedSize(12, 12)
        b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        b.setStyleSheet(f"QPushButton {{ background-color: {color}; border-radius: 6px; border: none; }}")
        b.clicked.connect(on_click)
        return b

    def _toggle_max(self):
        if self._win.isMaximized():
            self._win.showNormal()
        else:
            self._win.showMaximized()


class NavItem(QPushButton):
    def __init__(self, icon: str, key: str, selected: bool = False, on_click=None):
        super().__init__(TR.t(key))
        self.icon = icon
        self.key = key
        self.setObjectName("NavItem")
        self.setProperty("selected", "true" if selected else "false")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(34)
        set_button_icon(self, icon, size=18, role="muted")
        self.setIconSize(QSize(18, 18))
        if on_click:
            self.clicked.connect(on_click)

    def retranslate(self):
        self.setText(TR.t(self.key))

    def set_selected(self, selected: bool):
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)


class TunnelCard(QFrame):
    def __init__(self, info: TunnelInfo, on_stop, on_start, on_qr, on_toast=None):
        super().__init__()
        self.info = info
        self.on_stop = on_stop
        self.on_start = on_start
        self.on_qr = on_qr
        self.on_toast = on_toast
        self.setObjectName("Card")
        self._shadow = None
        self._hover_in = None
        self._hover_out = None
        self._progress_anim = None
        self._build()
        self._install_hover_shadow()

    def dispose(self):
        # остановка анимаций и эффектов, подготовка к удалению
        try:
            for child in self.findChildren(PulsingDot):
                try:
                    child.stop()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self.deleteLater()
        except Exception:
            pass

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(9)

        # ---- row 1: globe · name · badge · status dot · eye · stop/start
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        globe_wrap = QWidget()
        gw = QHBoxLayout(globe_wrap)
        gw.setContentsMargins(0, 0, 0, 0)
        globe = load_icon_label("globe", size=20, role="text")
        globe.setObjectName("GlobeAvatar")
        gw.addWidget(globe)
        row1.addWidget(globe_wrap)

        name = QLabel(self.info.name)
        name.setObjectName("TunnelName")
        row1.addWidget(name)

        badge = QLabel(self.info.proto.upper())
        badge.setObjectName("Badge")
        row1.addWidget(badge)

        if self.info.active:
            row1.addWidget(PulsingDot())

        row1.addStretch()

        eye = AnimatedIconButton("eye")
        eye.setToolTip(TR.t("open_link"))
        eye.clicked.connect(lambda: webbrowser.open(self.info.public_url))
        row1.addWidget(eye)

        self.toggle_btn = QPushButton(TR.t("stop") if self.info.active else TR.t("start"))
        self.toggle_btn.setObjectName("StopBtn" if self.info.active else "StartBtn")
        self.toggle_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        set_button_icon(self.toggle_btn, "stop" if self.info.active else "play", size=12,
                         role="text" if not self.info.active else "muted")
        self.toggle_btn.setIconSize(QSize(12, 12))
        self.toggle_btn.clicked.connect(self._on_toggle)
        row1.addWidget(self.toggle_btn)

        outer.addLayout(row1)

        # ---- row 2: link · url · copy · open · qr
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        link_icon = load_icon_label("link", size=16, role="text")
        link_icon.setObjectName("MutedSmall")
        row2.addWidget(link_icon)

        url_lbl = QLabel(
            f'<a href="{self.info.public_url}" style="color:inherit; text-decoration:none;">{self.info.public_url}</a>'
        )
        url_lbl.setObjectName("UrlLabel")
        url_lbl.setOpenExternalLinks(True)
        url_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        row2.addWidget(url_lbl)
        row2.addStretch()

        copy_btn = AnimatedIconButton("copy")
        copy_btn.setToolTip(TR.t("copy_link"))
        copy_btn.clicked.connect(self._copy_url)
        row2.addWidget(copy_btn)

        open_btn = AnimatedIconButton("open")
        open_btn.setToolTip(TR.t("open_link"))
        open_btn.clicked.connect(lambda: webbrowser.open(self.info.public_url))
        row2.addWidget(open_btn)

        qr_btn = AnimatedIconButton("qr")
        qr_btn.setToolTip(TR.t("qr"))
        qr_btn.clicked.connect(lambda: self.on_qr(self.info.public_url))
        row2.addWidget(qr_btn)

        outer.addLayout(row2)

        # ---- row 3: local address
        self.addr_lbl = QLabel(f"→  {self.info.local_addr}")
        self.addr_lbl.setObjectName("MutedSmall")
        outer.addWidget(self.addr_lbl)

        # ---- row 4: comments · elapsed time · share
        row4 = QHBoxLayout()
        row4.setSpacing(14)

        comments_wrap = QHBoxLayout()
        comments_wrap.setSpacing(4)
        comments_icon = load_icon_label("message-circle", size=13, role="text")
        comments_wrap.addWidget(comments_icon)
        self.comments_lbl = QLabel("0")
        self.comments_lbl.setObjectName("FaintSmall")
        comments_wrap.addWidget(self.comments_lbl)
        row4.addLayout(comments_wrap)

        self.time_lbl = QLabel(elapsed_str(self.info.started_at))
        self.time_lbl.setObjectName("FaintSmall")
        row4.addWidget(self.time_lbl)

        row4.addStretch()

        self.share_btn = QPushButton(TR.t("share_label"))
        self.share_btn.setObjectName("IconGhost")
        self.share_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        set_button_icon(self.share_btn, "share", size=13, role="text")
        self.share_btn.setIconSize(QSize(13, 13))
        self.share_btn.clicked.connect(self._on_share)
        row4.addWidget(self.share_btn)

        outer.addLayout(row4)

        # ---- connections label + animated gradient progress bar
        row5 = QHBoxLayout()
        self.conn_label = QLabel(TR.t("connections"))
        self.conn_label.setObjectName("MutedSmall")
        row5.addWidget(self.conn_label)
        row5.addStretch()
        self.conn_count_lbl = QLabel(f"{self.info.connections}/24")
        self.conn_count_lbl.setObjectName("MutedSmall")
        row5.addWidget(self.conn_count_lbl)
        outer.addLayout(row5)

        self.progress = QProgressBar()
        self.progress.setRange(0, 24)
        self.progress.setValue(self.info.connections)
        self.progress.setTextVisible(False)
        outer.addWidget(self.progress)

    # ---------------- hover: shadow lift + border glow ----------------
    def _install_hover_shadow(self):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(0)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 0))
        self.setGraphicsEffect(shadow)
        self._shadow = shadow

    def _shadow_alive(self) -> bool:
        if self._shadow is None:
            return False
        try:
            self._shadow.blurRadius()
            return True
        except RuntimeError:
            self._shadow = None
            return False

    def enterEvent(self, event):
        self.setProperty("hovered", "true")
        self.style().unpolish(self)
        self.style().polish(self)
        if not self._shadow_alive():
            self._install_hover_shadow()
        if self._shadow is not None:
            self._shadow.setOffset(0, 10)
            self._shadow.setColor(QColor(41, 98, 255, 90))
            anim = QPropertyAnimation(self._shadow, b"blurRadius", self)
            anim.setDuration(180)
            anim.setStartValue(self._shadow.blurRadius())
            anim.setEndValue(28)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._hover_in = anim
            anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setProperty("hovered", "false")
        self.style().unpolish(self)
        self.style().polish(self)
        if self._shadow_alive():
            anim = QPropertyAnimation(self._shadow, b"blurRadius", self)
            anim.setDuration(180)
            anim.setStartValue(self._shadow.blurRadius())
            anim.setEndValue(0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._hover_out = anim
            anim.start()
        super().leaveEvent(event)

    # ---------------- actions ----------------
    def _on_toggle(self):
        if self.info.active:
            self.on_stop(self.info.public_url)
        else:
            self.on_start(self.info.public_url)

    def _copy_url(self):
        QApplication.clipboard().setText(self.info.public_url)
        if self.on_toast:
            self.on_toast(TR.t("link_copied_title"), TR.t("link_copied_msg"), "success")

    def _on_share(self):
        # No universal desktop "system share sheet" API exists in PyQt6 —
        # copy-to-clipboard is the reliable cross-platform fallback the
        # spec calls for.
        QApplication.clipboard().setText(self.info.public_url)
        if self.on_toast:
            self.on_toast(TR.t("share_toast_title"), TR.t("share_toast_msg"), "success")

    def refresh(self):
        self.time_lbl.setText(elapsed_str(self.info.started_at))
        self.conn_count_lbl.setText(f"{self.info.connections}/24")
        target = min(self.info.connections, 24)
        if self._progress_anim is not None:
            self._progress_anim.stop()
        anim = QPropertyAnimation(self.progress, b"value", self)
        anim.setDuration(280)
        anim.setStartValue(self.progress.value())
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._progress_anim = anim
        anim.start()

    def animate_entry(self):
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(220)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.finished.connect(self._install_hover_shadow)
        self._entry_anim = anim
        anim.start()

    def retranslate(self):
        self.toggle_btn.setText(TR.t("stop") if self.info.active else TR.t("start"))
        self.conn_label.setText(TR.t("connections"))
        self.share_btn.setText(TR.t("share_label"))


class ProtocolOption(QPushButton):
    """Selectable card used inside the New Tunnel dialog's protocol picker."""

    def __init__(self, icon: str, title: str, subtitle: str, badge: str | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("ProtocolCard")
        self.setCheckable(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMinimumHeight(78)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(8)
        icon_lbl = load_icon_label(icon, size=16, role="text")
        top.addWidget(icon_lbl)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("ProtocolTitle")
        top.addWidget(title_lbl)
        top.addStretch()
        if badge:
            badge_lbl = QLabel(badge)
            badge_lbl.setObjectName("ProtocolBadge")
            top.addWidget(badge_lbl)
        lay.addLayout(top)

        sub_lbl = QLabel(subtitle)
        sub_lbl.setObjectName("ProtocolSubtitle")
        sub_lbl.setWordWrap(True)
        lay.addWidget(sub_lbl)
        lay.addStretch()

    def setSelected(self, selected: bool):
        self.setChecked(selected)
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)


class NewTunnelDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(TR.t("new_tunnel_title"))
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(403)
        self.result_data = None
        self._proto = "http"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        panel = QFrame()
        panel.setObjectName("DialogPanel")
        outer.addWidget(panel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 20, 24, 22)
        layout.setSpacing(16)

        # ---- title row -------------------------------------------------
        title_row = QHBoxLayout()
        title_lbl = QLabel(TR.t("new_tunnel_title"))
        title_lbl.setObjectName("DialogTitle")
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setObjectName("DialogCloseBtn")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.clicked.connect(self.reject)
        title_row.addWidget(close_btn)
        layout.addLayout(title_row)

        # ---- protocol ----------------------------------------------------
        proto_label = QLabel(TR.t("protocol"))
        proto_label.setObjectName("DialogSectionLabel")
        layout.addWidget(proto_label)

        proto_row = QHBoxLayout()
        proto_row.setSpacing(10)
        self.http_opt = ProtocolOption("globe", TR.t("proto_http_title"), TR.t("proto_http_sub"))
        self.tcp_opt = ProtocolOption("server", TR.t("proto_tcp_title"), TR.t("proto_tcp_sub"), badge=TR.t("tcp_badge"))
        self.http_opt.clicked.connect(lambda: self._select_proto("http"))
        self.tcp_opt.clicked.connect(lambda: self._select_proto("tcp"))
        proto_row.addWidget(self.http_opt)
        proto_row.addWidget(self.tcp_opt)
        layout.addLayout(proto_row)

        self.tcp_notice = QLabel(TR.t("tcp_billing_notice"))
        self.tcp_notice.setObjectName("TcpNotice")
        self.tcp_notice.setWordWrap(True)
        self.tcp_notice.setVisible(False)
        layout.addWidget(self.tcp_notice)

        self._select_proto("http")

        # ---- local port ----------------------------------------------------
        port_label = QLabel(TR.t("local_port"))
        port_label.setObjectName("DialogSectionLabel")
        layout.addWidget(port_label)
        self.port_edit = QLineEdit()
        self.port_edit.setObjectName("DialogBigInput")
        self.port_edit.setPlaceholderText(TR.t("port_placeholder"))
        layout.addWidget(self.port_edit)

        # ---- display name ----------------------------------------------------
        name_label = QLabel(TR.t("name_optional"))
        name_label.setObjectName("DialogSectionLabel")
        layout.addWidget(name_label)
        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("DialogBigInput")
        self.name_edit.setPlaceholderText(TR.t("name_placeholder"))
        layout.addWidget(self.name_edit)

        # ---- buttons ----------------------------------------------------
        layout.addSpacing(2)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()
        cancel_btn = QPushButton(TR.t("cancel"))
        cancel_btn.setObjectName("DialogCancel2")
        cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_btn.clicked.connect(self.reject)
        create_btn = QPushButton(f"⊕  {TR.t('create_tunnel')}")
        create_btn.setObjectName("CreateTunnelBtn")
        apply_neon_glow(create_btn, blur=24)
        create_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        create_btn.clicked.connect(self._on_create)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(create_btn)
        layout.addLayout(btn_row)

    def _select_proto(self, proto: str):
        self._proto = proto
        self.http_opt.setSelected(proto == "http")
        self.tcp_opt.setSelected(proto == "tcp")
        self.tcp_notice.setVisible(proto == "tcp")
        self.adjustSize()

    def _on_create(self):
        port_text = self.port_edit.text().strip()
        try:
            port = int(port_text)
        except Exception:
            QMessageBox.warning(self, TR.t("error"), TR.t("error_port"))
            return
        if not (1 <= port <= 65535):
            QMessageBox.warning(self, TR.t("error"), TR.t("error_port_range"))
            return
        self.result_data = (port, self._proto, self.name_edit.text().strip())
        self.accept()


class QRDialog(QDialog):
    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url
        self.setWindowTitle(TR.t("qr_title"))
        self.setFixedSize(340, 500)

        qr = qrcode.QRCode(border=2, box_size=8)
        qr.add_data(url)
        qr.make(fit=True)
        self._qr_image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        buf = io.BytesIO()
        self._qr_image.save(buf, format="PNG")
        self._qr_png_bytes = buf.getvalue()

        pixmap = QPixmap()
        pixmap.loadFromData(self._qr_png_bytes, "PNG")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title_lbl = QLabel(TR.t("qr_title"))
        title_lbl.setObjectName("DialogTitle")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)

        img_frame = QFrame()
        img_frame.setObjectName("QrImageFrame")
        img_lay = QVBoxLayout(img_frame)
        img_lay.setContentsMargins(16, 16, 16, 16)
        img_label = QLabel()
        img_label.setPixmap(pixmap)
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_lay.addWidget(img_label)
        layout.addWidget(img_frame)

        url_label = QLabel(url)
        url_label.setObjectName("UrlLabel")
        url_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        url_label.setWordWrap(True)
        layout.addWidget(url_label)

        hint = QLabel(TR.t("qr_hint"))
        hint.setObjectName("MutedSmall")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.copy_btn = QPushButton(TR.t("qr_copy_url"))
        self.copy_btn.setObjectName("QrActionBtn")
        self.copy_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        set_button_icon(self.copy_btn, "copy", size=14, role="text")
        self.copy_btn.clicked.connect(self._copy_url)
        actions.addWidget(self.copy_btn)

        self.save_btn = QPushButton(TR.t("qr_save_png"))
        self.save_btn.setObjectName("QrActionBtn")
        self.save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        set_button_icon(self.save_btn, "qr", size=14, role="text")
        self.save_btn.clicked.connect(self._save_png)
        actions.addWidget(self.save_btn)
        layout.addLayout(actions)

        close_btn = QPushButton(TR.t("close"))
        close_btn.setObjectName("DialogCancel")
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _copy_url(self):
        QApplication.clipboard().setText(self.url)
        original = self.copy_btn.text()
        self.copy_btn.setText(TR.t("qr_copied_btn"))
        QTimer.singleShot(1400, lambda: self.copy_btn.setText(original))

    def _save_png(self):
        path, _ = QFileDialog.getSaveFileName(
            self, TR.t("qr_save_png"), "ngrok-qr.png", "PNG Image (*.png)"
        )
        if not path:
            return
        try:
            with open(path, "wb") as f:
                f.write(self._qr_png_bytes)
            original = self.save_btn.text()
            self.save_btn.setText(TR.t("qr_copied_btn"))
            QTimer.singleShot(1400, lambda: self.save_btn.setText(original))
        except Exception as e:
            QMessageBox.warning(self, TR.t("qr_save_failed_title"), clean_error_text(str(e)))


# ---------------------------------------------------------- страница Requests
class RequestsPage(QWidget):
    def __init__(self, manager: NgrokManager):
        super().__init__()
        self.manager = manager
        v = QVBoxLayout(self)
        v.setContentsMargins(28, 20, 28, 20)
        v.setSpacing(4)

        header = QHBoxLayout()
        self.title = QLabel(TR.t("req_title"))
        self.title.setObjectName("PageTitle")
        header.addWidget(self.title)
        header.addStretch()
        self.clear_btn = QPushButton(TR.t("req_clear"))
        self.clear_btn.setObjectName("ToggleBtn")
        self.clear_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.clear_btn.clicked.connect(self._clear)
        header.addWidget(self.clear_btn)
        v.addLayout(header)

        self.sub = QLabel(TR.t("req_sub"))
        self.sub.setObjectName("SubHeader")
        v.addWidget(self.sub)
        v.addSpacing(14)

        self.table_header = QFrame()
        th = QHBoxLayout(self.table_header)
        th.setContentsMargins(4, 0, 4, 4)
        self.h_method = QLabel(TR.t("req_col_method"))
        self.h_method.setObjectName("TableHeader")
        self.h_method.setFixedWidth(70)
        self.h_path = QLabel(TR.t("req_col_path"))
        self.h_path.setObjectName("TableHeader")
        self.h_status = QLabel(TR.t("req_col_status"))
        self.h_status.setObjectName("TableHeader")
        self.h_status.setFixedWidth(70)
        self.h_time = QLabel(TR.t("req_col_time"))
        self.h_time.setObjectName("TableHeader")
        self.h_time.setFixedWidth(60)
        th.addWidget(self.h_method)
        th.addWidget(self.h_path, 1)
        th.addWidget(self.h_status)
        th.addWidget(self.h_time)
        v.addWidget(self.table_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.list_container = QWidget()
        self.list_container.setObjectName("ListContainer")
        self.list_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setSpacing(6)
        self.list_layout.addStretch()
        scroll.setWidget(self.list_container)
        v.addWidget(scroll, 1)

        self.empty_wrap = QWidget()
        ev = QVBoxLayout(self.empty_wrap)
        ev.setSpacing(4)
        self.empty_title = QLabel(TR.t("req_empty"))
        self.empty_title.setObjectName("EmptyTitle")
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_hint = QLabel(TR.t("req_empty_hint"))
        self.empty_hint.setObjectName("EmptyHint")
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ev.addWidget(self.empty_title)
        ev.addWidget(self.empty_hint)
        self.list_layout.insertWidget(0, self.empty_wrap)

        self._seen_ids = set()
        self._row_ids = deque()
        self.table_header.setVisible(False)
        self.empty_wrap.setVisible(True)

    def _clear(self):
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            w = item.widget()
            if w and w is not self.empty_wrap:
                w.deleteLater()
        self._seen_ids.clear()
        self._row_ids.clear()
        self.empty_wrap.setVisible(True)
        self.table_header.setVisible(False)

    def process_requests(self, reqs):
        # reqs: list or None. None indicates inspector/offline/error
        if reqs is None:
            # show offline message
            self.empty_title.setText(TR.t("req_offline"))
            self.empty_wrap.setVisible(True)
            self.table_header.setVisible(False)
            return
        # normal processing
        for r in reversed(reqs):
            rid = r.get("id") or str(r.get("start", ""))
            if rid in self._seen_ids:
                continue
            self._seen_ids.add(rid)
            self._add_row(r, rid)
        if self._seen_ids:
            self.empty_wrap.setVisible(False)
            self.table_header.setVisible(True)

    def _add_row(self, r: dict, rid: str):
        # enforce max rows
        # count excluding the stretching spacer (last item)
        current_rows = max(0, self.list_layout.count() - 1)
        while current_rows >= MAX_REQUEST_ROWS:
            # remove the last real row (at position count-2)
            item = self.list_layout.takeAt(self.list_layout.count() - 2)
            w = item.widget()
            if w and w is not self.empty_wrap:
                old_rid = w.property("request_id")
                if old_rid is not None:
                    self._seen_ids.discard(old_rid)
                    try:
                        self._row_ids.remove(old_rid)
                    except ValueError:
                        pass
                w.deleteLater()
            current_rows = max(0, self.list_layout.count() - 1)

        row = QFrame()
        row.setProperty("request_id", rid)
        row.setObjectName("Card")
        h = QHBoxLayout(row)
        h.setContentsMargins(10, 8, 10, 8)

        method = QLabel(r.get("method", "GET"))
        method.setObjectName("MethodBadge")
        method.setFixedWidth(60)
        h.addWidget(method)

        path = r.get("uri") or r.get("request", {}).get("uri", "/")
        path_lbl = QLabel(path)
        path_lbl.setObjectName("MutedSmall")
        h.addWidget(path_lbl, 1)

        status = r.get("response", {}).get("status_code", 0) if isinstance(r.get("response"), dict) else 0
        status_lbl = QLabel(str(status) if status else "…")
        status_lbl.setObjectName("StatusOk" if 200 <= status < 400 else "StatusErr")
        status_lbl.setFixedWidth(70)
        h.addWidget(status_lbl)

        time_lbl = QLabel(time.strftime("%H:%M:%S"))
        time_lbl.setObjectName("FaintSmall")
        time_lbl.setFixedWidth(60)
        h.addWidget(time_lbl)

        self.list_layout.insertWidget(0, row)
        self._row_ids.append(rid)

    def retranslate(self):
        self.title.setText(TR.t("req_title"))
        self.sub.setText(TR.t("req_sub"))
        self.clear_btn.setText(TR.t("req_clear"))
        self.h_method.setText(TR.t("req_col_method"))
        self.h_path.setText(TR.t("req_col_path"))
        self.h_status.setText(TR.t("req_col_status"))
        self.h_time.setText(TR.t("req_col_time"))
        self.empty_title.setText(TR.t("req_empty"))
        self.empty_hint.setText(TR.t("req_empty_hint"))


# ------------------------------------------------------------- страница Serve
class ServeRow(QFrame):
    def __init__(self, svc: SavedService, is_running: bool, on_launch, on_remove):
        super().__init__()
        self.svc = svc
        self.setObjectName("Card")
        h = QHBoxLayout(self)
        h.setContentsMargins(14, 10, 14, 10)

        icon = load_icon_label("serve", size=18, role="text")
        icon.setObjectName("GlobeAvatar")
        h.addWidget(icon)

        box = QVBoxLayout()
        box.setSpacing(0)
        name = QLabel(svc.name)
        name.setObjectName("RowLabel")
        addr = QLabel(f"localhost:{svc.port} · {svc.proto.upper()}")
        addr.setObjectName("MutedSmall")
        box.addWidget(name)
        box.addWidget(addr)
        h.addLayout(box)
        h.addStretch()

        if is_running:
            tag = QLabel(TR.t("serve_running"))
            tag.setObjectName("StatusOk")
            h.addWidget(tag)
        else:
            self.launch_btn = QPushButton(TR.t("serve_launch"))
            self.launch_btn.setObjectName("StartBtn")
            apply_neon_glow(self.launch_btn, blur=18)
            self.launch_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.launch_btn.clicked.connect(lambda: on_launch(svc))
            h.addWidget(self.launch_btn)

        remove_btn = AnimatedIconButton("remove")
        remove_btn.setToolTip(TR.t("remove_service"))
        remove_btn.clicked.connect(lambda: on_remove(svc))
        h.addWidget(remove_btn)

    def animate_entry(self):
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(220)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        self._entry_anim = anim
        anim.start()


class ServePage(QWidget):
    def __init__(self, on_launch):
        super().__init__()
        self.on_launch = on_launch
        self.services: list[SavedService] = []
        self.running_ports: set[int] = set()

        v = QVBoxLayout(self)
        v.setContentsMargins(28, 20, 28, 20)
        v.setSpacing(4)

        header = QHBoxLayout()
        self.title = QLabel(TR.t("serve_title"))
        self.title.setObjectName("PageTitle")
        header.addWidget(self.title)
        header.addStretch()
        self.add_btn = QPushButton(TR.t('serve_add'))
        self.add_btn.setObjectName("NewTunnelBtn")
        apply_neon_glow(self.add_btn, blur=22)
        set_button_icon(self.add_btn, "add", size=16, role="text")
        self.add_btn.setIconSize(QSize(16, 16))
        self.add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.add_btn.clicked.connect(self._add_service)
        header.addWidget(self.add_btn)
        v.addLayout(header)

        self.sub = QLabel(TR.t("serve_sub"))
        self.sub.setObjectName("SubHeader")
        v.addWidget(self.sub)
        v.addSpacing(14)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.list_container = QWidget()
        self.list_container.setObjectName("ListContainer")
        self.list_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setSpacing(10)
        self.list_layout.addStretch()
        scroll.setWidget(self.list_container)
        v.addWidget(scroll, 1)

        self.empty_wrap = QWidget()
        ev = QVBoxLayout(self.empty_wrap)
        self.empty_title = QLabel(TR.t("serve_empty"))
        self.empty_title.setObjectName("EmptyTitle")
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_hint = QLabel(TR.t("serve_empty_hint"))
        self.empty_hint.setObjectName("EmptyHint")
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ev.addWidget(self.empty_title)
        ev.addWidget(self.empty_hint)
        self.list_layout.insertWidget(0, self.empty_wrap)

        # немного стартовых пресетов, чтобы страница не была пустой
        for svc in (SavedService("Serve Web App", 3000, "http"),
                    SavedService("Serve API", 8000, "http")):
            self.services.append(svc)
        self._rebuild()

    def _add_service(self):
        dlg = NewTunnelDialog(self)
        dlg.setWindowTitle(TR.t("serve_add"))
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_data:
            port, proto, name = dlg.result_data
            self.services.append(SavedService(name or f"Serve {port}", port, proto))
            self._rebuild()

    def _remove_service(self, svc: SavedService):
        self.services = [s for s in self.services if s is not svc]
        self._rebuild()

    def mark_running(self, port: int, running: bool):
        if running:
            self.running_ports.add(port)
        else:
            self.running_ports.discard(port)
        self._rebuild()

    def _rebuild(self):
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            w = item.widget()
            if w and w is not self.empty_wrap:
                w.deleteLater()
        for svc in self.services:
            row = ServeRow(svc, svc.port in self.running_ports, self.on_launch, self._remove_service)
            self.list_layout.insertWidget(self.list_layout.count() - 1, row)
            row.animate_entry()
        self.empty_wrap.setVisible(len(self.services) == 0)

    def retranslate(self):
        self.title.setText(TR.t("serve_title"))
        self.sub.setText(TR.t("serve_sub"))
        self.add_btn.setText(f"⊕  {TR.t('serve_add')}")
        self.empty_title.setText(TR.t("serve_empty"))
        self.empty_hint.setText(TR.t("serve_empty_hint"))
        self._rebuild()


# ---------------------------------------------------------- страница Settings
class SettingsPage(QWidget):
    def __init__(self, manager: NgrokManager, controller: MainController, on_lang_toggle, on_theme_toggle, get_theme):
        super().__init__()
        self.manager = manager
        self.controller = controller
        self.on_lang_toggle = on_lang_toggle
        self.on_theme_toggle = on_theme_toggle
        self.get_theme = get_theme
        self._pending_token = None

        v = QVBoxLayout(self)
        v.setContentsMargins(28, 20, 28, 20)
        v.setSpacing(10)

        self.title = QLabel(TR.t("set_title"))
        self.title.setObjectName("PageTitle")
        v.addWidget(self.title)
        self.sub = QLabel(TR.t("set_sub"))
        self.sub.setObjectName("SubHeader")
        v.addWidget(self.sub)
        v.addSpacing(10)

        # --- General
        self.sec_general = self._section(TR.t("set_general"))
        v.addWidget(self.sec_general)
        gen_card = QFrame()
        gen_card.setObjectName("SectionCard")
        gc = QVBoxLayout(gen_card)
        gc.setContentsMargins(14, 12, 14, 12)
        gc.setSpacing(12)

        row_lang = QHBoxLayout()
        self.lang_label = QLabel(TR.t("set_language"))
        self.lang_label.setObjectName("RowLabel")
        row_lang.addWidget(self.lang_label)
        row_lang.addStretch()
        self.lang_btn = QPushButton(TR.t('set_language'))
        set_button_icon(self.lang_btn, "language", size=16, role="muted")
        self.lang_btn.setIconSize(QSize(16, 16))
        self.lang_btn.setObjectName("ToggleBtn")
        self.lang_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.lang_btn.clicked.connect(self.on_lang_toggle)
        row_lang.addWidget(self.lang_btn)
        gc.addLayout(row_lang)
 
        row_theme = QHBoxLayout()
        self.theme_label = QLabel(TR.t("set_theme"))
        self.theme_label.setObjectName("RowLabel")
        row_theme.addWidget(self.theme_label)
        row_theme.addStretch()
        self.theme_btn = QPushButton(TR.t('light_mode') if self.get_theme() == 'dark' else TR.t('dark_mode'))
        set_button_icon(self.theme_btn, "theme", size=16, role="muted")
        self.theme_btn.setIconSize(QSize(16, 16))
        self.theme_btn.setObjectName("ToggleBtn")
        self.theme_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.theme_btn.clicked.connect(self.on_theme_toggle)
        row_theme.addWidget(self.theme_btn)
        gc.addLayout(row_theme)

        v.addWidget(gen_card)

        # --- ngrok
        self.sec_ngrok = self._section(TR.t("set_ngrok"))
        v.addWidget(self.sec_ngrok)
        ngrok_card = QFrame()
        ngrok_card.setObjectName("SectionCard")
        nc = QVBoxLayout(ngrok_card)
        nc.setContentsMargins(14, 12, 14, 12)
        nc.setSpacing(8)
        self.token_label = QLabel(TR.t("set_authtoken"))
        self.token_label.setObjectName("RowLabel")
        nc.addWidget(self.token_label)
        row_token = QHBoxLayout()
        self.token_edit = QLineEdit()
        self.token_edit.setPlaceholderText(TR.t("set_authtoken_ph"))
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        row_token.addWidget(self.token_edit)
        self.save_btn = QPushButton(TR.t("set_save"))
        self.save_btn.setObjectName("PrimaryBtn")
        apply_neon_glow(self.save_btn, blur=22)
        self.save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.save_btn.clicked.connect(self._save_token)
        row_token.addWidget(self.save_btn)
        nc.addLayout(row_token)
        self.saved_lbl = QLabel("")
        self.saved_lbl.setObjectName("StatusOk")
        nc.addWidget(self.saved_lbl)
        v.addWidget(ngrok_card)

        # --- Profile
        self.sec_profile = self._section(TR.t("set_profile"))
        v.addWidget(self.sec_profile)
        prof_card = QFrame()
        prof_card.setObjectName("SectionCard")
        pc = QVBoxLayout(prof_card)
        pc.setContentsMargins(14, 12, 14, 12)
        pc.setSpacing(8)

        row_org = QHBoxLayout()
        self.org_label = QLabel(TR.t("set_org"))
        self.org_label.setObjectName("RowLabel")
        row_org.addWidget(self.org_label)
        row_org.addStretch()
        org_val = QLabel(ORG_NAME)
        org_val.setObjectName("MutedSmall")
        row_org.addWidget(org_val)
        pc.addLayout(row_org)

        row_plan = QHBoxLayout()
        self.plan_label = QLabel(TR.t("set_plan"))
        self.plan_label.setObjectName("RowLabel")
        row_plan.addWidget(self.plan_label)
        row_plan.addStretch()
        self.plan_val = QLabel(TR.t("set_plan_value"))
        self.plan_val.setObjectName("MutedSmall")
        row_plan.addWidget(self.plan_val)
        pc.addLayout(row_plan)

        v.addWidget(prof_card)

        # --- About
        self.sec_about = self._section(TR.t("set_about"))
        v.addWidget(self.sec_about)
        about_card = QFrame()
        about_card.setObjectName("SectionCard")
        ac = QVBoxLayout(about_card)
        ac.setContentsMargins(14, 12, 14, 12)
        ac.setSpacing(6)
        row_ver = QHBoxLayout()
        self.ver_label = QLabel(TR.t("set_version"))
        self.ver_label.setObjectName("RowLabel")
        row_ver.addWidget(self.ver_label)
        row_ver.addStretch()
        ver_val = QLabel("3.0.0 PRO")
        ver_val.setObjectName("MutedSmall")
        row_ver.addWidget(ver_val)
        ac.addLayout(row_ver)
        self.status_lbl = QLabel(f"🟢  {TR.t('set_status')}")
        self.status_lbl.setObjectName("MutedSmall")
        ac.addWidget(self.status_lbl)
        v.addWidget(about_card)

        v.addStretch()

        # connect validation signal early to update UI after async save
        self.controller.signals.authtoken_validated.connect(self._on_token_validated)

    def _section(self, text) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("SectionLabel")
        return lbl

    def _save_token(self):
        token = self.token_edit.text().strip()
        self._pending_token = token
        self.save_btn.setEnabled(False)
        self.saved_lbl.setText("Validating...")
        self.controller.validate_authtoken_async(token)

    def _on_token_validated(self, token: str, success: bool, error: object):
        if token != self._pending_token:
            return

        self.save_btn.setEnabled(True)
        if success:
            if keyring is not None:
                try:
                    if token:
                        keyring.set_password("ngrok_gui_pro", "authtoken", token)
                        self.saved_lbl.setText(TR.t("set_saved"))
                    else:
                        try:
                            keyring.delete_password("ngrok_gui_pro", "authtoken")
                        except Exception:
                            pass
                        self.saved_lbl.setText("")
                except Exception:
                    logger.exception("Keyring operation failed")
                    QMessageBox.warning(self, TR.t("error"), TR.t("error") + ": failed to persist authtoken to system keyring")
                    self.saved_lbl.setText(TR.t("set_saved"))
            else:
                QMessageBox.information(self, "Info", "keyring not available — token stored only in-session")
                self.saved_lbl.setText(TR.t("set_saved") if token else "")

            try:
                self.token_edit.clear()
            except Exception:
                pass
        else:
            logger.exception("Auth token validation failed: %s", error)
            self.saved_lbl.setText("")
            QMessageBox.critical(self, TR.t("error"), str(error) or TR.t("tunnel_error"))

    def retranslate(self):
        self.title.setText(TR.t("set_title"))
        self.sub.setText(TR.t("set_sub"))
        self.sec_general.setText(TR.t("set_general"))
        self.lang_label.setText(TR.t("set_language"))
        self.lang_btn.setText(TR.t('set_language'))
        self.theme_label.setText(TR.t("set_theme"))
        self.theme_btn.setText(TR.t('light_mode') if self.get_theme() == 'dark' else TR.t('dark_mode'))
        self.sec_ngrok.setText(TR.t("set_ngrok"))
        self.token_label.setText(TR.t("set_authtoken"))
        self.token_edit.setPlaceholderText(TR.t("set_authtoken_ph"))
        self.save_btn.setText(TR.t("set_save"))
        self.sec_profile.setText(TR.t("set_profile"))
        self.org_label.setText(TR.t("set_org"))
        self.plan_label.setText(TR.t("set_plan"))
        self.plan_val.setText(TR.t("set_plan_value"))
        self.sec_about.setText(TR.t("set_about"))
        self.ver_label.setText(TR.t("set_version"))
        self.status_lbl.setText(f"🟢  {TR.t('set_status')}")


# ============================================================== ГЛАВНОЕ ОКНО
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.resize(960, 660)

        self.theme = "dark"
        self.manager = NgrokManager()
        self.controller = MainController(self.manager)
        self.cards: dict[str, TunnelCard] = {}
        self.inactive_infos: list[TunnelInfo] = []
        self._drag_pos = None
        self._inactive_expanded = False

        self._build()
        self.apply_theme()

        self.controller.signals.tunnel_opened.connect(self._on_tunnel_opened)
        self.controller.signals.tunnel_closed.connect(self._on_tunnel_closed)
        self.controller.signals.conn_count.connect(self._on_conn_count)
        self.controller.signals.requests_fetched.connect(self.requests_page.process_requests)

        # try to load authtoken from system keyring (optional)
        if keyring is not None:
            try:
                saved = keyring.get_password("ngrok_gui_pro", "authtoken")
                if saved:
                    try:
                        self.manager.set_authtoken(saved)
                        # update settings UI to indicate saved
                        try:
                            self.settings_page.saved_lbl.setText(TR.t("set_saved"))
                            self.settings_page.token_edit.clear()
                        except Exception:
                            pass
                        logger.info("Loaded authtoken from keyring")
                    except Exception:
                        logger.exception("Failed to apply authtoken from keyring")
            except Exception:
                logger.exception("Failed to read authtoken from keyring")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(CONN_POLL_INTERVAL_MS)

        self.req_timer = QTimer(self)
        self.req_timer.timeout.connect(self._poll_requests)
        self.req_timer.start(REQUEST_POLL_INTERVAL_MS)

        self.performance = PerformanceOptimizer(self.timer, self.req_timer)
        self.performance.set_page(0)

    # ---------------- palette
    def apply_theme(self):
        self.setStyleSheet(build_stylesheet(THEMES[self.theme]))
        refresh_icon_theme(THEMES[self.theme])
        refresh_glow_theme(THEMES[self.theme])
        self._repolish_all()

    def _repolish_all(self):
        """Belt-and-braces: force every descendant widget to re-evaluate its
        stylesheet. Qt normally propagates a stylesheet change to children
        automatically, but a handful of widgets here use dynamic QSS
        properties (e.g. ProtocolCard's [selected="true"]); those only
        repaint reliably after an explicit unpolish/polish, so we do it for
        the whole tree on every theme switch to avoid any stale/invisible
        text or icons."""
        for w in self.findChildren(QWidget):
            try:
                w.style().unpolish(w)
                w.style().polish(w)
            except RuntimeError:
                continue

    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        self.apply_theme()
        self.theme_nav_item.setText(TR.t('light_mode') if self.theme == 'dark' else TR.t('dark_mode'))

    def toggle_lang(self):
        TR.toggle()
        self._retranslate_all()

    def _retranslate_all(self):
        for item in self.nav_items:
            item.retranslate()
        self.theme_nav_item.setText(TR.t('light_mode') if self.theme == 'dark' else TR.t('dark_mode'))
        self.title.setText(TR.t("page_tunnels_title"))
        self.new_btn.setText(f"⊕  {TR.t('new_tunnel')}")
        self._refresh_counters()
        arrow_text = TR.t("inactive", len(self.inactive_infos), self._inactive_expanded)
        self.inactive_toggle.setText(arrow_text)
        for card in self.cards.values():
            card.retranslate()
        self._rebuild_inactive()
        self.requests_page.retranslate()
        self.serve_page.retranslate()
        self.settings_page.retranslate()

    # ---------------- layout
    def _build(self):
        root = QFrame()
        root.setObjectName("AppRoot")
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(TrafficLights(self))

        header = QFrame()
        header.setObjectName("AppHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 18, 24, 18)
        header_layout.setSpacing(16)
        self.header_title = QLabel(TR.t("page_tunnels_title"))
        self.header_title.setObjectName("HeaderTitle")
        header_layout.addWidget(self.header_title)
        header_layout.addStretch()
        self.header_status = QLabel(TR.t("set_status"))
        self.header_status.setObjectName("HeaderStatus")
        header_layout.addWidget(self.header_status)
        outer.addWidget(header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        outer.addLayout(body)

        body.addWidget(self._build_sidebar())

        self.stack = AnimatedStackedWidget()
        self.tunnels_page = self._build_tunnels_page()
        self.requests_page = RequestsPage(self.manager)
        self.serve_page = ServePage(self._launch_from_serve)
        self.settings_page = SettingsPage(self.manager, self.controller, self.toggle_lang, self.toggle_theme, lambda: self.theme)

        self.stack.addWidget(self.tunnels_page)
        self.stack.addWidget(self.requests_page)
        self.stack.addWidget(self.serve_page)
        self.stack.addWidget(self.settings_page)
        body.addWidget(self.stack, 1)

        status_bar = QFrame()
        status_bar.setObjectName("StatusBar")
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(24, 12, 24, 12)
        status_layout.setSpacing(8)
        self.global_status = QLabel(TR.t("set_status"))
        self.global_status.setObjectName("StatusText")
        status_layout.addWidget(self.global_status)
        status_layout.addStretch()
        self.status_badge = QLabel("Ready")
        self.status_badge.setObjectName("StatusBadge")
        status_layout.addWidget(self.status_badge)
        outer.addWidget(status_bar)

    # ---------------- уведомления (toast)
    def show_notification(self, title: str, message: str, kind: str = "error"):
        if not hasattr(self, "_toasts"):
            self._toasts = []
        toast = Toast(self.centralWidget(), kind, title, message)
        toast.destroyed.connect(lambda *_: self._on_toast_destroyed(toast))
        self._toasts.append(toast)
        toast.show_animated()
        self._reflow_toasts()

    def _on_toast_destroyed(self, toast):
        try:
            self._toasts.remove(toast)
        except (ValueError, AttributeError):
            pass
        try:
            self._reflow_toasts()
        except RuntimeError:
            # MainWindow itself is being torn down (app shutdown) — nothing to do
            pass

    def _reflow_toasts(self):
        if not hasattr(self, "_toasts"):
            return
        try:
            central = self.centralWidget()
        except RuntimeError:
            return
        if not central:
            return
        margin = 20
        gap = 10
        y = 64
        cw = central.width()
        for toast in self._toasts:
            try:
                toast.adjustSize()
                toast.move(cw - toast.width() - margin, y)
                toast.raise_()
                y += toast.height() + gap
            except RuntimeError:
                continue

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow_toasts()

    def _select_page(self, index: int):
        self.stack.fade_to_index(index)
        for i, item in enumerate(self.nav_items):
            item.set_selected(i == index)
        page_keys = ["nav_tunnels", "nav_requests", "nav_serve", "nav_settings"]
        self.header_title.setText(TR.t(page_keys[index]))
        self.performance.set_page(index)

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(200)
        v = QVBoxLayout(sidebar)
        v.setContentsMargins(12, 8, 12, 0)
        v.setSpacing(2)

        self.nav_items = [
            NavItem("tunnel", "nav_tunnels", selected=True, on_click=lambda: self._select_page(0)),
            NavItem("requests", "nav_requests", on_click=lambda: self._select_page(1)),
            NavItem("serve", "nav_serve", on_click=lambda: self._select_page(2)),
            NavItem("settings", "nav_settings", on_click=lambda: self._select_page(3)),
        ]
        for item in self.nav_items:
            v.addWidget(item)
        v.addStretch()

        self.active_count_lbl = QLabel(f"{TR.t('active_tunnels')}     0/4")
        self.active_count_lbl.setObjectName("MutedSmall")
        v.addWidget(self.active_count_lbl)

        self.theme_nav_item = QPushButton(TR.t('light_mode'))
        set_button_icon(self.theme_nav_item, "theme", size=18, role="muted")
        self.theme_nav_item.setIconSize(QSize(18, 18))
        self.theme_nav_item.setObjectName("NavItem")
        self.theme_nav_item.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.theme_nav_item.setFixedHeight(34)
        self.theme_nav_item.clicked.connect(self.toggle_theme)
        v.addWidget(self.theme_nav_item)

        lang_item = QPushButton(TR.t('set_language'))
        set_button_icon(lang_item, "language", size=18, role="muted")
        lang_item.setIconSize(QSize(18, 18))
        lang_item.setObjectName("NavItem")
        lang_item.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        lang_item.setFixedHeight(34)
        lang_item.clicked.connect(self.toggle_lang)
        v.addWidget(lang_item)

        user_row = QFrame()
        user_row.setObjectName("UserRow")
        user_row.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        ur = QHBoxLayout(user_row)
        ur.setContentsMargins(6, 10, 6, 10)
        avatar = QLabel("G")
        avatar.setObjectName("Avatar")
        avatar.setFixedSize(30, 30)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ur.addWidget(avatar)

        name_box = QVBoxLayout()
        name_box.setSpacing(0)
        n = QLabel(ORG_NAME)
        n.setObjectName("UserName")
        n.setWordWrap(True)
        n.setFixedWidth(110)
        e = QLabel(ORG_TAG)
        e.setObjectName("UserEmail")
        name_box.addWidget(n)
        name_box.addWidget(e)
        ur.addLayout(name_box)
        ur.addStretch()
        chevron = QLabel("›")
        chevron.setObjectName("MutedSmall")
        ur.addWidget(chevron)
        v.addWidget(user_row)

        return sidebar

    def _build_tunnels_page(self) -> QWidget:
        main = QWidget()
        v = QVBoxLayout(main)
        v.setContentsMargins(28, 20, 28, 20)
        v.setSpacing(4)

        header = QHBoxLayout()
        self.title = QLabel(TR.t("page_tunnels_title"))
        self.title.setObjectName("PageTitle")
        header.addWidget(self.title)
        header.addStretch()
        self.new_btn = QPushButton(f"⊕  {TR.t('new_tunnel')}")
        self.new_btn.setObjectName("NewTunnelBtn")
        apply_neon_glow(self.new_btn, blur=24)
        self.new_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.new_btn.clicked.connect(self._new_tunnel)
        header.addWidget(self.new_btn)
        v.addLayout(header)

        sub_row = QHBoxLayout()
        self.sub_label = QLabel(TR.t("active_tunnels_sub", 0))
        self.sub_label.setObjectName("SubHeader")
        sub_row.addWidget(self.sub_label)
        self.mini_progress = QProgressBar()
        self.mini_progress.setFixedWidth(90)
        self.mini_progress.setRange(0, 4)
        self.mini_progress.setValue(0)
        self.mini_progress.setTextVisible(False)
        sub_row.addWidget(self.mini_progress)
        self.mini_progress_lbl = QLabel("0/4")
        self.mini_progress_lbl.setObjectName("SubHeader")
        sub_row.addWidget(self.mini_progress_lbl)
        sub_row.addStretch()
        v.addLayout(sub_row)
        v.addSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.list_container = QWidget()
        self.list_container.setObjectName("ListContainer")
        self.list_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setSpacing(14)
        self.list_layout.addStretch()
        scroll.setWidget(self.list_container)
        v.addWidget(scroll, 1)

        self.inactive_toggle = QPushButton(TR.t("inactive", 0, False))
        self.inactive_toggle.setObjectName("InactiveHeader")
        self.inactive_toggle.setFlat(True)
        self.inactive_toggle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.inactive_toggle.clicked.connect(self._toggle_inactive)
        v.addWidget(self.inactive_toggle)

        self.inactive_container = QWidget()
        self.inactive_layout = QVBoxLayout(self.inactive_container)
        self.inactive_layout.setSpacing(10)
        self.inactive_container.setVisible(False)
        v.addWidget(self.inactive_container)

        return main

    # ---------------- дрэг окна за тайтлбар
    def mousePressEvent(self, event):
        if event.position().y() < 40:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            minimized = self.windowState() & Qt.WindowState.WindowMinimized
            self.performance.set_window_active(not minimized)
        super().changeEvent(event)

    # ---------------- логика туннелей
    def _new_tunnel(self):
        if len(self.cards) >= MAX_TUNNELS_SLOTS:
            QMessageBox.warning(self, TR.t("error"), TR.t("max_tunnels_reached"))
            return
        dlg = NewTunnelDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_data:
            port, proto, name = dlg.result_data
            valid, message = self._can_open_tunnel(port)
            if not valid:
                QMessageBox.warning(self, TR.t("error"), message)
                return
            self.controller.open_tunnel_async(port, proto=proto, name=name or None)

    def _launch_from_serve(self, svc: SavedService):
        valid, message = self._can_open_tunnel(svc.port)
        if not valid:
            QMessageBox.warning(self, TR.t("error"), message)
            return
        self.controller.open_tunnel_async(svc.port, proto=svc.proto, name=svc.name)

    def _can_open_tunnel(self, port: int) -> tuple[bool, str]:
        duplicates = [info for info in list(self.cards.values()) if info.info.local_addr.endswith(f":{port}")]
        if duplicates:
            return False, TR.t("error_duplicate_port", port)
        inactive_dup = [info for info in self.inactive_infos if info.local_addr.endswith(f":{port}")]
        if inactive_dup:
            return False, TR.t("error_closed_tunnel_exists", port)
        return True, ""

    def _add_card(self, info: TunnelInfo):
        card = TunnelCard(info, on_stop=self._stop_tunnel, on_start=self._restart_tunnel, on_qr=self._show_qr, on_toast=self.show_notification)
        self.list_layout.insertWidget(self.list_layout.count() - 1, card)
        card.animate_entry()
        self.cards[info.public_url] = card
        self._refresh_counters()

    def _stop_tunnel(self, public_url: str):
        self.controller.close_tunnel_async(public_url)

    def _restart_tunnel(self, public_url: str):
        old = next((i for i in self.inactive_infos if i.public_url == public_url), None)
        if not old:
            return
        self.controller.restart_tunnel_async(old)

    def _show_qr(self, public_url: str):
        QRDialog(public_url, self).exec()

    def _toggle_inactive(self):
        self._inactive_expanded = not self._inactive_expanded
        self.inactive_container.setVisible(self._inactive_expanded)
        self.inactive_toggle.setText(TR.t("inactive", len(self.inactive_infos), self._inactive_expanded))

    def _rebuild_inactive(self):
        while self.inactive_layout.count():
            item = self.inactive_layout.takeAt(0)
            w = item.widget()
            if w:
                # ensure proper disposal
                try:
                    w.dispose()
                except Exception:
                    pass
        for info in self.inactive_infos:
            card = TunnelCard(info, on_stop=self._stop_tunnel, on_start=self._restart_tunnel, on_qr=self._show_qr, on_toast=self.show_notification)
            self.inactive_layout.addWidget(card)
        self.inactive_toggle.setText(TR.t("inactive", len(self.inactive_infos), self._inactive_expanded))

    def _refresh_counters(self):
        n = len(self.cards)
        total_slots = max(MAX_TUNNELS_SLOTS, n)
        self.active_count_lbl.setText(f"{TR.t('active_tunnels')}     {n}/{total_slots}")
        self.sub_label.setText(TR.t("active_tunnels_sub", n))
        self.mini_progress.setRange(0, total_slots)
        self.mini_progress.setValue(n)
        self.mini_progress_lbl.setText(f"{n}/{total_slots}")
        self.new_btn.setEnabled(n < MAX_TUNNELS_SLOTS)
        self.new_btn.setToolTip(TR.t("max_tunnels_reached") if n >= MAX_TUNNELS_SLOTS else TR.t("new_tunnel"))

    def _set_status(self, text: str):
        if hasattr(self, 'header_status'):
            self.header_status.setText(text)
        if hasattr(self, 'global_status'):
            self.global_status.setText(text)

    def _tick(self):
        # запускаем асинхронные задачи для получения количества подключений
        for url in list(self.cards.keys()):
            self.controller.fetch_connection_count_async(url)

    def _on_tunnel_opened(self, info, err):
        if err:
            self._set_status(TR.t("tunnel_error"))
            if is_ngrok_billing_error(err):
                self.show_notification(TR.t("notice_billing_title"), TR.t("notice_billing_msg"), kind="error")
            else:
                self.show_notification(TR.t("notice_generic_error_title"), clean_error_text(err), kind="error")
            return
        if not info:
            return
        self._set_status(f"Tunnel opened: {info.public_url}")
        # remove matching inactive info if any
        try:
            match = next((i for i in self.inactive_infos if i.local_addr == info.local_addr), None)
            if match:
                try:
                    self.inactive_infos.remove(match)
                except ValueError:
                    pass
        except Exception:
            pass
        self._add_card(info)
        try:
            port = int(info.local_addr.split(":")[1])
            self.serve_page.mark_running(port, True)
        except Exception:
            pass

    def _on_tunnel_closed(self, public_url, err):
        if err:
            self._set_status(TR.t("tunnel_error"))
            if is_ngrok_billing_error(err):
                self.show_notification(TR.t("notice_billing_title"), TR.t("notice_billing_msg"), kind="error")
            else:
                self.show_notification(TR.t("notice_generic_error_title"), clean_error_text(err), kind="error")
            return
        card = self.cards.pop(public_url, None)
        self._set_status("Tunnel closed")
        if card:
            card.info.active = False
            self.inactive_infos.append(card.info)
            try:
                self.list_layout.removeWidget(card)
            except Exception:
                pass
            try:
                card.dispose()
            except Exception:
                pass
            try:
                port = int(card.info.local_addr.split(":")[1])
                self.serve_page.mark_running(port, False)
            except Exception:
                pass
        self._rebuild_inactive()
        self._refresh_counters()

    def _on_conn_count(self, public_url, count):
        card = self.cards.get(public_url)
        if card:
            card.info.connections = count
            card.refresh()

    def _poll_requests(self):
        self.controller.fetch_http_requests_async()

    def closeEvent(self, event):
        try:
            self.timer.stop()
            self.req_timer.stop()
        except Exception:
            pass
        try:
            if hasattr(self, 'controller'):
                try:
                    self.controller.executor.submit(self.manager.close_all)
                except Exception:
                    # fallback if executor is unavailable
                    try:
                        self.manager.close_all()
                    except Exception:
                        pass
                self.controller.shutdown(wait=False)
        except Exception:
            pass
        event.accept()


def _pick_nice_font() -> QFont:
    """Pick the nicest-looking font actually installed on this machine,
    falling back gracefully down a chain of good UI fonts to the Qt
    platform default so the app never ends up on a jarring fallback."""
    preferred = ["Poppins", "Manrope", "Inter", "SF Pro Display", "Segoe UI Variable", "Segoe UI"]
    available = set(QFontDatabase.families())
    for name in preferred:
        if name in available:
            font = QFont(name, 11)
            return font
    return QFont()  # platform default (still fine — QSS stack covers the rest)


def main():
    app = QApplication(sys.argv)
    app.setFont(_pick_nice_font())
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()