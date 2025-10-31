#!/usr/bin/env python3
"""
Comprehensive Flake8 Linting Fix Script
Automatically fixes all common linting issues
"""

import re
from pathlib import Path


def fix_file(filepath):
    """Fix all linting issues in a file"""
    print(f"\n🔧 Fixing: {filepath}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    lines = content.split('\n')
    fixed_lines = []
    
    for i, line in enumerate(lines, 1):
        original_line = line
        
        # Fix W293: blank line contains whitespace
        if line.strip() == '' and line != '':
            line = ''
        
        # Fix W291: trailing whitespace
        line = line.rstrip()
        
        fixed_lines.append(line)
    
    content = '\n'.join(fixed_lines)
    
    # Fix F401: Remove unused imports
    if 'cpt_oss_integration.py' in filepath:
        content = content.replace('from typing import Dict, Any, Optional, List', 
                                  'from typing import Dict, Any, Optional')
    
    # Fix F541: f-strings without placeholders - remove f prefix
    content = re.sub(r'logger\.info\(f"([^{]*?)"\)', r'logger.info("\1")', content)
    content = re.sub(r'logger\.warning\(f"([^{]*?)"\)', r'logger.warning("\1")', content)
    content = re.sub(r'print\(f"([^{]*?)"\)', r'print("\1")', content)
    
    # Fix E722: bare except
    content = re.sub(r'(\s+)except:\s*\n', r'\1except Exception:\n', content)
    
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"   ✅ Fixed whitespace, trailing spaces, f-strings, bare excepts")
        return True
    else:
        print(f"   ℹ️  No automatic fixes needed")
        return False


def main():
    """Fix all files with linting issues"""
    base_path = Path('thinkmesh_core/localai')
    
    files_to_fix = [
        'cpt_oss_integration.py',
        'local_model_manager.py',
        'voice_pipeline.py',
        'model_optimizer.py',
        'hybrid_model_manager.py'
    ]
    
    fixed_count = 0
    for filename in files_to_fix:
        filepath = base_path / filename
        if filepath.exists():
            if fix_file(str(filepath)):
                fixed_count += 1
        else:
            print(f"⚠️  Not found: {filepath}")
    
    print(f"\n✨ Fixed {fixed_count} files automatically")
    print("\n⚙️  Running flake8 to check remaining issues...")
    import subprocess
    result = subprocess.run(['python', '-m', 'flake8', 'thinkmesh_core', '--count', '--statistics'], 
                          capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)


if __name__ == '__main__':
    main()
