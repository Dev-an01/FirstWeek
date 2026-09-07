"""
OCR Parser - Handles scanned PDFs and image-based documents.

Supports two backends:
- MinerU (default): Pipeline-based, works on 6GB VRAM (RTX 3060)
- olmOCR 2: Vision-language model, needs 32GB VRAM (RTX 5090)
"""

import logging
import os
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class OCRBackend(ABC):
    """Abstract base class for OCR backends."""

    @abstractmethod
    def ocr_pdf(self, file_bytes: bytes, filename: str) -> str:
        """Convert PDF to text using OCR."""
        pass

    @abstractmethod
    def ocr_image(self, file_bytes: bytes, filename: str) -> str:
        """Convert image to text using OCR."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is available."""
        pass


class MinerUBackend(OCRBackend):
    """MinerU OCR backend - works on RTX 3060 6GB VRAM."""

    def __init__(self, config: dict):
        self.config = config
        self._available: Optional[bool] = None
        self.base_timeout = config.get("timeout", 600)

    def _calculate_timeout(self, file_bytes: bytes) -> int:
        """
        Calculate timeout based on estimated page count.

        For scanned PDFs, we estimate ~100KB per page. Each page may take
        up to 60 seconds for complex OCR operations.

        Args:
            file_bytes: Raw file bytes

        Returns:
            Calculated timeout in seconds (minimum is base_timeout)
        """
        # Estimate ~100KB per page for scanned PDFs
        estimated_pages = max(1, len(file_bytes) // 100_000)
        # 60 seconds per page, minimum base_timeout
        page_based_timeout = estimated_pages * 60
        calculated = max(self.base_timeout, page_based_timeout)
        logger.debug(
            f"Calculated timeout: {calculated}s (est. {estimated_pages} pages, "
            f"base: {self.base_timeout}s)"
        )
        return calculated

    def is_available(self) -> bool:
        if self._available is None:
            # Check if magic-pdf CLI is available (MinerU's package name)
            try:
                # First try shutil.which (faster)
                if shutil.which("magic-pdf") is not None:
                    self._available = True
                else:
                    # Fallback to subprocess check
                    result = subprocess.run(
                        ["magic-pdf", "--version"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        shell=True  # Needed for Windows PATH resolution
                    )
                    self._available = result.returncode == 0
            except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
                logger.debug(f"MinerU (magic-pdf) availability check failed: {e}")
                self._available = False
        return self._available

    def ocr_pdf(self, file_bytes: bytes, filename: str) -> str:
        """Use MinerU to OCR a PDF."""
        if not self.is_available():
            raise RuntimeError("MinerU is not installed or not available")

        temp_dir = None
        pdf_path = None
        output_dir = None
        timeout = self._calculate_timeout(file_bytes)

        try:
            # Create temp directory for all files
            temp_dir = tempfile.mkdtemp(prefix="mineru_ocr_")
            pdf_path = os.path.join(temp_dir, "input.pdf")
            output_dir = os.path.join(temp_dir, "output")
            os.makedirs(output_dir, exist_ok=True)

            # Write PDF bytes to temp file
            with open(pdf_path, "wb") as f:
                f.write(file_bytes)

            # Run magic-pdf CLI with configured method
            # MinerU methods: 'ocr' (force OCR), 'txt' (text-based), 'auto' (detect)
            method = self.config.get("method", "auto")
            logger.info(f"Running MinerU OCR on '{filename}' with method '{method}' (timeout: {timeout}s)")
            result = subprocess.run(
                ["magic-pdf", "-p", pdf_path, "-o", output_dir, "-m", method],
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode != 0:
                logger.warning(f"MinerU returned non-zero exit code: {result.stderr}")

            # Find and read markdown output
            output_path = Path(output_dir)
            md_files = list(output_path.glob("**/*.md"))

            if md_files:
                # Read the first markdown file found
                text = md_files[0].read_text(encoding="utf-8")
                logger.info(f"MinerU extracted {len(text)} chars from '{filename}'")
                return text

            logger.warning(f"MinerU produced no markdown output for '{filename}'")
            return ""

        except subprocess.TimeoutExpired:
            logger.error(f"MinerU OCR timed out after {timeout}s for '{filename}'")
            return ""
        except Exception as e:
            logger.error(f"MinerU OCR failed for '{filename}': {e}")
            return ""
        finally:
            # Cleanup temp directory
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp dir: {e}")

    def ocr_image(self, file_bytes: bytes, filename: str) -> str:
        """Use MinerU to OCR an image by converting to single-page PDF."""
        if not self.is_available():
            raise RuntimeError("MinerU is not installed or not available")

        temp_dir = None
        # Images are single page, use base timeout (min 60s for one page)
        timeout = max(self.base_timeout, 60)

        try:
            # Create temp directory
            temp_dir = tempfile.mkdtemp(prefix="mineru_img_")
            ext = Path(filename).suffix.lower()
            img_path = os.path.join(temp_dir, f"input{ext}")
            output_dir = os.path.join(temp_dir, "output")
            os.makedirs(output_dir, exist_ok=True)

            # Write image bytes
            with open(img_path, "wb") as f:
                f.write(file_bytes)

            # Run magic-pdf on image with configured method
            method = self.config.get("method", "ocr")  # Force OCR for images
            logger.info(f"Running MinerU OCR on image '{filename}' with method '{method}' (timeout: {timeout}s)")
            result = subprocess.run(
                ["magic-pdf", "-p", img_path, "-o", output_dir, "-m", method],
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode != 0:
                logger.warning(f"MinerU returned non-zero exit code: {result.stderr}")

            # Find markdown output
            output_path = Path(output_dir)
            md_files = list(output_path.glob("**/*.md"))

            if md_files:
                text = md_files[0].read_text(encoding="utf-8")
                logger.info(f"MinerU extracted {len(text)} chars from image '{filename}'")
                return text

            return ""

        except subprocess.TimeoutExpired:
            logger.error(f"MinerU image OCR timed out for '{filename}'")
            return ""
        except Exception as e:
            logger.error(f"MinerU image OCR failed for '{filename}': {e}")
            return ""
        finally:
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp dir: {e}")


class OlmOCR2Backend(OCRBackend):
    """olmOCR 2 backend - needs RTX 5090 32GB VRAM."""

    def __init__(self, config: dict):
        self.config = config
        self._available: Optional[bool] = None
        self.timeout = config.get("timeout", 600)
        self.model = config.get("model", "allenai/olmOCR-2-7B-1025")
        self.vllm_server = config.get("vllm_server")

    def is_available(self) -> bool:
        if self._available is None:
            # Check if olmocr module is available
            try:
                result = subprocess.run(
                    ["python", "-c", "import olmocr"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                self._available = result.returncode == 0
            except (FileNotFoundError, subprocess.TimeoutExpired):
                self._available = False
        return self._available

    def ocr_pdf(self, file_bytes: bytes, filename: str) -> str:
        """Use olmOCR 2 to OCR a PDF."""
        if not self.is_available():
            raise RuntimeError("olmOCR is not installed or not available")

        temp_dir = None

        try:
            temp_dir = tempfile.mkdtemp(prefix="olmocr_")
            pdf_path = os.path.join(temp_dir, "input.pdf")
            output_dir = os.path.join(temp_dir, "output")
            os.makedirs(output_dir, exist_ok=True)

            # Write PDF bytes
            with open(pdf_path, "wb") as f:
                f.write(file_bytes)

            # Build olmOCR command
            cmd = [
                "python", "-m", "olmocr.pipeline",
                output_dir,
                "--markdown",
                "--pdfs", pdf_path
            ]

            # Add vLLM server if configured
            if self.vllm_server:
                cmd.extend(["--server", self.vllm_server])
                cmd.extend(["--model", self.model])

            logger.info(f"Running olmOCR 2 on '{filename}'")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            if result.returncode != 0:
                logger.warning(f"olmOCR returned non-zero: {result.stderr}")

            # Read markdown output
            md_dir = Path(output_dir) / "markdown"
            md_files = list(md_dir.glob("*.md")) if md_dir.exists() else []

            if md_files:
                text = md_files[0].read_text(encoding="utf-8")
                logger.info(f"olmOCR extracted {len(text)} chars from '{filename}'")
                return text

            return ""

        except subprocess.TimeoutExpired:
            logger.error(f"olmOCR timed out after {self.timeout}s for '{filename}'")
            return ""
        except Exception as e:
            logger.error(f"olmOCR failed for '{filename}': {e}")
            return ""
        finally:
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp dir: {e}")

    def ocr_image(self, file_bytes: bytes, filename: str) -> str:
        """Use olmOCR 2 to OCR an image."""
        if not self.is_available():
            raise RuntimeError("olmOCR is not installed or not available")

        temp_dir = None

        try:
            temp_dir = tempfile.mkdtemp(prefix="olmocr_img_")
            ext = Path(filename).suffix.lower()
            img_path = os.path.join(temp_dir, f"input{ext}")
            output_dir = os.path.join(temp_dir, "output")
            os.makedirs(output_dir, exist_ok=True)

            with open(img_path, "wb") as f:
                f.write(file_bytes)

            # olmOCR can handle images directly
            cmd = [
                "python", "-m", "olmocr.pipeline",
                output_dir,
                "--markdown",
                "--images", img_path
            ]

            if self.vllm_server:
                cmd.extend(["--server", self.vllm_server])
                cmd.extend(["--model", self.model])

            logger.info(f"Running olmOCR 2 on image '{filename}'")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            if result.returncode != 0:
                logger.warning(f"olmOCR image returned non-zero: {result.stderr}")

            md_dir = Path(output_dir) / "markdown"
            md_files = list(md_dir.glob("*.md")) if md_dir.exists() else []

            if md_files:
                text = md_files[0].read_text(encoding="utf-8")
                logger.info(f"olmOCR extracted {len(text)} chars from image '{filename}'")
                return text

            return ""

        except subprocess.TimeoutExpired:
            logger.error(f"olmOCR image OCR timed out for '{filename}'")
            return ""
        except Exception as e:
            logger.error(f"olmOCR image OCR failed for '{filename}': {e}")
            return ""
        finally:
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp dir: {e}")


def get_ocr_backend(config: dict) -> Optional[OCRBackend]:
    """
    Factory function to get configured OCR backend.

    Args:
        config: OCR configuration dictionary

    Returns:
        OCRBackend instance or None if not available
    """
    backend_name = config.get("backend", "mineru")

    if backend_name == "mineru":
        backend = MinerUBackend(config.get("mineru", {}))
    elif backend_name == "olmocr2":
        backend = OlmOCR2Backend(config.get("olmocr2", {}))
    else:
        logger.warning(f"Unknown OCR backend: {backend_name}")
        return None

    if not backend.is_available():
        logger.warning(f"OCR backend '{backend_name}' not available (not installed)")
        return None

    return backend


def parse_pdf_with_ocr(file_bytes: bytes, filename: str = "document.pdf") -> str:
    """
    Parse PDF using OCR.

    Args:
        file_bytes: Raw PDF bytes
        filename: Original filename

    Returns:
        Extracted text from OCR

    Raises:
        ValueError: If no OCR backend is available
    """
    from onboarding.config import OCR_CONFIG

    backend = get_ocr_backend(OCR_CONFIG)
    if backend is None:
        raise ValueError(
            f"No OCR backend available. "
            f"Install mineru or olmocr. Configured backend: {OCR_CONFIG.get('backend')}"
        )

    logger.info(f"Using OCR backend: {OCR_CONFIG['backend']}")
    return backend.ocr_pdf(file_bytes, filename)


def parse_image_with_ocr(file_bytes: bytes, filename: str) -> str:
    """
    Parse image using OCR.

    Args:
        file_bytes: Raw image bytes
        filename: Original filename

    Returns:
        Extracted text from OCR

    Raises:
        ValueError: If no OCR backend is available
    """
    from onboarding.config import OCR_CONFIG

    backend = get_ocr_backend(OCR_CONFIG)
    if backend is None:
        raise ValueError(
            f"No OCR backend available for images. "
            f"Install mineru or olmocr. Configured backend: {OCR_CONFIG.get('backend')}"
        )

    logger.info(f"Using OCR backend for image: {OCR_CONFIG['backend']}")
    return backend.ocr_image(file_bytes, filename)
