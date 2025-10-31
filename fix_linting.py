"""
Automated linting fixer for common Flake8 issues
"""

import re
import sys
from pathlib import Path


def fix_e302_blank_lines(content):
    """Add 2 blank lines before class/function definitions"""
    # Fix single blank line before class definition
    content = re.sub(
        r'\n\nclass ',
        r'\n\n\nclass ',
        content
    )
    return content


def fix_w292_newline_eof(content):
    """Ensure newline at end of file"""
    if content and not content.endswith('\n'):
        content += '\n'
    return content


def fix_f401_unused_imports(filepath, content):
    """Remove specific unused imports"""
    unused_patterns = [
        (r'from typing import[^\n]*\bList\b[^\n]*\n', 'List'),
        (r'import asyncio\n', 'asyncio'),
        (r'import json\n', 'json'),
    ]

    for pattern, name in unused_patterns:
        # Only remove if import exists and name is not used in code
        if re.search(pattern, content):
            # Simple check - see if the name appears elsewhere
            lines = content.split('\n')
            import_line = None
            for i, line in enumerate(lines):
                if re.search(pattern.replace('\\n', ''), line):
                    import_line = i
                    break

            if import_line is not None:
                # Check if name is used after import line
                after_import = '\n'.join(lines[import_line + 1:])
                # Don't remove if it appears in actual code (not comments)
                if not re.search(rf'\b{name}\b', after_import):
                    content = re.sub(pattern, '', content)

    return content


def fix_f541_empty_fstrings(content):
    """Convert f-strings without placeholders to regular strings"""
    # Match f"..." or f'...' without any {} placeholders
    content = re.sub(
        r'f"([^"{}]*)"',
        r'"\1"',
        content
    )
    content = re.sub(
        r"f'([^'{}]*)'",
        r"'\1'",
        content
    )
    return content


def fix_e722_bare_except(content):
    """Replace bare except with except Exception"""
    content = re.sub(
        r'except:',
        r'except Exception:',
        content
    )
    return content


def fix_file(filepath):
    """Apply all fixes to a file"""
    print(f"Fixing {filepath}...")

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    # Apply fixes
    content = fix_e302_blank_lines(content)
    content = fix_w292_newline_eof(content)
    content = fix_f401_unused_imports(filepath, content)
    content = fix_f541_empty_fstrings(content)
    content = fix_e722_bare_except(content)

    if content != original:
        with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
            f.write(content)
        print(f"  ✅ Fixed {filepath}")
        return True
    else:
        print(f"  ⏭️  No changes needed for {filepath}")
        return False


def main():
    base_path = Path(
        r'C:\Users\Richard.Downing\OneDrive - ITEC Group\Desktop'
        r'\Universal AI Soul Unlimited\thinkmesh_core'
    )

    fixed_count = 0
    for py_file in base_path.rglob('*.py'):
        if fix_file(py_file):
            fixed_count += 1

    print(f"\n✅ Fixed {fixed_count} files")


if __name__ == '__main__':
    main()
