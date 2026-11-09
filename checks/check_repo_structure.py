#!/usr/bin/env python3
"""rel-* Repository Standards & Compliance Linter.

Audits sibling rel-* repositories against core standards:
  1. Strict Zero-Data Gitignore (excludes *.db, *.sqlite*, data/, *.DAT, *.zip)
  2. pyproject.toml compliance
  3. Deploy script (deploy/sync_to_vm.sh) present
  4. No tracked data or database files in Git
"""

import os
import subprocess
import sys
from pathlib import Path

REQUIRED_GITIGNORE_PATTERNS = [
    "*.db",
    "*.sqlite",
    "*.DAT",
    "*.zip",
    "data/",
]

EXPECTED_REPOS = [
    "rel-repo-standards",
    "rel-aly-works",
    "rel-svc-denton-data",
    "rel-svc-collin-data",
    "rel-svc-mls-data",
]


def check_gitignore(repo_path: Path) -> list[str]:
    gitignore = repo_path / ".gitignore"
    errors = []
    if not gitignore.exists():
        return ["Missing .gitignore file"]

    content = gitignore.read_text(encoding="utf-8")
    for pattern in REQUIRED_GITIGNORE_PATTERNS:
        if pattern not in content:
            errors.append(f"Missing required pattern in .gitignore: '{pattern}'")
    return errors


def check_tracked_data_files(repo_path: Path) -> list[str]:
    """Ensure no data files, databases, or heavy archives are tracked by git."""
    errors = []
    try:
        res = subprocess.run(
            ["git", "-C", str(repo_path), "ls-files", "*.db", "*.sqlite*", "*.DAT", "*.zip", "*.har", "data/*"],
            capture_output=True,
            text=True,
            check=False,
        )
        tracked = [f.strip() for f in res.stdout.strip().splitlines() if f.strip()]
        if tracked:
            errors.append(f"VIOLATION: Found tracked data files in Git: {', '.join(tracked)}")
    except (subprocess.SubprocessError, OSError) as e:
        errors.append(f"Failed to check git tracked files: {e}")
    return errors


def check_symlinks(repo_path: Path) -> list[str]:
    """Ensure zero symlinks exist in the repository to guarantee pure native portability."""
    errors = []
    for root, dirs, files in os.walk(repo_path):
        if ".git" in root or ".venv" in root:
            continue
        for name in dirs + files:
            full_path = Path(root) / name
            if full_path.is_symlink():
                errors.append(f"VIOLATION: Found symlink: {full_path.relative_to(repo_path)} -> {os.readlink(full_path)}")
    return errors


def check_repo(repo_path: Path) -> dict:
    results = {"path": repo_path.name, "errors": [], "warnings": []}

    if not (repo_path / "pyproject.toml").exists():
        results["errors"].append("Missing pyproject.toml")

    if not (repo_path / "README.md").exists():
        results["warnings"].append("Missing README.md")

    # Check for master pipeline runner in operational repos
    if repo_path.name in ["rel-aly-works", "rel-svc-denton-data", "rel-svc-collin-data", "rel-svc-mls-data"]:
        if not (repo_path / "run_all.py").exists():
            results["errors"].append("Missing master pipeline orchestrator: run_all.py")
        if not (repo_path / "Makefile").exists():
            results["warnings"].append("Missing Makefile")

    # Gitignore checks
    gi_errs = check_gitignore(repo_path)
    results["errors"].extend(gi_errs)

    # Tracked files check
    tracked_errs = check_tracked_data_files(repo_path)
    results["errors"].extend(tracked_errs)

    # Symlink check
    symlink_errs = check_symlinks(repo_path)
    results["errors"].extend(symlink_errs)

    # Check for deploy script in services/analysis
    if repo_path.name in ["rel-aly-works", "rel-svc-denton-data", "rel-svc-collin-data", "rel-svc-mls-data"]:
        deploy_script = repo_path / "deploy" / "sync_to_vm.sh"
        if not deploy_script.exists():
            results["warnings"].append("Missing deploy/sync_to_vm.sh script")

    return results


def main():
    workspace_root = Path(__file__).resolve().parent.parent.parent
    print(f"[*] Auditing rel-* Repositories under: {workspace_root}\n")

    found_any = False
    all_clean = True

    for item in sorted(workspace_root.iterdir()):
        if item.is_dir() and item.name.startswith("rel-"):
            found_any = True
            report = check_repo(item)
            status_icon = "✓" if not report["errors"] else "✗"
            print(f"[{status_icon}] {item.name}:")
            if not report["errors"] and not report["warnings"]:
                print("    All compliance checks passed cleanly.")
            for err in report["errors"]:
                print(f"    ERROR: {err}")
                all_clean = False
            for warn in report["warnings"]:
                print(f"    WARN : {warn}")
            print()

    if not found_any:
        print("[!] No rel-* repositories found in parent workspace.")
        sys.exit(1)

    if all_clean:
        print("[✓] ALL REL-* REPOSITORIES COMPLIANT WITH ECOSYSTEM STANDARDS!")
        sys.exit(0)
    else:
        print("[✗] Standards violations detected. Please resolve errors.")
        sys.exit(1)


if __name__ == "__main__":
    main()
