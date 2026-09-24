"""High-value API regression flows for the rebuilt backend."""

from __future__ import annotations

import asyncio
import re

from sqlalchemy import select

from app.db.models import UploadRow

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


def csrf_headers(client, **extra):
    return {"X-CSRF-Token": client.cookies.get("lug_csrf", ""), **extra}


def test_health_docs_openapi_and_ready(client):
    assert client.get("/health").status_code == 200
    assert client.get("/healthz").status_code == 200
    assert client.get("/livez").status_code == 200
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    schema = client.get("/openapi.json").json()
    assert "/health" in schema["paths"]
    assert "/api/auth/login" in schema["paths"]
    assert client.get("/api/openapi.json").status_code == 200
    assert client.get("/ready").status_code == 200

    legacy_paths = {
        "/api/config",
        "/api/results",
        "/api/session",
        "/api/sessions",
        "/api/sessions/others",
        "/api/auth/login",
        "/api/auth/request-password-reset",
        "/api/auth/reset-password",
        "/api/auth/logout",
        "/api/auth/register-team",
        "/api/auth/join-team",
        "/api/auth/student-card/stream",
        "/api/auth/student-card/intent",
        "/api/auth/student-card/complete",
        "/api/auth/verify-email",
        "/api/auth/resend-email-code",
        "/api/invites/{code}",
        "/api/dashboard",
        "/api/me",
        "/api/uploads/stream",
        "/api/uploads/intent",
        "/api/uploads/complete",
        "/api/achievements",
        "/api/achievements/{id}",
        "/api/team",
        "/api/team/invite",
        "/api/team/video",
        "/api/notifications",
        "/api/notifications/{id}/read",
        "/api/admin/overview",
        "/api/admin/collections/{resource}",
        "/api/admin/audit",
        "/api/admin/teams/{teamId}/quota",
        "/api/admin/teams/{teamId}/review",
        "/api/admin/teams/{teamId}/members/{userId}",
        "/api/admin/users/{userId}/identity",
        "/api/admin/achievements/{id}/review",
        "/api/admin/videos/{teamId}/review",
        "/api/admin/settings",
        "/api/admin/notifications/broadcast",
        "/healthz",
        "/readyz",
        "/livez",
        "/metrics",
        "/version",
        "/api/openapi.json",
        "/uploads/{filename}",
    }
    assert legacy_paths <= set(schema["paths"])
    assert {"sessionCookie", "csrfHeader", "operationsBearer"} <= set(
        schema["components"]["securitySchemes"]
    )
    assert schema["paths"]["/uploads/{filename}"]["get"]["security"] == [{"sessionCookie": []}]
    assert (
        schema["paths"]["/api/auth/login"]["post"]["responses"]["422"]["content"][
            "application/json"
        ]["schema"]["$ref"]
        == "#/components/schemas/ErrorBody"
    )
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            if method == "parameters":
                continue
            assert "responses" in operation, f"missing responses: {method} {path}"
            assert "422" in operation["responses"], f"missing validation error: {method} {path}"


def test_json_body_limit_is_enforced_before_validation(client):
    client.get("/health")
    response = client.post(
        "/api/auth/login",
        json={"email": "a@example.test", "password": "x" * 5000},
        headers=csrf_headers(client),
    )
    assert response.status_code == 413
    assert response.json()["code"] == "BODY_TOO_LARGE"


def test_csrf_and_admin_login(client):
    rejected = client.post(
        "/api/auth/login", json={"email": "admin@lug.local", "password": "Strong!Admin1"}
    )
    assert rejected.status_code == 403
    assert rejected.json()["code"] == "CSRF_INVALID"
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@lug.local", "password": "Strong!Admin1"},
        headers=csrf_headers(client),
    )
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "admin"
    assert client.get("/api/admin/overview").status_code == 200


def test_registration_upload_verification_dashboard_and_private_file(client):
    captured: dict[str, str] = {}

    async def capture(recipient: str, subject: str, text: str, html: str = ""):
        captured["text"] = text

    client.get("/api/session")
    client.app.state.container.email.send = capture
    upload = client.post(
        "/api/auth/student-card/stream",
        content=PNG,
        headers=csrf_headers(client, **{"X-Upload-Name": "card.png", "Content-Type": "image/png"}),
    )
    assert upload.status_code == 201, upload.text
    upload_data = upload.json()
    registration = client.post(
        "/api/auth/register-team",
        json={
            "fio": "Тестовый капитан",
            "group": "QA-1",
            "teamName": "QA команда",
            "totalStudentsInGroup": 1,
            "email": "captain@example.test",
            "password": "Strong!Test1",
            "messenger": "telegram",
            "messengerContact": "@qa_test",
            "studentCardFile": upload_data["url"],
            "studentCardFileName": "card.png",
            "studentCardUploadToken": upload_data["registrationToken"],
            "studentCardSize": upload_data["size"],
            "studentCardType": upload_data["contentType"],
            "consent": True,
        },
        headers=csrf_headers(client),
    )
    assert registration.status_code == 202, registration.text
    code_match = re.search(r"(\d{6})", captured["text"])
    assert code_match
    verification = client.post(
        "/api/auth/verify-email",
        json={"verificationId": registration.json()["verificationId"], "code": code_match[1]},
        headers=csrf_headers(client),
    )
    assert verification.status_code == 201, verification.text
    dashboard = client.get("/api/dashboard")
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()["team"]["group"] == "QA-1"
    assert client.get(upload_data["url"]).status_code == 200
    assert client.head(upload_data["url"]).status_code == 200

    async def mark_upload_rejected():
        async with client.app.state.container.new_uow() as uow:
            row = await uow.session.scalar(
                select(UploadRow).where(UploadRow.url == upload_data["url"])
            )
            assert row is not None
            row.scan_status = "rejected"

    asyncio.run(mark_upload_rejected())
    blocked = client.get(upload_data["url"])
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "UPLOAD_SCAN_PENDING"
