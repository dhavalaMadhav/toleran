import hashlib
import os
import shutil
import uuid
from pathlib import Path
from typing import Tuple
from fastapi import UploadFile
from app.config import settings
from app.core.exceptions import AppError


class StorageService:
    def __init__(self, base_dir: Path = settings.STORAGE_DIR):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def compute_sha256(self, file_path: Path) -> str:
        """Computes the SHA256 checksum of a file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def compute_bytes_sha256(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def save_upload_file(self, upload_file: UploadFile, subfolder: str = "drawings") -> Tuple[str, str, int, str]:
        """
        Saves an uploaded file safely:
        - Prevents path traversal
        - Generates a collision-resistant safe filename
        - Calculates SHA256 hash and size
        Returns: (safe_filename, relative_path, file_size_bytes, sha256_hash)
        """
        original_name = Path(upload_file.filename).name  # strip any directory paths
        ext = "".join(Path(original_name).suffixes).lower()
        if not ext:
            ext = ".bin"

        unique_id = uuid.uuid4().hex[:12]
        safe_name = f"{unique_id}_{original_name}"
        target_dir = self.base_dir / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / safe_name

        hasher = hashlib.sha256()
        size = 0

        with open(target_path, "wb") as buffer:
            while chunk := upload_file.file.read(65536):
                size += len(chunk)
                if size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
                    buffer.close()
                    if target_path.exists():
                        target_path.unlink()
                    raise AppError(f"File size exceeds maximum allowed limit of {settings.MAX_UPLOAD_SIZE_MB}MB", status_code=413)
                hasher.update(chunk)
                buffer.write(chunk)

        sha256 = hasher.hexdigest()
        rel_path = str(target_path.relative_to(Path(".")) if target_path.is_relative_to(Path(".")) else target_path)
        return safe_name, rel_path, size, sha256

    def save_bytes(self, content: bytes, filename: str, subfolder: str = "crops") -> str:
        target_dir = self.base_dir / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename
        with open(target_path, "wb") as f:
            f.write(content)
        return str(target_path.relative_to(Path(".")) if target_path.is_relative_to(Path(".")) else target_path)

    def get_absolute_path(self, relative_path: str) -> Path:
        return Path(relative_path).resolve()


storage_service = StorageService()
