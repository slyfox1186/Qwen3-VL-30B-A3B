#!/usr/bin/env python3
"""
Project Linter Script

Runs linters in order:
1. TypeScript (tsc --noEmit)
2. ESLint
3. Python (ruff)

Stops immediately on first failure and returns all errors for that section.
"""

import subprocess
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class LintResult:
    """Result of a lint check."""
    name: str
    success: bool
    output: str
    return_code: int


def run_command(cmd: list[str], cwd: Optional[Path] = None) -> tuple[int, str, str]:
    """Run a command and return (return_code, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return -1, "", f"Command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out: {' '.join(cmd)}"
    except Exception as e:
        return -1, "", str(e)


def check_typescript(frontend_dir: Path) -> LintResult:
    """Run TypeScript compiler check."""
    print("\n" + "=" * 60)
    print("🔍 Running TypeScript Check (tsc --noEmit)")
    print("=" * 60)

    if not frontend_dir.exists():
        return LintResult(
            name="TypeScript",
            success=True,
            output="Frontend directory not found, skipping TypeScript check",
            return_code=0,
        )

    # Check if tsconfig.json exists
    tsconfig = frontend_dir / "tsconfig.json"
    if not tsconfig.exists():
        return LintResult(
            name="TypeScript",
            success=True,
            output="No tsconfig.json found, skipping TypeScript check",
            return_code=0,
        )

    # Check if node_modules exists
    node_modules = frontend_dir / "node_modules"
    if not node_modules.exists():
        return LintResult(
            name="TypeScript",
            success=False,
            output="node_modules not found. Run 'npm install' first.",
            return_code=1,
        )

    # Run tsc --noEmit
    code, stdout, stderr = run_command(
        ["npx", "tsc", "--noEmit"],
        cwd=frontend_dir,
    )

    output = stdout + stderr
    success = code == 0

    if success:
        print("✅ TypeScript check passed")
    else:
        print("❌ TypeScript check failed")
        print(output)

    return LintResult(
        name="TypeScript",
        success=success,
        output=output if not success else "No errors",
        return_code=code,
    )


def check_eslint(frontend_dir: Path) -> LintResult:
    """Run ESLint check."""
    print("\n" + "=" * 60)
    print("🔍 Running ESLint Check")
    print("=" * 60)

    if not frontend_dir.exists():
        return LintResult(
            name="ESLint",
            success=True,
            output="Frontend directory not found, skipping ESLint check",
            return_code=0,
        )

    # Check for eslint config
    eslint_configs = [
        ".eslintrc.js",
        ".eslintrc.cjs",
        ".eslintrc.json",
        ".eslintrc.yml",
        ".eslintrc.yaml",
        "eslint.config.js",
        "eslint.config.mjs",
    ]
    has_eslint = any((frontend_dir / cfg).exists() for cfg in eslint_configs)

    # Also check package.json for eslintConfig
    package_json = frontend_dir / "package.json"
    if package_json.exists():
        import json
        try:
            with open(package_json) as f:
                pkg = json.load(f)
                if "eslintConfig" in pkg:
                    has_eslint = True
        except Exception:
            pass

    if not has_eslint:
        return LintResult(
            name="ESLint",
            success=True,
            output="No ESLint config found, skipping ESLint check",
            return_code=0,
        )

    # Check if node_modules exists
    node_modules = frontend_dir / "node_modules"
    if not node_modules.exists():
        return LintResult(
            name="ESLint",
            success=False,
            output="node_modules not found. Run 'npm install' first.",
            return_code=1,
        )

    # Run eslint
    code, stdout, stderr = run_command(
        ["npx", "eslint", ".", "--ext", ".ts,.tsx,.js,.jsx", "--max-warnings=0"],
        cwd=frontend_dir,
    )

    output = stdout + stderr
    success = code == 0

    if success:
        print("✅ ESLint check passed")
    else:
        print("❌ ESLint check failed")
        print(output)

    return LintResult(
        name="ESLint",
        success=success,
        output=output if not success else "No errors",
        return_code=code,
    )


def check_python(backend_dir: Path) -> LintResult:
    """Run Python linter (ruff)."""
    print("\n" + "=" * 60)
    print("🔍 Running Python Linter (ruff)")
    print("=" * 60)

    if not backend_dir.exists():
        return LintResult(
            name="Python (ruff)",
            success=True,
            output="Backend directory not found, skipping Python check",
            return_code=0,
        )

    # Check if there are any Python files
    py_files = list(backend_dir.rglob("*.py"))
    if not py_files:
        return LintResult(
            name="Python (ruff)",
            success=True,
            output="No Python files found, skipping Python check",
            return_code=0,
        )

    # Try ruff first, fall back to flake8
    code, stdout, stderr = run_command(
        ["ruff", "check", "."],
        cwd=backend_dir,
    )

    # If ruff not found, try flake8
    if code == -1 and "not found" in stderr.lower():
        print("ruff not found, trying flake8...")
        code, stdout, stderr = run_command(
            ["flake8", ".", "--max-line-length=100", "--ignore=E501,W503"],
            cwd=backend_dir,
        )

        if code == -1 and "not found" in stderr.lower():
            # Neither found, try python -m
            code, stdout, stderr = run_command(
                [sys.executable, "-m", "ruff", "check", "."],
                cwd=backend_dir,
            )

            if code == -1:
                # Last resort: basic syntax check
                print("No Python linter found, running basic syntax check...")
                errors = []
                for py_file in py_files:
                    try:
                        with open(py_file) as f:
                            compile(f.read(), py_file, "exec")
                    except SyntaxError as e:
                        errors.append(f"{py_file}:{e.lineno}: {e.msg}")

                if errors:
                    return LintResult(
                        name="Python (syntax)",
                        success=False,
                        output="\n".join(errors),
                        return_code=1,
                    )
                else:
                    print("✅ Python syntax check passed")
                    return LintResult(
                        name="Python (syntax)",
                        success=True,
                        output="Basic syntax check passed (install ruff for full linting)",
                        return_code=0,
                    )

    output = stdout + stderr
    success = code == 0

    if success:
        print("✅ Python check passed")
    else:
        print("❌ Python check failed")
        print(output)

    return LintResult(
        name="Python (ruff)",
        success=success,
        output=output if not success else "No errors",
        return_code=code,
    )


def main() -> int:
    """Run all linters in order."""
    print("🚀 Starting Project Linter")
    print("=" * 60)

    # Determine project root
    project_root = Path(__file__).parent
    frontend_dir = project_root / "frontend"
    backend_dir = project_root / "backend"

    results: list[LintResult] = []

    # 1. TypeScript Check
    ts_result = check_typescript(frontend_dir)
    results.append(ts_result)
    if not ts_result.success:
        print_summary(results)
        return 1

    # 2. ESLint Check
    eslint_result = check_eslint(frontend_dir)
    results.append(eslint_result)
    if not eslint_result.success:
        print_summary(results)
        return 1

    # 3. Python Check
    python_result = check_python(backend_dir)
    results.append(python_result)
    if not python_result.success:
        print_summary(results)
        return 1

    print_summary(results)
    return 0


def print_summary(results: list[LintResult]) -> None:
    """Print summary of all lint results."""
    print("\n" + "=" * 60)
    print("📊 LINT SUMMARY")
    print("=" * 60)

    all_passed = True
    for result in results:
        status = "✅ PASS" if result.success else "❌ FAIL"
        print(f"  {result.name}: {status}")
        if not result.success:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("🎉 All checks passed!")
    else:
        print("💥 Linting failed! Fix the errors above.")
        # Print the failed section's errors
        for result in results:
            if not result.success:
                print(f"\n--- {result.name} Errors ---")
                print(result.output)
                break  # Only show first failure


if __name__ == "__main__":
    sys.exit(main())
