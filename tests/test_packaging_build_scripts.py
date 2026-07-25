# -*- coding: utf-8 -*-
"""Validation tests for backend packaging scripts."""

import json
import os
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_windows_backend_build_script_collects_alphasift_adapter() -> None:
    script = _read_text(REPO_ROOT / "scripts" / "build-backend.ps1")
    main_py = _read_text(REPO_ROOT / "main.py")

    assert "Checking AlphaSift adapter availability" in script
    assert "import alphasift.dsa_adapter" in script
    assert "--collect-all" in script
    assert "alphasift.dsa_adapter" in script
    assert "hiddenImports" in script
    assert "Verifying packaged runtime imports" in script
    assert "DSA_PACKAGED_IMPORT_PROBE" in script
    assert "Start-Process -FilePath $packagedEntry -Wait -PassThru" in script
    assert "$probeProcess.ExitCode" in script
    assert "& $packagedEntry" not in script
    assert "Packaged backend cannot import $module" in script
    assert "DSA_PACKAGED_IMPORT_PROBE" in main_py
    assert "importlib.import_module(_packaged_import_probe)" in main_py


def test_macos_backend_build_script_collects_alphasift_adapter() -> None:
    script = _read_text(REPO_ROOT / "scripts" / "build-backend-macos.sh")
    main_py = _read_text(REPO_ROOT / "main.py")

    assert "Checking AlphaSift adapter availability..." in script
    assert "import alphasift.dsa_adapter" in script
    assert "--collect-all" in script
    assert "cmd+=(\"--collect-all\" \"alphasift\")" in script
    assert "packaged_entry=\"${packaged_root}/stock_analysis\"" in script
    assert "--help" in script
    assert 'DSA_PACKAGED_IMPORT_PROBE="${module}"' in script
    assert "dsa-packaged-import.log" in script
    assert "PathFinder.find_spec(" not in script
    assert "zipfile" not in script
    assert 'normalized.startswith("alphasift/dsa_adapter.")' not in script
    assert "DSA_PACKAGED_IMPORT_PROBE" in main_py
    assert "importlib.import_module(_packaged_import_probe)" in main_py


def test_macos_backend_reports_first_invalid_pyinstaller_signature() -> None:
    script = _read_text(REPO_ROOT / "scripts" / "build-backend-macos.sh")

    assert 'file -b "${packaged_file}" | grep -q "Mach-O"' in script
    assert 'codesign --verify --strict --verbose=4 "${packaged_file}"' in script
    assert "code object is not signed at all" in script
    assert "removing invalid pre-existing signature from PyInstaller artifact" in script
    assert 'codesign --remove-signature "${packaged_file}"' in script
    assert "failed to clear invalid signature immediately after PyInstaller packaging" in script
    assert "unreadable signature immediately after PyInstaller packaging" in script


def test_macos_backend_strategy_count_uses_portable_globbing() -> None:
    script = _read_text(REPO_ROOT / "scripts" / "build-backend-macos.sh")

    assert "count_top_level_yaml_files()" in script
    assert 'for file_path in "${target_dir}"/*.yaml; do' in script
    assert "shopt -s nullglob" in script
    assert '-maxdepth 1 -type f -name \'*.yaml\'' not in script


def test_macos_distribution_build_requires_signing_and_notarization() -> None:
    script = _read_text(REPO_ROOT / "scripts" / "build-desktop-macos.sh")
    package = json.loads(
        _read_text(REPO_ROOT / "apps" / "dsa-desktop" / "package.json")
    )

    assert "is_release_workflow_context" in script
    assert 'if [[ -n "${DSA_MAC_DISTRIBUTION:-}" ]]; then' in script
    assert 'elif should_auto_enable_distribution_build; then' in script
    assert "macOS release workflows must run a signed distribution build." in script
    assert "Provide signing credentials in the release workflow" in script
    assert "has_complete_app_store_connect_notarization_credentials" in script
    assert "has_complete_apple_id_notarization_credentials" in script
    assert 'export CSC_IDENTITY_AUTO_DISCOVERY="true"' in script
    assert "Developer ID Application" in script
    assert "CSC_KEY_PASSWORD is required when CSC_LINK is provided." in script
    assert "APPLE_API_KEY must point to a readable" in script
    assert '--config.forceCodeSigning=true' in script
    assert "CSC_LINK/CSC_KEY_PASSWORD" in script
    assert "APPLE_API_KEY/APPLE_API_KEY_ID/APPLE_API_ISSUER" in script
    assert "APPLE_ID/APPLE_APP_SPECIFIC_PASSWORD/APPLE_TEAM_ID" in script
    assert "WARNING: unsigned local macOS build; do not publish this artifact." in script
    assert package["build"]["mac"]["hardenedRuntime"] is True
    assert package["build"]["mac"]["gatekeeperAssess"] is False
    assert "-maxdepth" not in script


def test_macos_backend_strips_invalid_packaged_signature(tmp_path: Path) -> None:
    script_path = REPO_ROOT / "scripts" / "build-backend-macos.sh"
    packaged_file = tmp_path / "broken.bin"
    packaged_file.write_text("mach-o", encoding="utf-8")
    marker = tmp_path / "removed.flag"
    command = """
source "$1"
marker_path="$3"
codesign() {
  if [[ "$1" == "-d" ]]; then
    if [[ -f "${marker_path}" ]]; then
      printf 'code object is not signed at all\\n' >&2
      return 1
    fi
    printf 'Authority=adhoc\\n' >&2
    return 0
  fi
  if [[ "$1" == "--verify" ]]; then
    printf 'broken signature\\n' >&2
    return 1
  fi
  if [[ "$1" == "--remove-signature" ]]; then
    : > "${marker_path}"
    printf 'removed:%s\\n' "$2"
    return 0
  fi
}
strip_invalid_packaged_signature "$2"
"""

    result = subprocess.run(
        ["bash", "-c", command, "bash", str(script_path), str(packaged_file), str(marker)],
        cwd=REPO_ROOT,
        env={"PATH": os.environ["PATH"]},
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "removing invalid pre-existing signature" in result.stdout
    assert f"removed:{packaged_file}" in result.stdout


def test_macos_backend_rejects_unreadable_packaged_signature(tmp_path: Path) -> None:
    script_path = REPO_ROOT / "scripts" / "build-backend-macos.sh"
    packaged_file = tmp_path / "broken.bin"
    packaged_file.write_text("mach-o", encoding="utf-8")
    command = """
source "$1"
codesign() {
  if [[ "$1" == "-d" ]]; then
    printf 'malformed signature\\n' >&2
    return 1
  fi
}
strip_invalid_packaged_signature "$2"
"""

    result = subprocess.run(
        ["bash", "-c", command, "bash", str(script_path), str(packaged_file)],
        cwd=REPO_ROOT,
        env={"PATH": os.environ["PATH"]},
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "unreadable signature immediately after PyInstaller packaging" in result.stdout


def test_macos_distribution_artifact_discovery_uses_portable_globbing(
    tmp_path: Path,
) -> None:
    script_path = REPO_ROOT / "scripts" / "build-desktop-macos.sh"
    dist_dir = tmp_path / "dist"
    (dist_dir / "mac-arm64" / "Daily Stock Analysis.app").mkdir(parents=True)
    (dist_dir / "Daily Stock Analysis-arm64.dmg").write_text(
        "dmg", encoding="utf-8"
    )
    command = """
source "$1"
cd "$2"
find_single_artifact d "Daily Stock Analysis.app"
find_single_artifact f "*.dmg"
"""

    result = subprocess.run(
        ["bash", "-c", command, "bash", str(script_path), str(tmp_path)],
        cwd=REPO_ROOT,
        env={"PATH": os.environ["PATH"]},
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.splitlines() == [
        "dist/mac-arm64/Daily Stock Analysis.app",
        "dist/Daily Stock Analysis-arm64.dmg",
    ]


def test_macos_github_actions_build_stays_unsigned_without_release_context() -> None:
    script_path = REPO_ROOT / "scripts" / "build-desktop-macos.sh"
    command = """
source "$1"
printf '%s\\n' "${distribution_build}"
"""
    env = {"PATH": os.environ["PATH"], "GITHUB_ACTIONS": "true"}

    result = subprocess.run(
        ["bash", "-c", command, "bash", str(script_path)],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "false"


def test_macos_github_actions_release_requires_distribution_credentials() -> None:
    script_path = REPO_ROOT / "scripts" / "build-desktop-macos.sh"

    result = subprocess.run(
        ["bash", "-c", 'source "$1"', "bash", str(script_path)],
        cwd=REPO_ROOT,
        env={
            "PATH": os.environ["PATH"],
            "GITHUB_ACTIONS": "true",
            "RELEASE_TAG": "v3.21.0",
        },
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "macOS release workflows must run a signed distribution build." in result.stdout


def test_macos_release_context_rejects_explicit_unsigned_override() -> None:
    script_path = REPO_ROOT / "scripts" / "build-desktop-macos.sh"

    result = subprocess.run(
        ["bash", "-c", 'source "$1"', "bash", str(script_path)],
        cwd=REPO_ROOT,
        env={
            "PATH": os.environ["PATH"],
            "GITHUB_ACTIONS": "true",
            "RELEASE_TAG": "v3.21.0",
            "DSA_MAC_DISTRIBUTION": "false",
            "APPLE_ID": "developer@example.com",
            "APPLE_APP_SPECIFIC_PASSWORD": "app-password",
            "APPLE_TEAM_ID": "TEAMID1234",
        },
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "macOS release workflows must run a signed distribution build." in result.stdout


def test_macos_distribution_release_workflow_exports_release_tag_context() -> None:
    workflow = _read_text(REPO_ROOT / ".github" / "workflows" / "desktop-release.yml")

    assert "build-macos:" in workflow
    assert "RELEASE_TAG: ${{ github.event_name == 'workflow_dispatch' && inputs.release_tag || github.ref_name }}" in workflow
    assert "run: bash scripts/build-all-macos.sh" in workflow
    assert "DSA_MAC_ARCH: ${{ matrix.arch }}" in workflow


def test_macos_github_actions_release_auto_enables_distribution_with_notary_credentials() -> None:
    script_path = REPO_ROOT / "scripts" / "build-desktop-macos.sh"
    command = """
source "$1"
printf '%s\\n' "${distribution_build}"
"""
    env = {
        "PATH": os.environ["PATH"],
        "GITHUB_ACTIONS": "true",
        "RELEASE_TAG": "v3.21.0",
        "APPLE_ID": "developer@example.com",
        "APPLE_APP_SPECIFIC_PASSWORD": "app-password",
        "APPLE_TEAM_ID": "TEAMID1234",
    }

    result = subprocess.run(
        ["bash", "-c", command, "bash", str(script_path)],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "true"


def test_macos_github_actions_release_auto_enables_distribution_with_api_key_credentials() -> None:
    script_path = REPO_ROOT / "scripts" / "build-desktop-macos.sh"
    command = """
source "$1"
printf '%s\\n' "${distribution_build}"
"""
    env = {
        "PATH": os.environ["PATH"],
        "GITHUB_ACTIONS": "true",
        "RELEASE_TAG": "v3.21.0",
        "APPLE_API_KEY": "/tmp/AuthKey_TEST.p8",
        "APPLE_API_KEY_ID": "KEYID123",
        "APPLE_API_ISSUER": "00000000-0000-0000-0000-000000000000",
    }

    result = subprocess.run(
        ["bash", "-c", command, "bash", str(script_path)],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "true"


def test_macos_distribution_masks_apple_notary_env_from_electron_builder(
    tmp_path: Path,
) -> None:
    script_path = REPO_ROOT / "scripts" / "build-desktop-macos.sh"
    stub_npx = tmp_path / "npx"
    stub_npx.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
for name in APPLE_API_KEY APPLE_API_KEY_ID APPLE_API_ISSUER APPLE_ID APPLE_APP_SPECIFIC_PASSWORD APPLE_TEAM_ID APPLE_KEYCHAIN APPLE_KEYCHAIN_PROFILE; do
  if [[ -n "${!name+x}" ]]; then
    printf '%s=set\\n' "$name"
  else
    printf '%s=unset\\n' "$name"
  fi
done
printf 'ARGS=%s\\n' "$*"
""",
        encoding="utf-8",
    )
    stub_npx.chmod(0o755)

    command = """
source "$1"
run_electron_builder --mac dmg --publish never
"""
    env = {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "APPLE_API_KEY": "/tmp/AuthKey_TEST.p8",
        "APPLE_API_KEY_ID": "KEYID123",
        "APPLE_API_ISSUER": "00000000-0000-0000-0000-000000000000",
        "APPLE_ID": "developer@example.com",
        "APPLE_APP_SPECIFIC_PASSWORD": "app-password",
        "APPLE_TEAM_ID": "TEAMID1234",
        "APPLE_KEYCHAIN": "build.keychain-db",
        "APPLE_KEYCHAIN_PROFILE": "AC_PASSWORD",
    }

    result = subprocess.run(
        ["bash", "-c", command, "bash", str(script_path)],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "APPLE_API_KEY=unset" in result.stdout
    assert "APPLE_API_KEY_ID=unset" in result.stdout
    assert "APPLE_API_ISSUER=unset" in result.stdout
    assert "APPLE_ID=unset" in result.stdout
    assert "APPLE_APP_SPECIFIC_PASSWORD=unset" in result.stdout
    assert "APPLE_TEAM_ID=unset" in result.stdout
    assert "APPLE_KEYCHAIN=unset" in result.stdout
    assert "APPLE_KEYCHAIN_PROFILE=unset" in result.stdout
    assert "ARGS=electron-builder --mac dmg --publish never" in result.stdout


def test_macos_distribution_resolves_api_key_path_before_directory_change(
    tmp_path: Path,
) -> None:
    script_path = REPO_ROOT / "scripts" / "build-desktop-macos.sh"
    api_key = tmp_path / "AuthKey_TEST.p8"
    api_key.write_text("test-key", encoding="utf-8")
    command = """
cd "$2"
source "$1"
uname() { printf 'Darwin\\n'; }
security() { printf '1) Developer ID Application: Test (TEAMID)\\n'; }
prepare_distribution_credentials
printf '%s\\n' "${notary_auth_args[@]}"
"""
    env = {
        "PATH": os.environ["PATH"],
        "APPLE_API_KEY": api_key.name,
        "APPLE_API_KEY_ID": "KEYID123",
        "APPLE_API_ISSUER": "00000000-0000-0000-0000-000000000000",
    }

    result = subprocess.run(
        ["bash", "-c", command, "bash", str(script_path), str(tmp_path)],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert str(api_key.resolve()) in result.stdout.splitlines()


def test_macos_distribution_resolves_csc_link_path_before_directory_change(
    tmp_path: Path,
) -> None:
    script_path = REPO_ROOT / "scripts" / "build-desktop-macos.sh"
    certificate = tmp_path / "developer-id.p12"
    certificate.write_text("signed-cert", encoding="utf-8")
    command = """
cd "$2"
source "$1"
uname() { printf 'Darwin\\n'; }
security() { printf ''; }
prepare_distribution_credentials
printf '%s\\n' "${CSC_LINK}"
"""
    env = {
        "PATH": os.environ["PATH"],
        "CSC_LINK": certificate.name,
        "CSC_KEY_PASSWORD": "test-password",
        "APPLE_ID": "developer@example.com",
        "APPLE_APP_SPECIFIC_PASSWORD": "app-password",
        "APPLE_TEAM_ID": "TEAMID1234",
    }

    result = subprocess.run(
        ["bash", "-c", command, "bash", str(script_path), str(tmp_path)],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.splitlines()[-1] == str(certificate.resolve())


@pytest.mark.parametrize(
    "csc_link",
    [
        "https://example.com/developer-id.p12",
        "MIIKBASE64CERTIFICATE==",
    ],
)
def test_macos_distribution_preserves_non_file_csc_link_values(
    csc_link: str,
) -> None:
    script_path = REPO_ROOT / "scripts" / "build-desktop-macos.sh"
    command = """
source "$1"
uname() { printf 'Darwin\\n'; }
security() { printf ''; }
prepare_distribution_credentials
printf '%s\\n' "${CSC_LINK}"
"""
    env = {
        "PATH": os.environ["PATH"],
        "CSC_LINK": csc_link,
        "CSC_KEY_PASSWORD": "test-password",
        "APPLE_ID": "developer@example.com",
        "APPLE_APP_SPECIFIC_PASSWORD": "app-password",
        "APPLE_TEAM_ID": "TEAMID1234",
    }

    result = subprocess.run(
        ["bash", "-c", command, "bash", str(script_path)],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.splitlines()[-1] == csc_link


def test_macos_distribution_verifies_app_notarized_dmg_and_gatekeeper() -> None:
    script = _read_text(REPO_ROOT / "scripts" / "build-desktop-macos.sh")

    bundle_verify = script.index(
        'codesign --verify --strict --verbose=4 "${component}"'
    )
    nested_verify = script.index(
        'ERROR: first invalid nested signature after Electron packaging'
    )
    app_verify = script.index(
        'codesign --verify --deep --strict --verbose=4 "${app_path}"'
    )
    developer_id_verify = script.index(
        'grep -q "^Authority=Developer ID Application:"'
    )
    notarize = script.index('xcrun notarytool submit "${dmg_path}" --wait')
    staple = script.index('xcrun stapler staple "${dmg_path}"')
    validate = script.index('xcrun stapler validate "${dmg_path}"')
    mounted_verify = script.index(
        'codesign --verify --deep --strict --verbose=4 "${mounted_app}"'
    )
    gatekeeper = script.index(
        'spctl --assess --type execute --verbose=4 "${mounted_app}"'
    )

    assert bundle_verify < nested_verify < app_verify
    assert app_verify < developer_id_verify < notarize < staple < validate
    assert validate < mounted_verify < gatekeeper


@pytest.mark.parametrize(
    ("extra_env", "expected_error"),
    [
        ({}, "Apple notarization credentials are incomplete."),
        (
            {"CSC_LINK": "developer-id.p12"},
            "CSC_KEY_PASSWORD is required when CSC_LINK is provided.",
        ),
        (
            {"APPLE_API_KEY": "AuthKey_TEST.p8"},
            "App Store Connect API notarization credentials are incomplete.",
        ),
        (
            {"APPLE_ID": "developer@example.com"},
            "Apple ID notarization credentials are incomplete.",
        ),
        (
            {
                "APPLE_API_KEY": "missing-AuthKey_TEST.p8",
                "APPLE_API_KEY_ID": "TEST",
                "APPLE_API_ISSUER": "00000000-0000-0000-0000-000000000000",
            },
            "APPLE_API_KEY must point to a readable",
        ),
    ],
)
def test_macos_distribution_credential_preflight_rejects_partial_sets(
    extra_env: dict[str, str], expected_error: str
) -> None:
    script_path = REPO_ROOT / "scripts" / "build-desktop-macos.sh"
    command = """
source "$1"
uname() { printf 'Darwin\\n'; }
security() { printf '1) Developer ID Application: Test (TEAMID)\\n'; }
prepare_distribution_credentials
"""
    env = {"PATH": os.environ["PATH"], **extra_env}

    result = subprocess.run(
        ["bash", "-c", command, "bash", str(script_path)],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert expected_error in result.stdout
