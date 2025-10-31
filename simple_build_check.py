#!/usr/bin/env python3
import requests

# Fetch recent builds
r = requests.get(
    'https://api.github.com/repos/Awehbelekker/Universal-AI-Soul-Unlimited/actions/runs',
    headers={'Accept': 'application/vnd.github.v3+json'},
    params={'per_page': 5}
)

if r.status_code == 200:
    data = r.json()
    print("\nRecent Builds:")
    print("=" * 80)
    for run in data['workflow_runs']:
        print(f"Build #{run['run_number']}: {run['status']} - {run.get('conclusion', 'N/A')}")
        print(f"  Branch: {run['head_branch']}")
        print(f"  Commit: {run['head_commit']['message'][:60]}")
        print(f"  URL: {run['html_url']}")
        print()
else:
    print(f"Error: {r.status_code}")
