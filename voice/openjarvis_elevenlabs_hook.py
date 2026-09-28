"""``openjarvis.speech`` yuklanganda ElevenLabs backend'ini ro'yxatga oladi.

``openjarvis_elevenlabs.pth`` bu modulni Python ishga tushishida import qiladi.
Modul yengil: OpenJarvis'ni o'zi import qilmaydi, faqat ``openjarvis.speech``
ni kuzatadi. OpenJarvis ovoz backend'larini aynan shu paket orqali yuklaydi,
shuning uchun ElevenLabs ham o'sha paytda qo'shiladi.
"""

import importlib.abc
import importlib.util
import logging
import sys

_TARGET = "openjarvis.speech"


class _RegisterAfterSpeechImport(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname != _TARGET:
            return None
        # Bir martalik: o'zimizni olib tashlab, asl spec'ni topamiz
        sys.meta_path.remove(self)
        spec = importlib.util.find_spec(fullname)
        if spec is None or spec.loader is None:
            return spec
        original_exec = spec.loader.exec_module

        def exec_module(module):
            original_exec(module)
            try:
                import openjarvis_elevenlabs

                openjarvis_elevenlabs.register()
            except Exception:
                logging.getLogger(__name__).warning(
                    "ElevenLabs backend'ini ulab bo'lmadi", exc_info=True
                )

        spec.loader.exec_module = exec_module
        return spec


if _TARGET not in sys.modules and not any(
    isinstance(f, _RegisterAfterSpeechImport) for f in sys.meta_path
):
    sys.meta_path.insert(0, _RegisterAfterSpeechImport())
