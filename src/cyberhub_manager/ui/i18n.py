"""Shared UI translations for CyberHub Manager."""

from __future__ import annotations

from typing import Final, Literal
from .ui_copy import ENGLISH, ENGLISH_SINGULAR

Language = Literal["vi", "en"]

DEFAULT_LANGUAGE: Final[Language] = "vi"
SUPPORTED_LANGUAGES: Final[tuple[Language, ...]] = ("vi", "en")

_TRANSLATIONS: Final[dict[str, dict[Language, str]]] = {
    "nav.employees": {"vi": "Nhân viên", "en": "Employees"},
    "nav.promotions": {"vi": "Khuyến mãi", "en": "Promotions"},
    "nav.stores": {"vi": "Cơ sở", "en": "Stores"},
    "app.name": {
        "vi": "CyberHub Manager",
        "en": "CyberHub Manager",
    },
    "nav.dashboard": {
        "vi": "Tổng quan",
        "en": "Dashboard",
    },
    "nav.customers": {
        "vi": "Khách hàng",
        "en": "Customers",
    },
    "nav.machines": {
        "vi": "Quản lý máy",
        "en": "Machine management",
    },
    "nav.invoices": {
        "vi": "Hóa đơn",
        "en": "Invoices",
    },
    "nav.reports": {
        "vi": "Doanh thu",
        "en": "Revenue",
    },
    "header.search_placeholder": {
        "vi": "Tìm kiếm máy, khách hàng…",
        "en": "Search machines or customers…",
    },
    "header.logout": {
        "vi": "Đăng xuất",
        "en": "Sign out",
    },
    "role.admin": {
        "vi": "Quản trị viên",
        "en": "Administrator",
    },
    "role.manager": {
        "vi": "Quản lý",
        "en": "Manager",
    },
    "role.staff": {
        "vi": "Nhân viên",
        "en": "Staff",
    },
    "status.ready": {
        "vi": "Hệ thống sẵn sàng",
        "en": "System ready",
    },
    "view.placeholder_title": {
        "vi": "Chức năng đang được hoàn thiện",
        "en": "Feature under construction",
    },
    "view.placeholder_message": {
        "vi": "Màn hình này sẽ được kết nối ở task UI tương ứng.",
        "en": "This screen will be connected by its corresponding UI task.",
    },
    # HA-11 — màn đăng nhập
    "login.portal": {
        "vi": "CỔNG VẬN HÀNH NHÂN VIÊN",
        "en": "STAFF OPERATIONS PORTAL",
    },
    "login.title": {
        "vi": "Đăng nhập",
        "en": "Sign in",
    },
    "login.subtitle": {
        "vi": "Đăng nhập để tiếp tục quản lý cửa hàng",
        "en": "Sign in to continue managing your store",
    },
    "login.username": {
        "vi": "Tên đăng nhập",
        "en": "Username",
    },
    "login.username_placeholder": {
        "vi": "Nhập tên đăng nhập",
        "en": "Enter your username",
    },
    "login.password": {
        "vi": "Mật khẩu",
        "en": "Password",
    },
    "login.password_placeholder": {
        "vi": "Nhập mật khẩu",
        "en": "Enter your password",
    },
    "login.submit": {
        "vi": "Đăng nhập  →",
        "en": "Sign in  →",
    },
    "login.enter_hint": {
        "vi": "Nhấn Enter ↵ để đăng nhập",
        "en": "Press Enter ↵ to sign in",
    },
    "login.brand_tag": {
        "vi": "PHẦN MỀM QUẢN LÝ PHÒNG MÁY",
        "en": "INTERNET CAFE MANAGEMENT",
    },
    "login.brand_tagline": {
        "vi": "Hệ thống quản lý phòng máy chuyên nghiệp",
        "en": "Professional internet cafe management system",
    },
    "login.feature_sessions": {
        "vi": "Kiểm soát phiên thời gian thực",
        "en": "Real-time session control",
    },
    "login.feature_billing": {
        "vi": "Biểu phí & nạp tiền chuẩn xác",
        "en": "Accurate billing & top-ups",
    },
    "login.feature_roles": {
        "vi": "Phân quyền theo vai trò",
        "en": "Role-based access",
    },
    "login.feature_reports": {
        "vi": "Hóa đơn & doanh thu theo ngày",
        "en": "Daily invoices & revenue",
    },
    "login.copyright": {
        "vi": "© 2026 CyberHub Manager",
        "en": "© 2026 CyberHub Manager",
    },
}


def normalize_language(language: str | None) -> Language:
    """Return a supported language, falling back to Vietnamese."""

    if language == "en":
        return "en"
    return DEFAULT_LANGUAGE


def translate(key: str, language: str | None = None) -> str:
    """Translate a known UI key.

    Unknown keys are returned unchanged so a missing translation remains
    visible during development instead of crashing the application.
    """

    normalized = normalize_language(language)
    values = _TRANSLATIONS.get(key)
    if values is None:
        return key
    return values[normalized]


class UIStrings:
    """Translate explicit display templates before interpolating DTO values."""

    def __init__(self, language: str | None = None) -> None:
        self.language = normalize_language(language)

    def __call__(self, source: str, **values: object) -> str:
        template = ENGLISH.get(source, source) if self.language == "en" else source
        if self.language == "en" and source in ENGLISH_SINGULAR:
            field, singular = ENGLISH_SINGULAR[source]
            if str(values.get(field)) == "1":
                template = singular
        return template.format(**values) if values else template
