# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
import subprocess
from pathlib import Path

import adbutils

# App compile-time constants
_BB_CONSUMER_API_BASE_URL = "http://localhost:8090"
_BB_CONSUMER_API_CLIENT_ID = "test"
_BB_CONSUMER_API_CLIENT_SECRET = "test"
_BB_SSE_BASE_URL = "http://localhost:8092"
_C2_ENDPOINT_URL = "ws://localhost:9099"

# App build configuration
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_APP_REPO_DIR = _PROJECT_ROOT / "repos" / "nmshd_app_fork"
_APP_DIR = _APP_REPO_DIR / "apps" / "enmeshed"
_APK_PATH = _APP_DIR / "build" / "app" / "outputs" / "flutter-apk" / "app-debug.apk"
_APP_REQUESTED_PERMISSIONS = [
    "android.permission.CAMERA",
    "android.permission.POST_NOTIFICATIONS",
]
_NMSHD_APP_ID = "eu.enmeshed.app.dev"


def _sh(cmd: list[str], cwd: Path | None = None) -> None:
    _ = subprocess.run(cmd, check=True, cwd=cwd)


def build():
    if not _APP_REPO_DIR.exists():
        _APP_REPO_DIR.parent.mkdir(parents=True, exist_ok=True)
        _sh(
            [
                "git",
                "clone",
                "git@github.com:js-soft/nmshd_app_fork.git",
                str(_APP_REPO_DIR),
            ]
        )

    _sh(["melos", "bootstrap"], cwd=_APP_REPO_DIR)
    _sh(["melos", "generate_translations"], cwd=_APP_REPO_DIR)
    _sh(
        [
            "flutter",
            "build",
            "apk",
            "--debug",
            "--dart-define",
            f"app_baseUrl={_BB_CONSUMER_API_BASE_URL}",
            "--dart-define",
            f"app_clientId={_BB_CONSUMER_API_CLIENT_ID}",
            "--dart-define",
            f"app_clientSecret={_BB_CONSUMER_API_CLIENT_SECRET}",
            "--dart-define",
            f"app_sseBaseUrl={_BB_SSE_BASE_URL}",
            "--dart-define",
            f"app_c2Url={_C2_ENDPOINT_URL}",
        ],
        cwd=_APP_DIR,
    )


def install(
    *,
    device_serial: str | None = None,
) -> None:
    """Install an APK from a local file path."""
    device = adbutils.device(device_serial)
    device.install(_APK_PATH)


def start(
    *,
    device_serial: str | None = None,
):
    device = adbutils.device(device_serial)
    _wipe_cache(device_serial=device_serial)
    _grant_permissions(device_serial=device_serial)

    device.reverse("tcp:8090", "tcp:8090")
    device.reverse("tcp:8092", "tcp:8092")
    device.reverse("tcp:9099", "tcp:9099")

    _ = device.shell(
        [
            "am",
            "start",
            "-n",
            f"{_NMSHD_APP_ID}/.MainActivity",
        ]
    )


def uninstall(
    *,
    device_serial: str | None = None,
) -> None:
    device = adbutils.device(device_serial)
    result = device.shell(["pm", "list", "packages", _NMSHD_APP_ID])
    if _NMSHD_APP_ID in result:
        _ = device.shell(["pm", "uninstall", _NMSHD_APP_ID])


def _wipe_cache(
    *,
    device_serial: str | None = None,
) -> None:
    device = adbutils.device(device_serial)
    _ = device.shell(
        [
            "pm",
            "clear",
            _NMSHD_APP_ID,
        ]
    )


def _grant_permissions(
    *,
    device_serial: str | None = None,
) -> None:
    device = adbutils.device(device_serial)
    for p in _APP_REQUESTED_PERMISSIONS:
        _ = device.shell(
            [
                "pm",
                "grant",
                _NMSHD_APP_ID,
                p,
            ]
        )
