"""
Pluggable OCR Engine (PaddleOCR > EasyOCR > Tesseract)
=====================================================

Runtime-detects available OCR providers and uses the best one.
If none are available, returns an empty result with a warning.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _probe_paddleocr() -> Optional[Any]:
    try:
        import paddleocr  # type: ignore
        return paddleocr
    except Exception:
        return None


def _probe_easyocr() -> Optional[Any]:
    try:
        import easyocr  # type: ignore
        return easyocr
    except Exception:
        return None


def _probe_tesseract() -> Optional[Any]:
    try:
        import pytesseract  # type: ignore
        return pytesseract
    except Exception:
        return None


class OCREngine:
    """High-level OCR facade with provider fallback chain."""

    def __init__(self, lang: str = "en") -> None:
        self.lang = lang
        self._paddle = _probe_paddleocr()
        self._easy = _probe_easyocr()
        self._tess = _probe_tesseract()
        self._reader = None

        if self._paddle:
            try:
                self._reader = self._paddle.PaddleOCR(
                    use_angle_cls=True, lang=self.lang, show_log=False
                )
            except Exception:
                self._reader = None
        elif self._easy:
            try:
                self._reader = self._easy.Reader([self.lang])
            except Exception:
                self._reader = None

    def available(self) -> bool:
        return bool(self._paddle or self._easy or self._tess)

    def extract_text(self, image) -> List[Dict[str, Any]]:
        """Extract text elements from an image (numpy array or PIL)."""
        if self._paddle and self._reader:
            try:
                res = self._reader.ocr(image, cls=True)
                out: List[Dict[str, Any]] = []
                lines = res[0] if res and isinstance(res, list) else []
                for i, item in enumerate(lines):
                    try:
                        box, (txt, conf) = item
                    except Exception:
                        continue
                    xs = [p[0] for p in box]
                    ys = [p[1] for p in box]
                    out.append(
                        {
                            "id": f"paddle_{i}",
                            "text": txt,
                            "confidence": float(conf),
                            "x": int(min(xs)),
                            "y": int(min(ys)),
                            "width": int(max(xs) - min(xs)),
                            "height": int(max(ys) - min(ys)),
                            "bbox": box,
                            "engine": "paddleocr",
                        }
                    )
                return out
            except Exception:
                pass

        if self._easy and self._reader:
            try:
                res = self._reader.readtext(image)
                out: List[Dict[str, Any]] = []
                for i, (box, txt, conf) in enumerate(res):
                    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = box
                    xs = [x0, x1, x2, x3]
                    ys = [y0, y1, y2, y3]
                    out.append(
                        {
                            "id": f"easy_{i}",
                            "text": txt,
                            "confidence": float(conf),
                            "x": int(min(xs)),
                            "y": int(min(ys)),
                            "width": int(max(xs) - min(xs)),
                            "height": int(max(ys) - min(ys)),
                            "bbox": box,
                            "engine": "easyocr",
                        }
                    )
                return out
            except Exception:
                pass

        if self._tess:
            try:
                # Basic tesseract pass: returns one big string; no boxes
                txt = self._tess.image_to_string(image)  # type: ignore
                if txt:
                    return [
                        {
                            "id": "tess_0",
                            "text": txt.strip(),
                            "confidence": 0.0,
                            "x": 0,
                            "y": 0,
                            "width": 0,
                            "height": 0,
                            "bbox": None,
                            "engine": "tesseract",
                        }
                    ]
            except Exception:
                pass

        print("[OCR] No provider available; returning empty result")
        return []
