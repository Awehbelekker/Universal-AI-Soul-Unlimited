"""
Fetch GitHub Actions build logs to diagnose issues
"""
import requests
import sys

REPO_OWNER = "Awehbelekker"
REPO_NAME = "Universal-AI-Soul-Unlimited"

def get_latest_run():
    """Get the latest workflow run"""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/runs"
    response = requests.get(url, headers={"Accept": "application/vnd.github.v3+json"})
    
    if response.status_code == 200:
        data = response.json()
        if data.get("workflow_runs"):
            return data["workflow_runs"][0]
    return None

def get_jobs(run_id):
    """Get jobs for a workflow run"""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/runs/{run_id}/jobs"
    response = requests.get(url, headers={"Accept": "application/vnd.github.v3+json"})
    
    if response.status_code == 200:
        return response.json().get("jobs", [])
    return []

def analyze_failure():
    """Analyze the build failure"""
    print("🔍 Analyzing build failure...\n")
    
    run = get_latest_run()
    if not run:
        print("❌ Could not fetch workflow run")
        return
    
    print(f"📋 Workflow: {run['name']}")
    print(f"🔗 URL: {run['html_url']}\n")
    
    jobs = get_jobs(run['id'])
    
    for job in jobs:
        print(f"\n{'='*60}")
        print(f"Job: {job['name']}")
        print(f"Status: {job['status']} - {job['conclusion']}")
        print(f"{'='*60}\n")
        
        if job['conclusion'] == 'failure':
            print("❌ Failed Steps:")
            for step in job['steps']:
                if step['conclusion'] == 'failure':
                    print(f"\n  ⚠️  Step: {step['name']}")
                    print(f"     Status: {step['conclusion']}")
                    print(f"     Started: {step.get('started_at', 'N/A')}")
                    print(f"     Completed: {step.get('completed_at', 'N/A')}")
            
            print(f"\n💡 View detailed logs at: {run['html_url']}")

if __name__ == "__main__":
    analyze_failure()
