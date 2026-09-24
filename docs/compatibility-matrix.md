# LUG 2026 API compatibility matrix

Status values: `compatible` means the new implementation preserves the observed
external behavior; `intentional-change` means a safer/clearer behavior is
documented and covered by a regression test. `planned` is retained for future
capabilities only; all observed rows below are implemented.

The reference contains 47 unique non-HEAD operations and one additional HEAD
operation on `/uploads/{filename}`.

## Public and session/auth operations

| Old method + path | Observed behavior / contract | New module and operation | Status / reason |
| --- | --- | --- | --- |
| `GET /api/config` | Public `{settings}` projection; cacheable/ETag | `content.get_public_config` | compatible; preserve fields/cache |
| `GET /api/results` | Public published flag, available time, admitted scored teams | `content.get_results` | compatible; preserve admission/score rules |
| `GET /api/session` | Anonymous-safe `{user:null}` or safe user projection | `auth.get_current_session` | compatible; preserve anonymous response |
| `GET /api/sessions` | Authenticated current user's other sessions | `auth.list_sessions` | compatible; typed response |
| `DELETE /api/sessions/others` | Revoke sessions except current token | `auth.revoke_other_sessions` | compatible; one transaction |
| `POST /api/auth/login` | Email/password; `200`, session cookie; `401` generic error; rate limits | `auth.login` | compatible; preserve cookie/error |
| `POST /api/auth/request-password-reset` | Generic `202`, HMAC reset code delivery | `auth.request_password_reset` | compatible; avoid account enumeration |
| `POST /api/auth/reset-password` | Code/password reset; revoke sessions; `200` | `auth.reset_password` | compatible; preserve one-time code |
| `POST /api/auth/logout` | Revoke current session; clear cookie; `200` | `auth.logout` | compatible; preserve idempotence |
| `POST /api/auth/register-team` | Pending registration; `202` with verification ID; no raw password/code persistence | `teams.begin_registration` | compatible; preserve repeat semantics |
| `POST /api/auth/join-team` | Pending participant invite registration; `202` | `teams.begin_join` | compatible; preserve invite policy |
| `POST /api/auth/student-card/stream` | Anonymous bounded image stream; `201` upload + registration claim | `media.registration_stream` | compatible; preserve claim |
| `POST /api/auth/student-card/intent` | Anonymous multipart intent; `201` claim | `media.registration_intent` | compatible; async Redis state |
| `POST /api/auth/student-card/complete` | Claimed multipart completion; `201` upload + refreshed claim | `media.registration_complete` | compatible; verify claim/owner |
| `POST /api/auth/verify-email` | Code verification; creates user/session; `201` | `auth.verify_email` | compatible; preserve HMAC/attempts |
| `POST /api/auth/resend-email-code` | Refresh code for pending registration; `200` | `auth.resend_email_code` | compatible; preserve cooldown |
| `GET /api/invites/{code}` | Public active, unexpired invite projection; `404`/rate limit | `teams.get_invite` | compatible; preserve normalization |

## Participant operations

| Old method + path | Observed behavior / contract | New module and operation | Status / reason |
| --- | --- | --- | --- |
| `GET /api/dashboard` | Authenticated dashboard: user/team/members/achievements/notifications/settings | `teams.get_dashboard` | compatible; preserve frontend projection |
| `PATCH /api/me` | Explicit profile fields; student card replacement resets identity | `users.update_profile` | compatible; typed allowlist |
| `POST /api/uploads/stream` | Authenticated raw stream; `201` upload; owner/rate/quota checks | `media.stream_upload` | compatible; scan-gated access |
| `POST /api/uploads/intent` | Authenticated multipart intent; `201` | `media.create_intent` | compatible; private storage |
| `POST /api/uploads/complete` | Authenticated multipart completion; `201` | `media.complete_upload` | compatible; validate parts/owner |
| `POST /api/achievements` | Captain/participant material create within portfolio window; `201` | `portfolio.create_achievement` | compatible; preserve pending review |
| `DELETE /api/achievements/{id}` | Owner delete; `200`; object policy | `portfolio.delete_achievement` | compatible; explicit ownership |
| `PATCH /api/team` | Captain-only team profile update; `200 {team}` | `teams.update_team` | compatible; policy centralized |
| `POST /api/team/invite` | Captain rotates invite; `200` invite projection | `teams.rotate_invite` | compatible; preserve expiry |
| `PATCH /api/team/video` | Captain video submission within window; `200 {videoCard}` | `video.update_team_video` | compatible; provider validation |
| `GET /api/notifications` | Authenticated audience-filtered notifications | `notifications.list_for_user` | compatible; read join table |
| `PATCH /api/notifications/{id}/read` | Mark visible notification read; `200`/`404` | `notifications.mark_read` | compatible; object policy |

## Admin operations

| Old method + path | Observed behavior / contract | New module and operation | Status / reason |
| --- | --- | --- | --- |
| `GET /api/admin/overview` | Admin snapshot of settings, teams, users, achievements, videos, notifications, audit | `admin.get_overview` | compatible; façade over read ports |
| `GET /api/admin/collections/{resource}` | Admin paginated users/teams/achievements with limit/offset/query/status | `admin.list_collection` | compatible; typed resource enum |
| `GET /api/admin/audit` | Admin bounded audit log | `admin.list_audit` | compatible; retention documented |
| `PATCH /api/admin/teams/{teamId}/quota` | Admin quota confirmation; `200 {team}` | `admin.confirm_team_quota` -> `teams` | compatible; no admin repository |
| `PATCH /api/admin/teams/{teamId}/review` | Admin team field/status review; `200 {team}` | `admin.review_team` -> `teams` | compatible; domain transition |
| `DELETE /api/admin/teams/{teamId}/members/{userId}` | Admin remove member; conflict/captain rules | `admin.remove_member` -> `teams` | compatible; one policy |
| `PATCH /api/admin/users/{userId}/identity` | Admin identity status/comment review; `200 {user}` | `admin.review_identity` -> `users` | compatible; review use case |
| `PATCH /api/admin/achievements/{id}/review` | Admin achievement status/points/comment; `200` | `admin.review_achievement` -> `portfolio` | compatible; criteria validation |
| `PATCH /api/admin/videos/{teamId}/review` | Admin video status/criteria scores; `200 {videoCard}` | `admin.review_video` -> `video` | compatible; bounded scores |
| `PATCH /api/admin/settings` | Admin schedule/content/limits update; `200 {settings}` | `admin.update_settings` -> `content` | compatible; date/range validation |
| `POST /api/admin/notifications/broadcast` | Admin audience broadcast; `201`; chat kind rejected | `admin.broadcast` -> `notifications` | compatible; notification is persisted and email uses the configured adapter |

## Operations and private file delivery

| Old method + path | Observed behavior / contract | New module and operation | Status / reason |
| --- | --- | --- | --- |
| `GET /healthz` | Process health projection | `operations.healthz` alias of `/health` | compatible; compatibility alias |
| `GET /readyz` | Dependency readiness; operations auth/loopback in reference | `operations.readyz` alias of `/ready` | compatible; clear `503` semantics |
| `GET /metrics` | Prometheus text; operations access | `operations.metrics` | compatible; bounded labels |
| `GET /livez` | Lightweight liveness | `operations.livez` | compatible; preserve |
| `GET /version` | Service/build metadata | `operations.version` | compatible; preserve |
| `GET /api/openapi.json` | Checked-in legacy contract | generated OpenAPI compatibility alias | compatible; generated alias intentionally replaces the checked-in weak schema |
| `GET /uploads/{filename}` | Authenticated private owner/team/admin delivery or redirect to signed URL | `media.read_private_upload` | intentional-change; pending/rejected files are no longer readable before clean scan |
| `HEAD /uploads/{filename}` | Same object policy with headers only | `media.head_private_upload` | compatible; preserve method |

## Target additions and intentional changes

| New endpoint/behavior | Reason | Verification |
| --- | --- | --- |
| `GET /health` | User explicitly requires process liveness endpoint | API smoke |
| `GET /ready` | Separate readiness semantics from process health | DB/Redis readiness tests |
| `GET /docs`, `GET /redoc`, `GET /openapi.json` | Useful generated Swagger/ReDoc explicitly required | OpenAPI contract test |
| Structured internal `AppError` with legacy-compatible wire serialization | Enables typed error mapping without breaking current frontend parser | error/unit/API tests |
| Upload reads require clean scan status | closes reference lifecycle ambiguity; unsafe pending/rejected files stay private | BOLA/scan regression tests |
| SQLAlchemy/UoW transaction ownership | eliminates hidden repository commits and JSONB core-field fallback | migration/repository integration tests |
