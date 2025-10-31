import requests

runs = requests.get('https://api.github.com/repos/Awehbelekker/Universal-AI-Soul-Unlimited/actions/runs').json()['workflow_runs'][:10]

print("Last 10 builds:")
print("=" * 80)
for r in runs:
    status_emoji = {
        'completed': '✅' if r.get('conclusion') == 'success' else '❌',
        'in_progress': '🔵',
        'queued': '🟡'
    }.get(r['status'], '⚪')
    
    print(f"{status_emoji} Build #{r['run_number']}: {r['status']} - {r.get('conclusion', 'N/A')}")
    print(f"   {r['html_url']}")
    print()
