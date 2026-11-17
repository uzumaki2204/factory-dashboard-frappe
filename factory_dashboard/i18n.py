import json
from functools import lru_cache
from pathlib import Path

import frappe


@lru_cache(maxsize=1)
def catalog():
    return json.loads((Path(__file__).parent / "i18n.json").read_text(encoding="utf-8"))


def message(key, lang=None, **values):
    if lang is None:
        lang = getattr(frappe.local, "lang", "vi")
    entries = catalog()
    template = entries.get((lang or "vi").split("-")[0], entries["vi"]).get(key, entries["vi"]["error.invalid_input"])
    return template.format(**values)


import frappe
