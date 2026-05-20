import subprocess
import time
from pathlib import Path
from shutil import which
from typing import Optional

from app.models.schemas import ProviderConfig

from .base import OCRResult
from .fake import FakeOCRProvider
from .openai_compatible import OpenAICompatibleOCRProvider

ocr_provider = FakeOCRProvider()


class TesseractOCRProvider:
    provider_name = "tesseract"

    def __init__(self, language: str = "eng", psm: str = "6", model_name: str = "") -> None:
        self.language = language
        self.psm = psm
        self.model_name = model_name or f"tesseract-{language}"

    def ocr(self, image_uri: str) -> OCRResult:
        started = time.monotonic()
        if not which("tesseract"):
            return OCRResult(
                self.provider_name,
                self.model_name,
                0,
                error_message="Tesseract OCR is configured but the tesseract executable is not installed.",
            )
        image_path = Path(image_uri)
        if not image_path.exists():
            return OCRResult(
                self.provider_name,
                self.model_name,
                0,
                error_message=f"OCR image file does not exist: {image_uri}",
            )
        try:
            completed = subprocess.run(
                ["tesseract", str(image_path), "stdout", "-l", self.language, "--psm", self.psm],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            latency_ms = int((time.monotonic() - started) * 1000)
            return OCRResult(
                self.provider_name,
                self.model_name,
                latency_ms,
                error_message="Tesseract OCR timed out after 30 seconds.",
            )

        latency_ms = int((time.monotonic() - started) * 1000)
        if completed.returncode != 0:
            return OCRResult(
                self.provider_name,
                self.model_name,
                latency_ms,
                error_message=completed.stderr.strip() or "Tesseract OCR failed.",
            )
        return OCRResult(
            self.provider_name,
            self.model_name,
            latency_ms,
            text=completed.stdout.strip(),
            confidence=0.0,
        )


def run_configured_ocr(provider_config: Optional[ProviderConfig], image_uri: str) -> OCRResult:
    if not provider_config or provider_config.provider_name == ocr_provider.provider_name:
        result = ocr_provider.ocr(image_uri)
        if provider_config:
            result.provider_name = provider_config.provider_name
            result.model_name = provider_config.model_name
        return result

    if provider_config.provider_name == "tesseract":
        config = provider_config.config_json
        return TesseractOCRProvider(
            language=str(config.get("language", "eng") or "eng"),
            psm=str(config.get("psm", "6") or "6"),
            model_name=provider_config.model_name,
        ).ocr(image_uri)

    if (
        provider_config.provider_name in {"openai", "openai_compatible", "openai-compatible"}
        or provider_config.config_json.get("adapter") == "openai_compatible"
    ):
        return OpenAICompatibleOCRProvider(
            provider_config.provider_name,
            provider_config.model_name,
            provider_config.config_json,
        ).ocr(image_uri)

    return OCRResult(
        provider_config.provider_name,
        provider_config.model_name,
        0,
        error_message=f"OCR provider '{provider_config.provider_name}' is configured but no adapter is installed.",
    )
