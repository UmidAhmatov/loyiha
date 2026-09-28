"""OpenJarvis qo'shimcha modullarini kerakli paket yuklanganda ulaydi.

Har bir modul uchun ``.venv`` ga bitta ``.pth`` fayl yoziladi, masalan::

    import openjarvis_addon_hook; openjarvis_addon_hook.after_import("openjarvis.speech", "openjarvis_elevenlabs")

Python ishga tushganda bu qator faqat kuzatuvchini o'rnatadi — OpenJarvis'ni
import qilmaydi. ``openjarvis.speech`` (yoki boshqa maqsad paket) yuklanib
bo'lgach, qo'shimcha modulning ``register()`` funksiyasi chaqiriladi.
OpenJarvis o'z backend va tool'larini aynan shu paketlar orqali yuklaydi.
"""

import importlib
import importlib.abc
import importlib.util
import logging
import sys


def _register(addon):
    try:
        importlib.import_module(addon).register()
    except Exception:
        logging.getLogger(__name__).warning(
            "%s modulini ulab bo'lmadi", addon, exc_info=True
        )


class _AfterImport(importlib.abc.MetaPathFinder):
    def __init__(self, target, addon):
        self.key = (target, addon)

    def find_spec(self, fullname, path, target=None):
        if fullname != self.key[0]:
            return None
        # Bir martalik: o'zimizni olib tashlab, asl spec'ni topamiz
        sys.meta_path.remove(self)
        spec = importlib.util.find_spec(fullname)
        if spec is None or spec.loader is None:
            return spec
        original_exec = spec.loader.exec_module
        addon = self.key[1]

        def exec_module(module):
            original_exec(module)
            _register(addon)

        spec.loader.exec_module = exec_module
        return spec


def after_import(target, addon):
    """``target`` paket yuklangandan keyin ``addon.register()`` ni chaqirish."""
    if target in sys.modules:
        _register(addon)
        return
    if any(getattr(f, "key", None) == (target, addon) for f in sys.meta_path):
        return
    sys.meta_path.insert(0, _AfterImport(target, addon))
