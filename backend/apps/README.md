# App boundaries

Phases 2–4 implement the database, REST API, and authentication layers. Each
app owns one part of the domain so later frontend work does not require an
all-in-one refactor.

| App | Responsibility | Implemented |
| --- | --- | --- |
| `core` | Health check, shared slug/upload/validator helpers, admin previews | Yes (no models) |
| `wallpapers` | Wallpaper records, image sources, metadata, source/licence fields | `Wallpaper` |
| `catalog` | Categories and tags, with wallpaper relationships | `Category`, `Tag` |
| `library` | Per-user likes and saved wallpapers | `Like`, `SavedWallpaper` |
| `accounts` | allauth adapters, the authenticated profile endpoint, auth tests | Phase 4 (`/api/v1/auth/me/`) |
| `api` | Serializers, viewsets, routers, filtering, pagination, versioned URL routes | Phase 3 (`/api/v1/`) |

## Relationships

- `Wallpaper.category` is required and uses `PROTECT`, so deleting a category
  with wallpapers fails instead of silently orphaning records.
- `Wallpaper.tags` is a many-to-many relation; tags are reusable and deleting a
  tag does not delete its wallpapers.
- `Like` and `SavedWallpaper` reference `settings.AUTH_USER_MODEL` and
  `Wallpaper` with `CASCADE`, plus unique `(user, wallpaper)` constraints.

## Dependencies between apps

- `wallpapers` depends on `catalog` (category/tag).
- `library` depends on `wallpapers` and Django's configured user model.
- `api` contains no models; it serializes the models above and exposes them at
  `/api/v1/`. It is imported by `config/urls.py`.
- `accounts` depends on Django's user model and allauth; it adds the
  `UserProfileSerializer` and `MeView` on top of allauth Headless, which
  provides the actual login, token, and provider endpoints under `/_allauth/`.
- `api` mounts `apps.accounts.urls` at `/api/v1/auth/`.

django-allauth is active in `INSTALLED_APPS` with the `headless` and
`socialaccount` extras. Its URL namespace is mounted in `config/urls.py`, and
its tables are part of the normal migration graph. Google credentials come from
the environment only; without them Google is unavailable and no provider is
advertised.
