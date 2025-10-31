"""Quick build checker with periodic updates"""
import requests
import time
from datetime import datetime

REPO = "Awehbelekker/Universal-AI-Soul-Unlimited"

def check_build():
    """Check current build status"""
    try:
        response = requests.get(
            f"https://api.github.com/repos/{REPO}/actions/runs",
            timeout=10
        )
        if response.status_code == 200:
            run = response.json()['workflow_runs'][0]
            return {
                'number': run['run_number'],
                'status': run['status'],
                'conclusion': run.get('conclusion'),
                'url': run['html_url'],
                'id': run['id']
            }
    except:
        pass
    return None

# Check every minute for 15 minutes
print("🔍 Checking build status every 60 seconds...\n")

for i in range(15):
    build = check_build()
    if build:
        timestamp = datetime.now().strftime("%H:%M:%S")
        status_emoji = {
            'queued': '🟡',
            'in_progress': '🔵',
            'completed': '✅' if build['conclusion'] == 'success' else '❌'
        }.get(build['status'], '⚪')
        
        print(f"[{timestamp}] {status_emoji} Build #{build['number']}: "
              f"{build['status'].upper()}", end='')
        
        if build['conclusion']:
            print(f" - {build['conclusion'].upper()}")
        else:
            print()
        
        if build['status'] == 'completed':
            print(f"\n{'='*60}")
            if build['conclusion'] == 'success':
                print("✅ BUILD SUCCESSFUL!")
            elif build['conclusion'] == 'failure':
                print("❌ BUILD FAILED - Check logs")
            print(f"🔗 {build['url']}")
            print('='*60)
            break
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Could not fetch status")
    
    if i < 14:
        time.sleep(60)

print("\n✓ Status check complete")
