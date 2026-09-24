"""Object storage ports and safe local/S3-compatible implementations."""

from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import re
import secrets
import tempfile
from collections.abc import AsyncIterable
from pathlib import Path
from typing import Any, Protocol

from fastapi import Request
from fastapi.responses import FileResponse, Response

from ..core.config import StorageSettings
from ..core.errors import ValidationAppError
from ..core.logging import JsonLogger
from .scanner import ScannerAdapter, build_scanner

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,254}$")
_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
}


class StorageAdapter(Protocol):
    provider: str

    async def ready(self) -> bool: ...

    async def save_stream(
        self,
        chunks: AsyncIterable[bytes],
        name: str,
        content_type: str,
        kind: str,
        owner_subject: str,
        declared_size: int = 0,
    ) -> dict[str, Any]: ...

    async def create_intent(
        self, name: str, content_type: str, size: int, kind: str, owner_subject: str
    ) -> dict[str, Any]: ...

    async def complete(
        self, intent: dict[str, Any], parts: list[dict[str, Any]]
    ) -> dict[str, Any]: ...

    async def get_intent(self, upload_id: str) -> dict[str, Any] | None: ...

    async def delete(self, upload: dict[str, Any]) -> None: ...

    async def response(self, upload: dict[str, Any], request: Request) -> Response: ...


class LocalStorage:
    provider = "local"

    def __init__(
        self, settings: StorageSettings, logger: JsonLogger, scanner: ScannerAdapter
    ) -> None:
        self.settings = settings
        self.logger = logger
        self.scanner = scanner
        self.root = settings.upload_dir
        self.root.mkdir(parents=True, exist_ok=True)
        settings.data_dir.mkdir(parents=True, exist_ok=True)

    async def ready(self) -> bool:
        try:
            await asyncio.to_thread(self.root.mkdir, parents=True, exist_ok=True)
            return os.access(self.root, os.W_OK) and await self.scanner.ready()
        except OSError:
            return False

    async def save_stream(
        self,
        chunks: AsyncIterable[bytes],
        name: str,
        content_type: str,
        kind: str,
        owner_subject: str,
        declared_size: int = 0,
    ) -> dict[str, Any]:
        _validate_metadata(name, content_type, kind, declared_size, self.settings.max_upload_bytes)
        extension = _extension(name, content_type)
        token = secrets.token_hex(24)
        path = self.root / f"{token}{extension}"
        size = 0
        prefix = bytearray()
        try:
            for_path = path
            await asyncio.to_thread(for_path.parent.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(for_path.touch, exist_ok=False)
            async for chunk in chunks:
                size += len(chunk)
                if size > self.settings.max_upload_bytes:
                    raise ValidationAppError(
                        "Файл превышает допустимый размер.", "UPLOAD_TOO_LARGE"
                    )
                if len(prefix) < 64:
                    prefix.extend(chunk[: 64 - len(prefix)])
                await asyncio.to_thread(_append_bytes, for_path, chunk)
            if declared_size and size != declared_size:
                raise ValidationAppError(
                    "Размер файла не совпадает с заявленным.", "UPLOAD_SIZE_MISMATCH"
                )
            _validate_magic(bytes(prefix), content_type)
            scan_status = await self.scanner.scan_path(path)
            if scan_status != "clean":
                raise ValidationAppError(
                    "Файл не прошёл проверку безопасности.", "UPLOAD_SCAN_REJECTED"
                )
            return {
                "upload_id": token,
                "url": f"/uploads/{path.name}",
                "storage_key": path.name,
                "storage_path": str(path),
                "original_name": name,
                "content_type": content_type,
                "size_bytes": size,
                "kind": kind,
                "status": "clean",
                "scan_status": scan_status,
                "claim_subject": owner_subject,
            }
        except Exception:
            await asyncio.to_thread(_unlink, path)
            raise

    async def create_intent(
        self, name: str, content_type: str, size: int, kind: str, owner_subject: str
    ) -> dict[str, Any]:
        _validate_metadata(name, content_type, kind, size, self.settings.max_upload_bytes)
        # Local multipart is intentionally not advertised; the stream endpoint is
        # deterministic and avoids pretending a local filesystem is S3.
        raise ValidationAppError(
            "Multipart-загрузка доступна только для object storage.", "MULTIPART_NOT_SUPPORTED"
        )

    async def complete(self, intent: dict[str, Any], parts: list[dict[str, Any]]) -> dict[str, Any]:
        raise ValidationAppError(
            "Multipart-загрузка доступна только для object storage.", "MULTIPART_NOT_SUPPORTED"
        )

    async def delete(self, upload: dict[str, Any]) -> None:
        path = Path(str(upload.get("storage_path", "")))
        if path.is_file() and path.parent.resolve() == self.root.resolve():
            await asyncio.to_thread(path.unlink)

    async def get_intent(self, upload_id: str) -> dict[str, Any] | None:
        return None

    async def response(self, upload: dict[str, Any], request: Request) -> Response:
        path = Path(str(upload.get("storage_path", ""))).resolve()
        if path.parent != self.root.resolve() or not path.is_file():
            raise FileNotFoundError(path)
        disposition = (
            "inline"
            if upload.get("content_type", "").startswith(("image/", "video/"))
            else "attachment"
        )
        return FileResponse(
            path,
            media_type=upload.get("content_type") or mimetypes.guess_type(path.name)[0],
            filename=upload.get("original_name") or path.name,
            content_disposition_type=disposition,
            headers={
                "Cache-Control": "private, no-store",
                "X-Request-Id": request.state.request_id,
            },
        )


class S3Storage:
    """S3 adapter seam; blocking boto3 calls are isolated in worker threads."""

    provider = "s3"

    def __init__(
        self,
        settings: StorageSettings,
        logger: JsonLogger,
        redis_client: Any | None = None,
        scanner: ScannerAdapter | None = None,
    ) -> None:
        self.settings = settings
        self.logger = logger
        self.redis = redis_client
        self.scanner = scanner or build_scanner(settings, logger)
        self._intents: dict[str, dict[str, Any]] = {}
        import boto3
        from botocore.config import Config

        self.client = boto3.client(
            "s3",
            region_name=settings.s3_region or None,
            endpoint_url=settings.s3_endpoint_url or None,
            aws_access_key_id=settings.s3_access_key or None,
            aws_secret_access_key=settings.s3_secret_key or None,
            config=Config(
                s3={"addressing_style": ("path" if settings.s3_force_path_style else "auto")}
            ),
        )

    async def ready(self) -> bool:
        try:
            await asyncio.to_thread(self.client.head_bucket, Bucket=self.settings.s3_bucket)
            return await self.scanner.ready()
        except Exception:
            return False

    async def save_stream(
        self,
        chunks: AsyncIterable[bytes],
        name: str,
        content_type: str,
        kind: str,
        owner_subject: str,
        declared_size: int = 0,
    ) -> dict[str, Any]:
        _validate_metadata(name, content_type, kind, declared_size, self.settings.max_upload_bytes)
        data = bytearray()
        prefix = bytearray()
        async for chunk in chunks:
            data.extend(chunk)
            if len(prefix) < 64:
                prefix.extend(chunk[: 64 - len(prefix)])
            if len(data) > self.settings.max_upload_bytes:
                raise ValidationAppError("Файл превышает допустимый размер.", "UPLOAD_TOO_LARGE")
        if declared_size and len(data) != declared_size:
            raise ValidationAppError(
                "Размер файла не совпадает с заявленным.", "UPLOAD_SIZE_MISMATCH"
            )
        _validate_magic(bytes(prefix), content_type)
        scan_status = await self._scan_bytes(bytes(data))
        if scan_status != "clean":
            raise ValidationAppError(
                "Файл не прошёл проверку безопасности.", "UPLOAD_SCAN_REJECTED"
            )
        key = f"{self.settings.s3_prefix}/{secrets.token_hex(24)}{_extension(name, content_type)}"
        kwargs: dict[str, Any] = {
            "Bucket": self.settings.s3_bucket,
            "Key": key,
            "Body": bytes(data),
            "ContentType": content_type,
            "ServerSideEncryption": self.settings.s3_server_side_encryption,
        }
        if self.settings.s3_server_side_encryption == "aws:kms":
            kwargs["SSEKMSKeyId"] = self.settings.s3_kms_key_id
        await asyncio.to_thread(self.client.put_object, **kwargs)
        return {
            "upload_id": secrets.token_hex(24),
            "url": f"/uploads/{key}",
            "storage_key": key,
            "original_name": name,
            "content_type": content_type,
            "size_bytes": len(data),
            "kind": kind,
            "status": "clean",
            "scan_status": "clean",
            "claim_subject": owner_subject,
        }

    async def create_intent(
        self, name: str, content_type: str, size: int, kind: str, owner_subject: str
    ) -> dict[str, Any]:
        _validate_metadata(name, content_type, kind, size, self.settings.max_upload_bytes)
        if self.settings.upload_scan_required and self.scanner.provider == "none":
            raise ValidationAppError("Проверка файлов не настроена.", "UPLOAD_SCANNER_UNAVAILABLE")
        key = f"{self.settings.s3_prefix}/{secrets.token_hex(24)}{_extension(name, content_type)}"
        kwargs: dict[str, Any] = {
            "Bucket": self.settings.s3_bucket,
            "Key": key,
            "ContentType": content_type,
            "ServerSideEncryption": self.settings.s3_server_side_encryption,
        }
        if self.settings.s3_server_side_encryption == "aws:kms":
            kwargs["SSEKMSKeyId"] = self.settings.s3_kms_key_id
        upload_id = await asyncio.to_thread(self.client.create_multipart_upload, **kwargs)
        intent = {
            "upload_id": upload_id["UploadId"],
            "key": key,
            "owner_subject": owner_subject,
            "name": name,
            "content_type": content_type,
            "size": size,
            "kind": kind,
        }
        upload_id_value = str(upload_id["UploadId"])
        self._intents[upload_id_value] = intent
        if self.redis is not None:
            await self.redis.setex(
                f"lug:upload-intent:{upload_id_value}",
                900,
                json.dumps(intent, separators=(",", ":")),
            )
        return {"uploadId": upload_id_value, "key": key, "parts": []}

    async def get_intent(self, upload_id: str) -> dict[str, Any] | None:
        if self.redis is not None:
            value = await self.redis.get(f"lug:upload-intent:{upload_id}")
            if value:
                try:
                    return json.loads(value)
                except (TypeError, ValueError):
                    self.logger.warning("storage.invalid_upload_intent", upload_id=upload_id)
                    return None
        return self._intents.get(upload_id)

    async def complete(self, intent: dict[str, Any], parts: list[dict[str, Any]]) -> dict[str, Any]:
        if not parts:
            raise ValidationAppError(
                "Не указаны части multipart-загрузки.", "UPLOAD_PARTS_REQUIRED"
            )
        try:
            normalized = [
                {"PartNumber": int(item["partNumber"]), "ETag": str(item["etag"])} for item in parts
            ]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationAppError(
                "Некорректные части multipart-загрузки.", "UPLOAD_PARTS_INVALID"
            ) from exc
        result = await asyncio.to_thread(
            self.client.complete_multipart_upload,
            Bucket=self.settings.s3_bucket,
            Key=intent["key"],
            UploadId=intent["upload_id"],
            MultipartUpload={"Parts": normalized},
        )
        head = await asyncio.to_thread(
            self.client.head_object, Bucket=self.settings.s3_bucket, Key=intent["key"]
        )
        if int(head.get("ContentLength", -1)) != int(intent["size"]):
            await self._clear_intent(str(intent["upload_id"]))
            await self.delete({"storage_key": intent["key"]})
            raise ValidationAppError(
                "Размер файла не совпадает с заявленным.", "UPLOAD_SIZE_MISMATCH"
            )
        scan_status = await self._scan_object(intent["key"])
        await self._clear_intent(str(intent["upload_id"]))
        if scan_status != "clean":
            await self.delete({"storage_key": intent["key"]})
            raise ValidationAppError(
                "Файл не прошёл проверку безопасности.", "UPLOAD_SCAN_REJECTED"
            )
        return {
            "upload_id": intent["upload_id"],
            "url": f"/uploads/{intent['key']}",
            "storage_key": intent["key"],
            "original_name": intent["name"],
            "content_type": intent["content_type"],
            "size_bytes": intent["size"],
            "kind": intent["kind"],
            "status": "clean",
            "scan_status": "clean",
            "claim_subject": intent["owner_subject"],
            "etag": result.get("ETag", ""),
        }

    async def delete(self, upload: dict[str, Any]) -> None:
        await asyncio.to_thread(
            self.client.delete_object, Bucket=self.settings.s3_bucket, Key=upload["storage_key"]
        )

    async def response(self, upload: dict[str, Any], request: Request) -> Response:
        url = await asyncio.to_thread(
            self.client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self.settings.s3_bucket, "Key": upload["storage_key"]},
            ExpiresIn=self.settings.s3_signed_url_ttl,
        )
        return Response(
            status_code=302,
            headers={
                "Location": url,
                "Cache-Control": "private, no-store",
                "X-Request-Id": request.state.request_id,
            },
        )

    async def _scan_bytes(self, data: bytes) -> str:
        if not self.settings.upload_scan_required:
            return "clean"
        path = await asyncio.to_thread(_write_temp_file, data)
        try:
            return await self.scanner.scan_path(path)
        finally:
            await asyncio.to_thread(_unlink, path)

    async def _scan_object(self, key: str) -> str:
        if not self.settings.upload_scan_required:
            return "clean"
        path = await asyncio.to_thread(
            _download_temp_file, self.client, self.settings.s3_bucket, key
        )
        try:
            return await self.scanner.scan_path(path)
        finally:
            await asyncio.to_thread(_unlink, path)

    async def _clear_intent(self, upload_id: str) -> None:
        self._intents.pop(upload_id, None)
        if self.redis is not None:
            try:
                await self.redis.delete(f"lug:upload-intent:{upload_id}")
            except Exception as exc:
                self.logger.warning(
                    "storage.intent_cleanup_failed",
                    upload_id=upload_id,
                    error_type=type(exc).__name__,
                )


def _append_bytes(path: Path, chunk: bytes) -> None:
    with path.open("ab") as handle:
        handle.write(chunk)


def _unlink(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _write_temp_file(data: bytes) -> Path:
    descriptor, name = tempfile.mkstemp(prefix="lug-scan-")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(data)
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        _unlink(Path(name))
        raise
    return Path(name)


def _download_temp_file(client: Any, bucket: str, key: str) -> Path:
    descriptor, name = tempfile.mkstemp(prefix="lug-scan-")
    path = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            body = client.get_object(Bucket=bucket, Key=key)["Body"]
            try:
                while chunk := body.read(1024 * 1024):
                    handle.write(chunk)
            finally:
                body.close()
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        _unlink(path)
        raise
    return path


def _validate_metadata(name: str, content_type: str, kind: str, size: int, maximum: int) -> None:
    if not name or len(name) > 255 or Path(name).name != name or not _SAFE_NAME.fullmatch(name):
        raise ValidationAppError("Недопустимое имя файла.", "UPLOAD_INVALID_NAME")
    if not content_type or content_type not in _EXTENSIONS:
        raise ValidationAppError("Недопустимый тип файла.", "UPLOAD_INVALID_TYPE")
    if kind not in {"attachment", "video", "student-card"}:
        raise ValidationAppError("Недопустимый вид загрузки.", "UPLOAD_INVALID_KIND")
    if size < 0 or size > maximum:
        raise ValidationAppError("Файл превышает допустимый размер.", "UPLOAD_TOO_LARGE")


def _extension(name: str, content_type: str) -> str:
    return _EXTENSIONS.get(content_type) or Path(name).suffix.lower() or ".bin"


def _validate_magic(prefix: bytes, content_type: str) -> None:
    signatures = {
        "image/png": prefix.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": prefix.startswith(b"\xff\xd8\xff"),
        "application/pdf": prefix.startswith(b"%PDF"),
        "application/msword": prefix.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": prefix.startswith(
            b"PK\x03\x04"
        ),
        "image/gif": prefix.startswith((b"GIF87a", b"GIF89a")),
        "image/webp": prefix.startswith(b"RIFF") and prefix[8:12] == b"WEBP",
        "video/mp4": len(prefix) >= 12 and prefix[4:8] == b"ftyp",
        "video/quicktime": len(prefix) >= 12 and prefix[4:8] == b"ftyp",
        "video/webm": prefix.startswith(b"\x1a\x45\xdf\xa3"),
    }
    if content_type in signatures and not signatures[content_type]:
        raise ValidationAppError("Содержимое файла не соответствует типу.", "UPLOAD_MAGIC_MISMATCH")


def build_storage(
    settings: StorageSettings,
    logger: JsonLogger,
    redis_client: Any | None = None,
    scanner: ScannerAdapter | None = None,
) -> StorageAdapter:
    resolved_scanner = scanner or build_scanner(settings, logger)
    return (
        S3Storage(settings, logger, redis_client, resolved_scanner)
        if settings.provider == "s3"
        else LocalStorage(settings, logger, resolved_scanner)
    )
