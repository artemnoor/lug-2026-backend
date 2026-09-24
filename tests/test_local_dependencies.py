"""Regression coverage for the concrete local dependency adapters."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.core.config import EmailSettings, Settings, StorageSettings
from app.core.logging import JsonLogger
from app.infrastructure.email import EmailService
from app.infrastructure.scanner import build_scanner


def test_compose_declares_real_s3_scanner_and_smtp_services():
    compose = (Path(__file__).parents[1] / "docker-compose.yml").read_text(encoding="utf-8")
    for service in ("backend", "minio", "minio-init", "clamav", "mailpit"):
        assert f"  {service}:" in compose
    assert "LUG_FILE_STORAGE_PROVIDER: s3" in compose
    assert "LUG_S3_ENDPOINT_URL: http://minio:9000" in compose
    assert "MINIO_KMS_SECRET_KEY:" in compose
    assert "LUG_UPLOAD_SCANNER: clamav" in compose
    assert "LUG_EMAIL_MODE: smtp" in compose
    assert "LUG_SMTP_HOST: mailpit" in compose


def test_compose_dependency_settings_are_typed():
    settings = Settings.from_env(
        {
            "LUG_ENV": "development",
            "LUG_FILE_STORAGE_PROVIDER": "s3",
            "LUG_S3_BUCKET": "lug",
            "LUG_S3_FORCE_PATH_STYLE": "true",
            "LUG_UPLOAD_SCANNER": "clamav",
            "LUG_UPLOAD_SCANNER_HOST": "clamav",
            "LUG_UPLOAD_SCANNER_PORT": "3310",
            "LUG_UPLOAD_SCAN_REQUIRED": "true",
            "LUG_EMAIL_MODE": "smtp",
            "LUG_SMTP_HOST": "mailpit",
            "LUG_SMTP_PORT": "1025",
        }
    )
    assert settings.storage.scanner_provider == "clamav"
    assert settings.storage.scanner_port == 3310
    assert settings.storage.s3_force_path_style is True
    assert settings.email.smtp_port == 1025


@pytest.mark.asyncio
async def test_clamav_scanner_uses_ping_and_stream_protocol(tmp_path):
    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            command = await reader.readuntil(b"\0")
            if command == b"zPING\0":
                writer.write(b"PONG\0")
            elif command == b"zINSTREAM\0":
                while True:
                    size = int.from_bytes(await reader.readexactly(4), "big")
                    if size == 0:
                        break
                    await reader.readexactly(size)
                writer.write(b"stream: OK\0")
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle_client, "127.0.0.1", 0)
    port = int(server.sockets[0].getsockname()[1])
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"safe upload")
    settings = StorageSettings(
        scanner_provider="clamav",
        scanner_host="127.0.0.1",
        scanner_port=port,
        scanner_timeout_seconds=2,
        upload_scan_required=True,
    )
    scanner = build_scanner(settings, JsonLogger("test-scanner"))
    try:
        assert await scanner.ready() is True
        assert await scanner.scan_path(sample) == "clean"
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_smtp_adapter_readiness_uses_configured_server():
    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        writer.write(b"220 local-test SMTP\r\n")
        await writer.drain()
        try:
            while line := await reader.readline():
                command = line.upper()
                if command.startswith((b"EHLO", b"HELO")):
                    writer.write(b"250-local-test\r\n250 OK\r\n")
                elif command.startswith(b"NOOP"):
                    writer.write(b"250 OK\r\n")
                elif command.startswith(b"QUIT"):
                    writer.write(b"221 Bye\r\n")
                    await writer.drain()
                    break
                else:
                    writer.write(b"250 OK\r\n")
                await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle_client, "127.0.0.1", 0)
    port = int(server.sockets[0].getsockname()[1])
    service = EmailService(
        EmailSettings(
            mode="smtp",
            smtp_host="127.0.0.1",
            smtp_port=port,
            smtp_starttls=False,
        ),
        JsonLogger("test-email"),
    )
    try:
        assert await service.ready() is True
    finally:
        server.close()
        await server.wait_closed()
