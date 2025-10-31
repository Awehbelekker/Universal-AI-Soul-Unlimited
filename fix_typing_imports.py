"""Fix missing typing imports"""
import re
from pathlib import Path

files_to_fix = {
    r'thinkmesh_core\localai\local_model_manager.py': ['Dict', 'List'],
    r'thinkmesh_core\localai\phase2_optimizer.py': ['Dict'],
    r'thinkmesh_core\orchestration\task_router.py': ['Dict', 'List'],
    r'thinkmesh_core\voice\voice_pipeline.py': ['Dict', 'Optional'],
}

base = Path(r'C:\Users\Richard.Downing\OneDrive - ITEC Group\Desktop\Universal AI Soul Unlimited')

for file_path, needed_types in files_to_fix.items():
    full_path = base / file_path
    print(f"Fixing {file_path}...")

    content = full_path.read_text(encoding='utf-8')

    # Check if typing import already exists
    if 'from typing import' in content:
        # Find the existing import line
        import_match = re.search(r'from typing import ([^\n]+)', content)
        if import_match:
            existing_imports = [x.strip() for x in import_match.group(1).split(',')]
            all_imports = sorted(set(existing_imports + needed_types))
            new_import = f'from typing import {", ".join(all_imports)}'
            content = re.sub(r'from typing import [^\n]+', new_import, content)
    else:
        # Add new import after first docstring or at top
        if content.startswith('"""'):
            # Find end of docstring
            end_idx = content.find('"""', 3) + 3
            before = content[:end_idx]
            after = content[end_idx:]
            content = before + f'\n\nfrom typing import {", ".join(sorted(needed_types))}\n' + after.lstrip()
        else:
            content = f'from typing import {", ".join(sorted(needed_types))}\n' + content

    full_path.write_text(content, encoding='utf-8', newline='\n')
    print(f"  ✅ Added: {', '.join(needed_types)}")

print("\n✅ All typing imports fixed")
