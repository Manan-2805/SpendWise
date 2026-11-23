# SpendWise frontend API contract

All paths below are relative to `/api/v1`. The local API binds `127.0.0.1:8000` via `make dev`. Use [openapi.json](openapi.json) for generated types and this contract for runtime behavior. `make openapi` calls `app.openapi()` with debug disabled and writes sorted JSON. The HTTP schema URL is `/openapi.json` when debug is enabled. Production rejects debug mode.

## Endpoints

| Method and path | Request | Success |
|---|---|---|
| `POST /auth/register` | `email`, `username`, `password`, `confirm_password` | `201`, token response, auth cookies, verification queued |
| `POST /auth/login` | `email`, `password` | `200`, token response and auth cookies |
| `POST /auth/refresh` | Browser sends the refresh cookie with an empty body. Other clients can send `{ "refresh_token": "…" }`. | `200`, token response and rotated auth cookies |
| `POST /auth/logout` | Authenticated, empty body | `200`, `{ "message": "Successfully logged out" }`, auth cookies cleared |
| `GET /auth/me`, `GET /users/me` | Authenticated | `200`, current user |
| `PATCH /users/me` | Authenticated, changed `email` and/or `username` | `200`, updated user |
| `POST /auth/change-password`, `POST /users/me/password` | Authenticated, `current_password`, `new_password`, `confirm_new_password` | `200`, `{ "message": "…" }`, auth cookies cleared. Prefer the explicitly rate-limited `/auth/change-password`. |
| `POST /auth/forgot-password` | `email` | `200`, same generic message for known and unknown addresses |
| `POST /auth/reset-password` | `token`, `new_password`, `confirm_new_password` | `200`, `{ "message": "Password reset successfully. Please log in again." }`, all sessions revoked |
| `GET /auth/verify-email` | `token` query parameter | `200`, `{ "message": "Email verified successfully." }` |
| `POST /auth/resend-verification` | Authenticated, empty body | `200`, queues a fresh token for an unverified user |
| `GET /transactions/` | Authenticated, optional filters, sort and pagination | `200`, paginated transaction list |
| `POST /transactions/` | Authenticated, transaction create payload | `201`, created transaction |
| `GET /transactions/{id}` | Authenticated | `200`, transaction with category details when present |
| `PATCH /transactions/{id}` | Authenticated, changed fields | `200`, updated transaction |
| `DELETE /transactions/{id}` | Authenticated | `204`, empty body |
| `GET /categories/` | Authenticated, `page` and `per_page` | `200`, category array |
| `POST /categories/` | Authenticated, `name`, `type`, optional `description`, `icon`, `color` | `201`, created category |
| `GET /categories/{id}` | Authenticated | `200`, category |
| `PATCH /categories/{id}` | Authenticated, changed fields | `200`, updated category |
| `DELETE /categories/{id}` | Authenticated, optional `reassign_to_id` query parameter | `204`, empty body |
| `GET /reports/monthly-summary` | Authenticated, optional `year` and `month` (current UTC values by default) | `200`, `year`, `month`, `income`, `expense`, `balance` |
| `GET /reports/category-breakdown` | Authenticated, optional inclusive `date_from`, `date_to`, and `type` (default `expense`) | `200`, array of category totals, counts and percentages |
| `GET /reports/balance-trend` | Authenticated, optional inclusive `date_from`, `date_to`, and `months` (default 12, max 60) | `200`, array of monthly income, expense and balance |
| `GET /health`, `GET /health/live` | Public | `200`, `status` of `ok` or `alive` respectively |
| `GET /health/ready` | Public | `200` when ready, otherwise `503`. Body contains `status`, `db`, `redis` and `celery`. |

Google OAuth and account deletion (`DELETE /users/me`) are outside the frontend scope. Public token operations can return `401 INVALID_TOKEN` for expired or invalid links.

## Browser authentication and origin

The token response is `{ "access_token": "…", "token_type": "bearer", "expires_in": 1800 }` with default settings. The browser uses same-origin cookies. Keep response tokens out of client state, storage and logs. When both are supplied, the API uses the bearer header. An explicit refresh token in the JSON body similarly takes precedence over the refresh cookie.

| Cookie | Path | HttpOnly | SameSite | Secure in dev | Secure in prod | Default Max-Age |
|---|---|---|---|---|---|---|
| `access_token` | `/` | Yes | `Lax` | No | Yes | `1800` seconds (`ACCESS_TOKEN_EXPIRE_MINUTES`, default 30 minutes) |
| `refresh_token` | `/api/v1/auth/refresh` | Yes | `Lax` | No | Yes | `604800` seconds (`REFRESH_TOKEN_EXPIRE_DAYS`, default 7 days) |

Both cookies are host-only. Login, registration, and successful refresh issue both. Logout, password change and an invalid refresh token expire both cookies at their respective paths. Logout and password change revoke all of the user's sessions. Access tokens carry `auth_version`, which is checked on authenticated requests. Password reset also revokes all sessions.

On cookie-authenticated writes, including cookie refresh, `Origin` must exactly match the API's `request.base_url` without its trailing slash or an entry in `CORS_ORIGINS` (default `[]`). If `Origin` is absent, `Sec-Fetch-Site: cross-site` or `same-site` is rejected. An absent `Origin` and absent `Sec-Fetch-Site`, or `Sec-Fetch-Site: same-origin`, pass this gate. `GET`, `HEAD`, and `OPTIONS` bypass it. An untrusted origin gets `403 ACCESS_DENIED`.

Use Vite on port `3000` with `strictPort: true`. Proxy `/api/v1` to `127.0.0.1:8000` and preserve the browser `Host`, so `http://localhost:3000` matches the origin FastAPI sees. `http://localhost:3000` is rejected when sent directly to `http://127.0.0.1:8000` with default settings, as is an unrelated origin. The Vite setup needs no backend configuration change.

For production nginx terminating TLS and forwarding HTTP, the current Granian entry point leaves the API's request scheme as HTTP even with `X-Forwarded-Proto: https`. Cookie-authenticated writes and refresh then return `403` for the public HTTPS origin with an empty allowlist. The minimal production configuration is to set `SPENDWISE_CORS_ORIGINS` to a JSON array containing the exact public HTTPS frontend origin. The browser still uses same-origin URLs. An alternative is a deployment that preserves the HTTPS scheme at the API. The production Compose file already requires `SPENDWISE_FRONTEND_URL`. Any change to the backend origin allowlist, email URL, or SMTP configuration requires approval. [Granian proxy documentation](https://github.com/emmett-framework/granian/blob/master/README.md#proxies-and-forwarded-headers)

## Refresh and sign-out

On the first `401` from an authenticated request, coordinate one `POST /auth/refresh` across concurrent callers. A missing refresh cookie returns `400` with `detail: "Refresh token is required"`. An invalid or reused token returns `401 INVALID_TOKEN` and clears both cookies. When two requests use the same valid refresh token in parallel, one returns `200` with a successor and the other returns `401` and revokes the entire refresh family, including the successor. The newly issued access token can still be valid until expiry because reuse revokes the refresh family without incrementing `auth_version`. Cookie responses can arrive in either order. Share the refresh across requests and coordinate across tabs where possible.

After a successful refresh, retry an eligible read once. For a failed `POST`, `PATCH` or `DELETE`, keep the user's input and require an explicit resubmission. If refresh fails or the retried read returns `401`, clear account state and account-scoped query data, then send the user to login. Public login failures and invalid verification or reset links are handled by their own screens. Email verification consumes the token despite using `GET`, so it is excluded from automatic replays.

## Profile and email

An active unverified user can sign in, refresh, sign out, read and update their profile, change their password, resend verification, and read or write transactions and categories and read reports. The backend has a verification-required dependency that returns `403 EMAIL_NOT_VERIFIED`, but none of these routes uses it. A verification link requires the token regardless of login status. Resend sends email only for an unverified account.

Changing to a different normalized email via `PATCH /users/me` returns `200` and the full user object, with keys `id`, `email`, `username`, `is_active`, `is_verified`, and `created_at`. The new email is lowercase and `is_verified` is `false`. The response has no `Set-Cookie` header and queues no verification message. The previous access cookie then fails authentication and the previous refresh token can no longer obtain a session. Show that the email was updated, clear cached account data, and send the user to login with the new email. After login, offer `POST /auth/resend-verification`. Saving the same normalized email does not revoke sessions.

Email and username comparisons and stored values are normalized to lowercase. Usernames are 3–50 characters using ASCII letters, digits, `_` and `-`. Password inputs use a 72 UTF-8 byte ceiling. New passwords require at least 8 characters, an ASCII uppercase and lowercase letter, and a digit. Confirmation must match. Show model-level errors by the form or map a known confirmation error to the confirmation field.

### Verification and reset links

Celery sends `${FRONTEND_URL}/verify-email?token=…` and `${FRONTEND_URL}/reset-password?token=…` with a URL-encoded, single-use token. The default `FRONTEND_URL` is `http://localhost:3000`. Verification tokens last 24 hours and reset tokens last one hour. The frontend verification route calls the API GET with the token. The frontend reset route submits the token with the new password and confirmation to the API POST.

If `SMTP_HOST` or `SMTP_FROM` is unset, the worker skips delivery. The API has no endpoint that returns an email link, and the database stores only a hash. For local manual testing, configure an SMTP catcher or sandbox such as Mailtrap after approval. With SMTP disabled, use a disposable test fixture that captures the task argument in memory before Celery delivery, as the reset integration test does. No email tooling or configuration was added.

## Lists, dates, and amounts

- Both list endpoints use 1-based `page` and `per_page` (default 20, maximum 100). Transactions return `items`, `total`, `page`, `per_page`, `pages`, `has_next`, and `has_prev`. With zero matches `pages` is `0`.
- Categories return a plain array ordered by `name`, then `id`. To load all categories, request successive pages with `per_page=100` until a page contains fewer than 100 rows. An exact multiple takes a final empty page. Offset pagination reflects changes made between requests. Invalidate and reload after category writes. System rows have `user_id: null` and are read-only. Deleting an owned category with active transactions requires a compatible reassignment target, or the API returns `409`.
- Transaction filters are `date_from`, `date_to`, `category_id`, `type`, `min_amount`, `max_amount`, and `search`. Search is a case-insensitive literal substring of the description (max 100 characters). Sorting uses `sort_by=transaction_date|amount|created_at` and `sort_order=asc|desc`, defaulting to `transaction_date` descending. Use `created_at` descending for recently added activity. Validate ordered date and amount ranges before sending them.
- Create requires positive `amount` (up to 12 digits and 2 decimal places), nonblank `description`, `transaction_date`, positive `category_id`, and `type` (`income` or `expense`). The category must be accessible and compatible with the type. `notes` can be null and `tags` default to an empty array. Responses can contain null `description`, `category_id`, `category`, and `notes`. Omit unchanged fields on PATCH. Explicit null clears `category_id` and `notes`. It fails for `amount`, `description`, `transaction_date`, `type`, and `tags`. Category name and type and profile email and username also reject explicit null on PATCH.
- Transaction dates use `YYYY-MM-DD`. Report ranges are inclusive, ordered, limited to five years, and bounded by 1900–2100. Category breakdown defaults to an end date of today in UTC and a start date 30 days earlier. `Uncategorized` can appear with `category_id: null`. Report category color and icon can also be null.
- Send amounts as decimal strings. Transaction amounts and report totals and balances come back as decimal strings. Keep money calculations exact, using decimal strings or integer minor units. `percentage` is a separate numeric presentation field. The API does not return a currency code.

## Runtime errors and retries

All frontend requests use one error parser. Normalize HTTP status, `code`, a user-facing message, field errors, request ID, and any retry delay. Use a friendly fallback for a network failure, non-JSON body or unrecognized shape. A `204` has no body to parse.

| Runtime response | Client handling |
|---|---|
| Domain error `{ "detail": "…", "code": "…", "request_id": "…" }` | Use the status and code. `request_id` can be null. Fall back to `X-Correlation-ID` for support. |
| Request validation `422` with `{ "detail": "Request validation failed", "code": "VALIDATION_ERROR", "errors": [{ "field": "…", "message": "…", "type": "…" }] }` | Bind known fields to controls. Paths are dot-separated and the `body` segment is removed. An empty or unmapped field belongs at form level. |
| Other failures such as `{ "detail": "…" }` or `{ "detail": "…", "code": "CONFLICT" }` | Show the available message at form or screen level. The latter can be `409` or `422` with no field list. |
| `429 RATE_LIMIT_EXCEEDED` | Show a rate limit message. Use a positive delay if supplied in `retry_after` (often `null`) or a valid retry header if one is available. Leave the request for the user to retry. |
| Overload `503 OVERLOADED` with `Retry-After` (integer seconds, default 1) | Show a friendly waiting message. Wait for the delay and retry only safe GETs with a bounded, cancellable policy. Keep writes and the verification GET manual. |
| Readiness `503` with `{ "status": "not_ready", "db": "…", "redis": "…", "celery": "…" }` | Treat this as a health failure without the overload retry contract. |

The limiter uses client address and fixed windows. The default is 200/minute. Auth overrides are register 3/minute, login 5/minute, refresh 10/minute, forgot/reset/change-password 3/minute each, and verification resend 2/minute. Health endpoints are exempt from rate limiting and request admission. Overload can come from request admission, database pool contention or login capacity.

### Known API doc gaps

- OpenAPI omits `429` responses. The runtime handler returns `RATE_LIMIT_EXCEEDED` and an optional JSON `retry_after`, with no `Retry-After` header.
- OpenAPI advertises FastAPI's default `HTTPValidationError` with a `detail` array. The runtime `422` validation response uses string `detail`, `code`, and a separate `errors` array. Runtime errors such as `401`, `403`, `404`, and `409` also have route-specific cases that the generated schema does not enumerate.
- OpenAPI describes `Retry-After` on overload `503` responses. Readiness can return a separate `503` without `Retry-After`, and its current schema only documents `200`.
- The schema advertises bearer security and points its OAuth token URL at login. Browser cookie auth is supported and login takes JSON.

## Screen gap table

| Screen | Endpoints needed | Status |
|---|---|---|
| Register | `POST /auth/register` | OK |
| Login and logout | `POST /auth/login`, `/auth/refresh`, `/auth/logout`; `GET /auth/me` | OK. Production cookie writes and refresh need the origin configuration above for TLS termination with an HTTP upstream. |
| Verify email | `GET /auth/verify-email`; `POST /auth/resend-verification` | OK. Live delivery depends on SMTP configuration. |
| Forgot and reset password | `POST /auth/forgot-password`, `/auth/reset-password` | OK. Live delivery depends on SMTP configuration. |
| Dashboard | `GET /reports/monthly-summary`, `/reports/category-breakdown`, `/transactions/` | OK |
| Transactions | `GET` and `POST /transactions/`; `GET`, `PATCH`, and `DELETE /transactions/{id}` | OK |
| Categories | `GET` and `POST /categories/`; `GET`, `PATCH`, and `DELETE /categories/{id}` | OK |
| Profile | `GET` and `PATCH /users/me`; `POST /auth/resend-verification` after email change and sign-in | OK |
| Change password | `POST /auth/change-password` | OK |

### Verification

The existing integration tests cover refresh rotation and concurrent reuse, cookie origin rejection, email verification and reset, rate limiting, and overload. Disposable contract probes checked the origin matrix against Granian, both development cookies over HTTP, the category page limit, unverified-user access, transaction field validation and nullable responses, and the email-change response and subsequent login. A response-header test exercised the production branch of the cookie writer. SMTP delivery and the future nginx deployment were outside these checks.
