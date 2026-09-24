"""Upload scanner adapters.

The application only depends on the small ``ScannerAdapter`` port.  Local
development can use the same network protocol as production (ClamAV ``clamd``)
while the command adapter keeps compatibility with existing deployments that
already expose ``clamdscan`` or another trusted scanner binary.
"""

from __future__ import annotations

import asyncio
import shlex
import shutil
import struct
import subprocess
from pathlib import Path
from typing import Protocol

from ..core.config import StorageSettings
from ..core.logging import JsonLogger


class ScannerAdapter(Protocol):
    """Infrastructure port used by local and object storage adapters."""

    provider: str

    async def ready(self) -> bool: ...

    async def scan_path(self, path: Path) -> str: ...


class NoopScanner:
    provider = "none"

    def __init__(self, required: bool) -> None:
        self.required = required

    async def ready(self) -> bool:
        return not self.required

    async def scan_path(self, path: Path) -> str:
        del path
        return "rejected" if self.required else "clean"


class CommandScanner:
    provider = "command"

    def __init__(self, command: str, required: bool, timeout_seconds: float) -> None:
        self.command = command
        self.required = required
        self.timeout_seconds = timeout_seconds

    async def ready(self) -> bool:
        if not self.required:
            return True
        try:
            executable = shlex.split(self.command)[0]
        except (IndexError, ValueError):
            return False
        return bool(shutil.which(executable) or Path(executable).is_file())

    async def scan_path(self, path: Path) -> str:
        if not self.required:
            return "clean"
        try:
            result = await asyncio.to_thread(self._scan_sync, path)
        except (OSError, subprocess.SubprocessError, ValueError):
            return "rejected"
        return "clean" if result == 0 else "rejected"

    def _scan_sync(self, path: Path) -> int:
        return subprocess.run(
            shlex.split(self.command) + [str(path)],
            capture_output=True,
            timeout=self.timeout_seconds,
            check=False,
        ).returncode


class ClamAVScanner:
    """ClamAV ``clamd`` client using the bounded ``INSTREAM`` protocol."""

    provider = "clamav"
    _chunk_size = 1024 * 1024

    def __init__(
        self,
        host: str,
        port: int,
        required: bool,
        timeout_seconds: float,
        logger: JsonLogger,
    ) -> None:
        self.host = host
        self.port = port
        self.required = required
        self.timeout_seconds = timeout_seconds
        self.logger = logger

    async def ready(self) -> bool:
        if not self.required:
            return True
        try:
            response = await self._ping()
        except (OSError, asyncio.IncompleteReadError, asyncio.TimeoutError):
            self.logger.warning(
                "scanner.ready.failed", provider=self.provider, host=self.host, port=self.port
            )
            return False
        return response == b"PONG"

    async def scan_path(self, path: Path) -> str:
        if not self.required:
            return "clean"
        writer: asyncio.StreamWriter | None = None
        try:
            reader, writer = await self._connect()
            writer.write(b"zINSTREAM\0")
            await writer.drain()
            handle = await asyncio.to_thread(path.open, "rb")
            try:
                while True:
                    chunk = await asyncio.to_thread(handle.read, self._chunk_size)
                    if not chunk:
                        break
                    writer.write(struct.pack("!I", len(chunk)))
                    writer.write(chunk)
                    await writer.drain()
            finally:
                await asyncio.to_thread(handle.close)
            writer.write(b"\0\0\0\0")
            await writer.drain()
            response = await self._read_response(reader)
        except (OSError, asyncio.IncompleteReadError, asyncio.TimeoutError):
            self.logger.warning(
                "scanner.scan.failed", provider=self.provider, host=self.host, port=self.port
            )
            return "rejected"
        finally:
            await self._close(writer)

        return "clean" if response.lower() in {b"stream: ok", b"ok"} else "rejected"

    async def _ping(self) -> bytes:
        reader, writer = await self._connect()
        try:
            writer.write(b"zPING\0")
            await writer.drain()
            return await self._read_response(reader)
        finally:
            await self._close(writer)

    async def _connect(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        return await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), timeout=self.timeout_seconds
        )

    async def _read_response(self, reader: asyncio.StreamReader) -> bytes:
        response = await asyncio.wait_for(reader.readuntil(b"\0"), timeout=self.timeout_seconds)
        return response.rstrip(b"\0")

    async def _close(self, writer: asyncio.StreamWriter | None) -> None:
        if writer is None:
            return
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass


def build_scanner(settings: StorageSettings, logger: JsonLogger) -> ScannerAdapter:
    """Build the configured scanner at the composition boundary."""

    provider = settings.scanner_provider
    # Directly-created settings from older integrations may only set the
    # legacy command field.  Preserve that behavior without making command
    # execution the default for new configurations.
    if provider == "none" and settings.upload_scan_command:
        provider = "command"
    if provider == "command":
        return CommandScanner(
            settings.upload_scan_command,
            settings.upload_scan_required,
            settings.scanner_timeout_seconds,
        )
    if provider == "clamav":
        return ClamAVScanner(
            settings.scanner_host,
            settings.scanner_port,
            settings.upload_scan_required,
            settings.scanner_timeout_seconds,
            logger,
        )
    return NoopScanner(settings.upload_scan_required)
