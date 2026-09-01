import re
from pathlib import Path

REPOSITORY = Path(__file__).parents[2]
OLD_BRAND = re.compile("abd" + r"\s*" + "wash|adb" + r"\s*" + "wash", re.IGNORECASE)

SCANNED_ROOTS = (
    REPOSITORY / "README.md",
    REPOSITORY / "apps",
    REPOSITORY / "backend",
    REPOSITORY / "docs",
    REPOSITORY / "package.json",
    REPOSITORY / "package-lock.json",
    REPOSITORY / "packages",
    REPOSITORY / "supabase",
)

IGNORED_PARTS = {
    ".git",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".gradle",
    ".cxx",
    ".expo",
    "coverage",
    "htmlcov",
    "build",
    "dist",
    "node_modules",
}

# Each exception is a deployed identifier, immutable migration history, a data-cleanup
# match, or a negative regression assertion. The implications are documented in README.
ALLOWED_BY_PATH: dict[str, tuple[str, ...]] = {
    "README.md": (
        "com.abdwash.staff",
        "abdwash-staff",
        "abdwash:",
        "staff.abdwash.local",
        "`abdwash`",
        "abdwash.vercel.app",
        "abdwash-vdtc.vercel.app",
        "abdwash-notification-dispatch",
        "abdwash_outbox_dispatch_url",
        "abdwash_outbox_dispatch_secret",
    ),
    "apps/mobile/.env.example": ("abdwash.vercel.app",),
    "apps/mobile/app.json": ("abdwash-staff", "com.abdwash.staff"),
    "apps/mobile/android/app/build.gradle": ("com.abdwash.staff",),
    "apps/mobile/android/app/src/main/java/com/abdwash/staff/MainActivity.kt": (
        "com.abdwash.staff",
    ),
    "apps/mobile/android/app/src/main/java/com/abdwash/staff/MainApplication.kt": (
        "com.abdwash.staff",
    ),
    "apps/mobile/src/android-ime-plugin.test.js": ("com.abdwash.staff",),
    "apps/mobile/src/cache/queryClient.tsx": ("abdwash:operations-query-cache:",),
    "apps/mobile/src/cache/sync.ts": ("abdwash:sync-revisions:",),
    "apps/mobile/src/staff-login.ts": ("staff.abdwash.local",),
    "apps/mobile/src/staff-login.test.ts": ("staff.abdwash.local",),
    "backend/.env.example": ("/abdwash",),
    "backend/alembic.ini": ("/abdwash",),
    "backend/app/cli/seed.py": ('slug == "abdwash"', 'slug="abdwash"'),
    "backend/app/cli/seed_demo_staff.py": ('Business.slug == "abdwash"',),
    "backend/app/core/config.py": ("/abdwash",),
    "backend/app/domain/staff_usernames.py": ("staff.abdwash.local",),
    "backend/app/repositories/business.py": ('Business.slug == "abdwash"',),
    "backend/migrations/versions/5e2c8f7a1b4d_provision_main_shop_and_rebrand.py": (
        "slug = 'abdwash'",
        "lower(name) IN ('abdwash', 'abd wash', 'adb wash')",
    ),
    "backend/migrations/versions/c52e9d1a40b7_add_sync_revisions_and_repair_assignments.py": (
        "AbdWash assignment repair",
    ),
    "backend/migrations/versions/e5b17c9d2a40_repair_customer_catalogue_identity.py": (
        "Development Standard Wash",
    ),
    "backend/tests/test_inventory.py": ("slug = 'abdwash'",),
    "backend/tests/test_management_tokens.py": ("/abdwash",),
    "backend/tests/test_notifications.py": ("AbdWash", "ABD Wash", "ADB Wash"),
    "backend/tests/test_postgres_integration.py": ('slug="abdwash"', 'slug == "abdwash"'),
    "backend/tests/test_staff_usernames.py": ("staff.abdwash.local",),
    "docs/deployment.md": (
        "abdwash-vdtc.vercel.app",
        "abdwash.vercel.app",
        "abdwash-notification-dispatch",
        "abdwash_outbox_dispatch_url",
        "abdwash_outbox_dispatch_secret",
    ),
    "supabase/notification_dispatch_cron.sql": (
        "abdwash-notification-dispatch",
        "abdwash_outbox_dispatch_url",
        "abdwash_outbox_dispatch_secret",
    ),
}


def _files() -> list[Path]:
    files: list[Path] = []
    for root in SCANNED_ROOTS:
        candidates = [root] if root.is_file() else root.rglob("*")
        files.extend(
            path
            for path in candidates
            if path.is_file()
            and path != Path(__file__)
            and path.name not in {".env", ".env.local"}
            and not any(part in IGNORED_PARTS for part in path.parts)
            and path.suffix not in {".pyc", ".png", ".jpg", ".ico"}
        )
    return files


def test_active_repository_has_no_unexplained_old_brand() -> None:
    unexplained: list[str] = []
    for path in _files():
        relative = path.relative_to(REPOSITORY).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not OLD_BRAND.search(line):
                continue
            allowed_fragments = ALLOWED_BY_PATH.get(relative, ())
            if not any(fragment in line for fragment in allowed_fragments):
                unexplained.append(f"{relative}:{line_number}: {line.strip()}")
    assert unexplained == []
