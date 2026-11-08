"""Shared UI translations for CyberHub Manager."""

from __future__ import annotations

from typing import Final, Literal
from .ui_copy import ENGLISH, ENGLISH_SINGULAR

Language = Literal["vi", "en"]

DEFAULT_LANGUAGE: Final[Language] = "vi"
SUPPORTED_LANGUAGES: Final[tuple[Language, ...]] = ("vi", "en")

_TRANSLATIONS: Final[dict[str, dict[Language, str]]] = {
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
