"""
Universal Soul Unlimited - Implementation Status
Quick verification and next steps guide
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
THINKMESH_ROOT = PROJECT_ROOT / "thinkmesh_core"

EXPECTED_MODULES = [
    "orchestration",
    "ai_providers",
    "voice",
    "monitoring",
    "cogniflow",
    "automation",
    "sync",
    "bridges",
    "synergycore",
    "hrm",
    "reasoning",
    "localai",
]


def verify_implementation():
    """Verify all modules are implemented"""
    print("=" * 70)
    print("UNIVERSAL SOUL UNLIMITED - IMPLEMENTATION STATUS")
    print("=" * 70)
    print()
    print(f"Project root: {PROJECT_ROOT}")
    print()

    print("Module Status:")
    print("-" * 70)

    all_good = True
    for module in EXPECTED_MODULES:
        module_path = THINKMESH_ROOT / module
        init_file = module_path / "__init__.py"

        if module_path.exists() and init_file.exists():
            py_files = list(module_path.glob("*.py"))
            status = f"[OK] {len(py_files)} files"
            print(f"  {module:20s} {status}")
        else:
            print(f"  {module:20s} [MISSING]")
            all_good = False

    print()
    print("-" * 70)

    total_py_files = len(list(THINKMESH_ROOT.rglob("*.py")))
    print(f"Total Python Files: {total_py_files}")
    print()

    config_file = PROJECT_ROOT / "config" / "universal_soul.json"
    print(f"Config file: {'[OK]' if config_file.exists() else '[MISSING]'}")
    print(f"Desktop entry: {'[OK]' if (PROJECT_ROOT / 'main_desktop.py').exists() else '[MISSING]'}")
    print(f"Android entry: {'[OK]' if (PROJECT_ROOT / 'app_main.py').exists() else '[MISSING]'}")
    print()

    if all_good:
        print("All ThinkMesh Core modules present.")
    else:
        print("Some modules missing — see list above.")

    print()
    print("Next: python scripts/setup_ollama.py && python main_desktop.py")
    return all_good


if __name__ == "__main__":
    verify_implementation()
