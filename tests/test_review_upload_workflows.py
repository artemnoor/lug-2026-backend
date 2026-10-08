"""End-to-end API workflows for consent, uploads, and organizer rejections."""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.db.models import UploadRow, UserRow

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


def _csrf(client, **extra):
    return {"X-CSRF-Token": client.cookies.get("lug_csrf", ""), **extra}


def _register(client, email: str, *, consent: bool = True, group: str = "QA-1") -> dict:
    client.get("/api/session")
    upload = client.post(
        "/api/auth/student-card/stream",
        content=PNG,
        headers=_csrf(client, **{"X-Upload-Name": "student-card.png", "Content-Type": "image/png"}),
    )
    assert upload.status_code == 201, upload.text
    document = upload.json()
    registration = client.post(
        "/api/auth/register-team",
        json={
            "fio": "Участник тестовой команды",
            "group": group,
            "teamName": f"Команда {group}",
            "totalStudentsInGroup": 1,
            "email": email,
            "password": "password123",
            "messenger": "telegram",
            "messengerContact": "@workflow_test",
            "studentCardFile": document["url"],
            "studentCardFileName": document["name"],
            "studentCardUploadToken": document["registrationToken"],
            "studentCardSize": document["size"],
            "studentCardType": document["contentType"],
            "consent": consent,
        },
        headers=_csrf(client),
    )
    return {"response": registration, "upload": document}


def _admin_login(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@lug.local", "password": "Strong!Admin1"},
        headers=_csrf(client),
    )
    assert response.status_code == 200, response.text


def test_registration_requires_consent_and_persists_acceptance(client):
    denied = _register(client, "no-consent@example.test", consent=False)
    assert denied["response"].status_code == 422
    assert denied["response"].json()["code"] == "REQUIRED_FIELDS_INVALID"
    assert "lug_session" not in client.cookies

    accepted = _register(client, "consent@example.test", group="CONSENT-1")
    assert accepted["response"].status_code == 201, accepted["response"].text
    user_id = accepted["response"].json()["user"]["id"]
    upload_url = accepted["upload"]["url"]

    async def read_persisted_consent():
        async with client.app.state.container.new_uow() as uow:
            user = await uow.session.scalar(select(UserRow).where(UserRow.id == user_id))
            upload = await uow.session.scalar(select(UploadRow).where(UploadRow.url == upload_url))
            return user.consent_at, upload.owner_user_id

    consent_at, owner_id = asyncio.run(read_persisted_consent())
    assert consent_at is not None
    assert owner_id == user_id


def test_registration_document_upload_rejects_unsafe_names_types_and_fake_content(client):
    client.get("/api/session")

    unsafe_name = client.post(
        "/api/auth/student-card/stream",
        content=PNG,
        headers=_csrf(client, **{"X-Upload-Name": "../escape.png", "Content-Type": "image/png"}),
    )
    assert unsafe_name.status_code == 422
    assert unsafe_name.json()["code"] == "UPLOAD_INVALID_NAME"

    unsupported_type = client.post(
        "/api/auth/student-card/stream",
        content=b"not a document",
        headers=_csrf(
            client, **{"X-Upload-Name": "card.exe", "Content-Type": "application/octet-stream"}
        ),
    )
    assert unsupported_type.status_code == 422
    assert unsupported_type.json()["code"] == "UPLOAD_INVALID_TYPE"

    fake_png = client.post(
        "/api/auth/student-card/stream",
        content=b"not a png",
        headers=_csrf(client, **{"X-Upload-Name": "card.png", "Content-Type": "image/png"}),
    )
    assert fake_png.status_code == 422
    assert fake_png.json()["code"] == "UPLOAD_MAGIC_MISMATCH"


def test_authenticated_upload_checks_access_metadata_and_declared_size(client):
    client.get("/api/session")
    anonymous = client.post(
        "/api/uploads/stream",
        content=PNG,
        headers=_csrf(
            client,
            **{
                "X-Upload-Name": "proof.png",
                "Content-Type": "image/png",
                "X-Upload-Kind": "attachment",
            },
        ),
    )
    assert anonymous.status_code == 401

    registration = _register(client, "upload-validation@example.test")
    assert registration["response"].status_code == 201, registration["response"].text

    unsafe_name = client.post(
        "/api/uploads/stream",
        content=PNG,
        headers=_csrf(
            client,
            **{
                "X-Upload-Name": "../proof.png",
                "Content-Type": "image/png",
                "X-Upload-Kind": "attachment",
            },
        ),
    )
    assert unsafe_name.status_code == 422
    assert unsafe_name.json()["code"] == "UPLOAD_INVALID_NAME"

    invalid_kind = client.post(
        "/api/uploads/stream",
        content=PNG,
        headers=_csrf(
            client,
            **{
                "X-Upload-Name": "proof.png",
                "Content-Type": "image/png",
                "X-Upload-Kind": "executable",
            },
        ),
    )
    assert invalid_kind.status_code == 422
    assert invalid_kind.json()["code"] == "UPLOAD_INVALID_KIND"

    wrong_size = client.post(
        "/api/uploads/stream",
        content=PNG,
        headers=_csrf(
            client,
            **{
                "X-Upload-Name": "proof.png",
                "Content-Type": "image/png",
                "X-Upload-Kind": "attachment",
                "Content-Length": "12",
            },
        ),
    )
    assert wrong_size.status_code == 422, wrong_size.text
    assert wrong_size.json()["code"] == "UPLOAD_SIZE_MISMATCH"


def test_registration_rejects_tampered_document_upload_claim(client):
    client.get("/api/session")
    uploaded = client.post(
        "/api/auth/student-card/stream",
        content=PNG,
        headers=_csrf(client, **{"X-Upload-Name": "student-card.png", "Content-Type": "image/png"}),
    )
    assert uploaded.status_code == 201, uploaded.text
    document = uploaded.json()
    response = client.post(
        "/api/auth/register-team",
        json={
            "fio": "Попытка подмены",
            "group": "CLAIM-1",
            "teamName": "Поддельная заявка",
            "totalStudentsInGroup": 1,
            "email": "tampered-claim@example.test",
            "password": "password123",
            "messenger": "telegram",
            "messengerContact": "@claim_test",
            "studentCardFile": document["url"],
            "studentCardFileName": document["name"],
            "studentCardUploadToken": document["registrationToken"] + "tampered",
            "studentCardSize": document["size"],
            "studentCardType": document["contentType"],
            "consent": True,
        },
        headers=_csrf(client),
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "REGISTRATION_UPLOAD_CLAIM_INVALID"
    assert "lug_session" not in client.cookies


def test_portfolio_attachment_is_owned_and_cannot_be_reused_by_another_team(client):
    first = _register(client, "first-owner@example.test")
    assert first["response"].status_code == 201, first["response"].text
    attachment = client.post(
        "/api/uploads/stream",
        content=PNG,
        headers=_csrf(
            client,
            **{
                "X-Upload-Name": "proof.png",
                "Content-Type": "image/png",
                "X-Upload-Kind": "attachment",
            },
        ),
    )
    assert attachment.status_code == 201, attachment.text
    file_url = attachment.json()["url"]
    own_material = client.post(
        "/api/achievements",
        json={
            "title": "Собственная работа",
            "direction": "science",
            "category": "Исследование",
            "fileUrl": file_url,
        },
        headers=_csrf(client),
    )
    assert own_material.status_code == 201, own_material.text
    assert own_material.json()["achievement"]["fileUrl"] == file_url

    client.post("/api/auth/logout", headers=_csrf(client))
    second = _register(client, "second-owner@example.test", group="QA-2")
    assert second["response"].status_code == 201, second["response"].text
    foreign_material = client.post(
        "/api/achievements",
        json={
            "title": "Чужой файл",
            "direction": "science",
            "category": "Исследование",
            "fileUrl": file_url,
        },
        headers=_csrf(client),
    )
    assert foreign_material.status_code == 403
    assert foreign_material.json()["code"] == "UPLOAD_NOT_OWNED"


def test_admin_rejections_require_comments_and_return_them_to_participant(client):
    registration = _register(client, "review-workflow@example.test")
    assert registration["response"].status_code == 201, registration["response"].text
    participant = registration["response"].json()["user"]
    team_id = participant["teamId"]

    achievement = client.post(
        "/api/achievements",
        json={"title": "Материал на проверку", "direction": "science", "category": "Наука"},
        headers=_csrf(client),
    )
    assert achievement.status_code == 201, achievement.text
    achievement_id = achievement.json()["achievement"]["id"]

    video = client.patch(
        "/api/team/video",
        json={"url": "https://rutube.ru/video/abc123"},
        headers=_csrf(client),
    )
    assert video.status_code == 200, video.text

    _admin_login(client)
    review_targets = [
        (f"/api/admin/teams/{team_id}/review", {"field": "name", "status": "rejected"}),
        (f"/api/admin/users/{participant['id']}/identity", {"status": "rejected"}),
        (f"/api/admin/achievements/{achievement_id}/review", {"status": "rejected"}),
        (f"/api/admin/videos/{team_id}/review", {"status": "rejected"}),
    ]
    for path, payload in review_targets:
        response = client.patch(path, json=payload, headers=_csrf(client))
        assert response.status_code == 422, response.text
        assert response.json()["code"] == "REVIEW_COMMENT_REQUIRED"

    comment = "Пожалуйста, исправьте документ и отправьте повторно."
    accepted_responses = []
    for path, payload in review_targets:
        response = client.patch(path, json={**payload, "comment": comment}, headers=_csrf(client))
        assert response.status_code == 200, response.text
        accepted_responses.append(response.json())

    assert accepted_responses[0]["team"]["reviewComment"] == comment
    assert accepted_responses[0]["team"]["reviewNameStatus"] == "rejected"
    assert accepted_responses[1]["user"]["identityComment"] == comment
    assert accepted_responses[2]["achievement"]["reviewComment"] == comment
    assert accepted_responses[3]["videoCard"]["comment"] == comment

    audit = client.get("/api/admin/audit")
    assert audit.status_code == 200
    assert "team.reviewed" in {item["action"] for item in audit.json()["auditLog"]}

    client.post("/api/auth/logout", headers=_csrf(client))
    login = client.post(
        "/api/auth/login",
        json={"email": "review-workflow@example.test", "password": "password123"},
        headers=_csrf(client),
    )
    assert login.status_code == 200, login.text
    dashboard = client.get("/api/dashboard")
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()["user"]["identityComment"] == comment
    assert dashboard.json()["team"]["reviewComment"] == comment
    assert dashboard.json()["team"]["reviewNameStatus"] == "rejected"
    assert dashboard.json()["achievements"][0]["reviewComment"] == comment
    assert dashboard.json()["team"]["videoCard"]["comment"] == comment
