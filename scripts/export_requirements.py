from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    requirements = list(project["dependencies"])
    for optional_requirements in project.get("optional-dependencies", {}).values():
        requirements.extend(optional_requirements)

    print("# Generated from pyproject.toml.")
    print("# Regenerate with: python scripts/export_requirements.py > requirements.txt")
    print()
    for requirement in requirements:
        print(requirement)


if __name__ == "__main__":
    main()
