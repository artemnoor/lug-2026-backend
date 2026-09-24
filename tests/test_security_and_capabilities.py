"""Authorization, object policy, and cross-module capability regressions."""

from __future__ import annotations

import re

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


def _csrf(client, **extra):
    return {"X-CSRF-Token": client.cookies.get("lug_csrf", ""), **extra}


def _register(client, email: str, fio: str = "Капитан тестовой команды") -> dict:
    captured: dict[str, str] = {}

    async def capture(recipient: str, subject: str, text: str, html: str = ""):
        captured["text"] = text

    client.get("/api/session")
    client.app.state.container.email.send = capture
    upload = client.post(
        "/api/auth/student-card/stream",
        content=PNG,
        headers=_csrf(client, **{"X-Upload-Name": "card.png", "Content-Type": "image/png"}),
    )
    assert upload.status_code == 201, upload.text
    upload_data = upload.json()
    registration = client.post(
        "/api/auth/register-team",
        json={
            "fio": fio,
            "group": "SEC-1",
            "teamName": "Security Team",
            "totalStudentsInGroup": 1,
            "email": email,
            "password": "Strong!Test1",
            "messenger": "telegram",
            "messengerContact": "@security_test",
            "studentCardFile": upload_data["url"],
            "studentCardFileName": "card.png",
            "studentCardUploadToken": upload_data["registrationToken"],
            "studentCardSize": upload_data["size"],
            "studentCardType": upload_data["contentType"],
            "consent": True,
        },
        headers=_csrf(client),
    )
    assert registration.status_code == 202, registration.text
    code = re.search(r"(\d{6})", captured["text"])
    assert code
    verified = client.post(
        "/api/auth/verify-email",
        json={"verificationId": registration.json()["verificationId"], "code": code[1]},
        headers=_csrf(client),
    )
    assert verified.status_code == 201, verified.text
    return verified.json()["user"]


def test_anonymous_and_participant_authorization(client):
    assert client.get("/api/dashboard").status_code == 401
    assert client.get("/api/admin/overview").status_code == 401
    invalid_upload = client.post(
        "/api/auth/student-card/stream",
        content=PNG,
        headers=_csrf(client, **{"X-Upload-Name": "..\\escape.png", "Content-Type": "image/png"}),
    )
    assert invalid_upload.status_code == 422
    user = _register(client, "participant@example.test")

    assert user["role"] == "participant"
    assert client.get("/api/admin/overview").status_code == 403

    profile = client.patch("/api/me", json={"fio": "Обновлённый капитан"}, headers=_csrf(client))
    assert profile.status_code == 200, profile.text
    assert profile.json()["user"]["fio"] == "Обновлённый капитан"

    mass_assignment = client.patch("/api/me", json={"role": "admin"}, headers=_csrf(client))
    assert mass_assignment.status_code == 422

    video = client.patch(
        "/api/team/video",
        json={"url": "https://rutube.ru/video/abc123"},
        headers=_csrf(client),
    )
    assert video.status_code == 200, video.text
    assert video.json()["videoCard"]["status"] == "pending"

    achievement = client.post(
        "/api/achievements",
        json={
            "title": "Security award",
            "direction": "science",
            "category": "Research",
            "details": "Evidence",
        },
        headers=_csrf(client),
    )
    assert achievement.status_code == 201, achievement.text


def test_admin_review_and_notification_visibility(client):
    participant = _register(client, "review-target@example.test")
    client.get("/api/dashboard")
    achievement = client.post(
        "/api/achievements",
        json={
            "title": "Reviewable achievement",
            "direction": "culture",
            "category": "Stage",
        },
        headers=_csrf(client),
    )
    assert achievement.status_code == 201, achievement.text
    achievement_id = achievement.json()["achievement"]["id"]

    admin_login = client.post(
        "/api/auth/login",
        json={"email": "admin@lug.local", "password": "Strong!Admin1"},
        headers=_csrf(client),
    )
    assert admin_login.status_code == 200, admin_login.text
    team_id = participant["teamId"]
    assert (
        client.patch(
            f"/api/admin/teams/{team_id}/quota",
            json={"confirmed": True},
            headers=_csrf(client),
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/admin/teams/{team_id}/review",
            json={"field": "name", "status": "approved"},
            headers=_csrf(client),
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/admin/users/{participant['id']}/identity",
            json={"status": "approved"},
            headers=_csrf(client),
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/admin/videos/{team_id}/review",
            json={
                "status": "approved",
                "criteriaScores": {"topic": 8, "creativity": 8, "quality": 5, "vfx": 2},
            },
            headers=_csrf(client),
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/admin/achievements/{achievement_id}/review",
            json={"status": "approved", "points": 7},
            headers=_csrf(client),
        ).status_code
        == 200
    )

    broadcast = client.post(
        "/api/admin/notifications/broadcast",
        json={"targetType": "all", "title": "Notice", "message": "Review complete"},
        headers=_csrf(client),
    )
    assert broadcast.status_code == 201, broadcast.text

    participant_login = client.post(
        "/api/auth/login",
        json={"email": "review-target@example.test", "password": "Strong!Test1"},
        headers=_csrf(client),
    )
    assert participant_login.status_code == 200, participant_login.text
    notifications = client.get("/api/notifications")
    assert notifications.status_code == 200
    assert any(item["title"] == "Notice" for item in notifications.json()["notifications"])
