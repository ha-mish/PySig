"""Run PySig local quality checks."""

from pathlib import Path
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parent


def get_python_path() -> Path:
    """Prompt for and validate the Python executable."""

    while True:
        value = (
            input(
                "Enter the full path to python.exe:\n"
                "Example: C:\\Users\\username\\Anaconda3\\python.exe\n\n"
                "> "
            )
            .strip()
            .strip('"')
        )

        python_path = Path(value)

        if python_path.is_file():
            return python_path

        print("\nPython executable not found. Please try again.\n")


def run_check(
    python_path: Path,
    name: str,
    arguments: list[str],
) -> bool:
    """Run one quality check and return True when it passes."""

    print()
    print("=" * 70)
    print(name)
    print("=" * 70)
    print()

    command = [
        str(python_path),
        "-m",
        *arguments,
    ]

    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=False,
    )

    if result.returncode == 0:
        print()
        print(f"PASS: {name}")
        return True

    print()
    print(f"FAIL: {name} returned exit code {result.returncode}")
    return False


def main() -> int:
    """Run Black, Flake8 and pytest."""

    print()
    print("PySig Code Quality Check")
    print("========================")
    print()

    python_path = get_python_path()

    print()
    print(f"Python:  {python_path}")
    print(f"Project: {PROJECT_ROOT}")

    results = {
        "Black": run_check(
            python_path,
            "Black formatting check",
            ["black", "--check", "--diff", "."],
        ),
        "Flake8": run_check(
            python_path,
            "Flake8 lint check",
            ["flake8", "."],
        ),
        "pytest": run_check(
            python_path,
            "pytest test suite",
            [
                "pytest",
                "-v",
                "-ra",
                "--tb=short",
            ],
        ),
    }

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"{name:<12} {status}")

    print()

    if all(results.values()):
        print("All PySig checks passed.")
        return 0

    print("One or more PySig checks failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
