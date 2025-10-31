import requests
import sys

run_id = "18877151441"  # Build #2
REPO = "Awehbelekker/Universal-AI-Soul-Unlimited"

print(f"Fetching logs for Build #2 (run {run_id})...\n")

# Get jobs
jobs_url = f"https://api.github.com/repos/{REPO}/actions/runs/{run_id}/jobs"
response = requests.get(jobs_url, timeout=10)

if response.status_code == 200:
    data = response.json()
    if data['jobs']:
        job = data['jobs'][0]
        
        print("=" * 70)
        print("JOB DETAILS")
        print("=" * 70)
        print(f"Job Name: {job['name']}")
        print(f"Status: {job['status']}")
        print(f"Conclusion: {job.get('conclusion', 'N/A')}")
        print(f"Started: {job.get('started_at', 'N/A')}")
        print(f"Completed: {job.get('completed_at', 'N/A')}")
        print(f"\nView full logs: {job['html_url']}")
        
        # Get steps
        print("\n" + "=" * 70)
        print("BUILD STEPS")
        print("=" * 70)
        
        for step in job['steps']:
            status_emoji = {
                'completed': '✅' if step.get('conclusion') == 'success' else '❌',
                'in_progress': '🔵',
                'queued': '🟡'
            }.get(step['status'], '⚪')
            
            conclusion = step.get('conclusion', 'N/A')
            print(f"\n{status_emoji} {step['name']}")
            print(f"   Status: {step['status']} | Conclusion: {conclusion}")
            
            if conclusion == 'failure':
                print(f"   ⚠️  THIS STEP FAILED!")
                print(f"   Started: {step.get('started_at', 'N/A')}")
                print(f"   Completed: {step.get('completed_at', 'N/A')}")
        
        print("\n" + "=" * 70)
        print("NEXT STEPS")
        print("=" * 70)
        print(f"1. Visit: {job['html_url']}")
        print("2. Click on the failed step to see detailed error logs")
        print("3. Look for error keywords: 'ERROR', 'FAILED', 'fatal'")
    else:
        print("No jobs found for this run")
else:
    print(f"Failed to fetch jobs: HTTP {response.status_code}")
