"""
Analyze build failures and suggest fixes
"""
import requests
import re
from typing import Dict, List

REPO = "Awehbelekker/Universal-AI-Soul-Unlimited"

def get_build_logs(run_id: str) -> str:
    """Get build logs from GitHub Actions"""
    try:
        # Get jobs for this run
        jobs_url = f"https://api.github.com/repos/{REPO}/actions/runs/{run_id}/jobs"
        response = requests.get(jobs_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data['jobs']:
                job = data['jobs'][0]
                logs_url = job['logs_url'] if 'logs_url' in job else None
                
                if logs_url:
                    logs_response = requests.get(logs_url, timeout=30)
                    if logs_response.status_code == 200:
                        return logs_response.text
                        
                # Alternative: construct web URL for logs
                return f"View logs: {job['html_url']}"
    except Exception as e:
        return f"Error fetching logs: {e}"
    
    return "Could not retrieve logs"

def analyze_error(logs: str) -> Dict[str, any]:
    """Analyze error logs and suggest fixes"""
    analysis = {
        'errors': [],
        'fixes': [],
        'error_type': 'unknown'
    }
    
    # Common error patterns
    patterns = {
        'ndk_not_found': (
            r'NDK.*not found|Could not find NDK',
            'NDK Installation Issue',
            [
                'Add NDK installation to workflow:',
                '  - name: Install Android NDK',
                '    run: |',
                '      wget https://dl.google.com/android/repository/android-ndk-r25c-linux.zip',
                '      unzip android-ndk-r25c-linux.zip -d $HOME',
                '      echo "ANDROID_NDK_HOME=$HOME/android-ndk-r25c" >> $GITHUB_ENV'
            ]
        ),
        'sdk_license': (
            r'licenses.*not.*accepted|Accept.*SDK.*license',
            'SDK License Issue',
            [
                'Accept SDK licenses in workflow:',
                '  - name: Accept SDK licenses',
                '    run: yes | sdkmanager --licenses'
            ]
        ),
        'python_version': (
            r'Python 3\.\d+ not found|requires Python',
            'Python Version Issue',
            [
                'Verify Python setup in workflow:',
                '  - name: Set up Python',
                '    uses: actions/setup-python@v4',
                '    with:',
                '      python-version: "3.9"'
            ]
        ),
        'dependency_error': (
            r'No module named|ImportError|ModuleNotFoundError',
            'Missing Python Dependencies',
            [
                'Install missing dependencies:',
                '  pip install --upgrade -r requirements.txt'
            ]
        ),
        'buildozer_error': (
            r'buildozer.*failed|Command failed: buildozer',
            'Buildozer Build Failure',
            [
                'Common fixes:',
                '1. Clear cache and rebuild',
                '2. Update buildozer.spec requirements',
                '3. Check p4a version compatibility'
            ]
        ),
        'timeout': (
            r'timeout|timed out|exceeded.*time',
            'Build Timeout',
            [
                'Increase timeout in workflow:',
                '  timeout-minutes: 120  # Increase from 90'
            ]
        ),
        'memory_error': (
            r'MemoryError|Out of memory|killed.*memory',
            'Memory Issue',
            [
                'Add swap space or reduce build parallelism:',
                '  - name: Setup swap',
                '    run: |',
                '      sudo fallocate -l 4G /swapfile',
                '      sudo chmod 600 /swapfile',
                '      sudo mkswap /swapfile',
                '      sudo swapon /swapfile'
            ]
        )
    }
    
    # Check for each pattern
    for key, (pattern, error_type, fixes) in patterns.items():
        if re.search(pattern, logs, re.IGNORECASE):
            analysis['errors'].append(error_type)
            analysis['fixes'].extend(fixes)
            analysis['error_type'] = key
            break
    
    if not analysis['errors']:
        analysis['errors'].append('Unknown error - manual review needed')
        analysis['fixes'].append('Check full logs for details')
    
    return analysis

def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python analyze_build.py <run_id>")
        print("Or: python analyze_build.py latest")
        sys.exit(1)
    
    run_id = sys.argv[1]
    
    if run_id == 'latest':
        # Get latest run
        response = requests.get(
            f"https://api.github.com/repos/{REPO}/actions/runs",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data['workflow_runs']:
                run_id = str(data['workflow_runs'][0]['id'])
    
    print(f"📊 Analyzing build run: {run_id}\n")
    
    logs = get_build_logs(run_id)
    analysis = analyze_error(logs)
    
    print("=" * 60)
    print("🔍 ERROR ANALYSIS")
    print("=" * 60)
    
    for error in analysis['errors']:
        print(f"❌ {error}")
    
    print("\n" + "=" * 60)
    print("💡 SUGGESTED FIXES")
    print("=" * 60)
    
    for fix in analysis['fixes']:
        print(f"  {fix}")
    
    print("\n" + "=" * 60)

if __name__ == '__main__':
    main()
