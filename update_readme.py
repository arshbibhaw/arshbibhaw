import os
import re
import requests
from datetime import datetime

# Environment Variables Setup
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
VERCEL_TOKEN = os.getenv('VERCEL_TOKEN')
VERCEL_PROJECT_ID = os.getenv('VERCEL_PROJECT_ID')

headers_github = {
    "Authorization": f"Bearer {GITHUB_TOKEN}" if GITHUB_TOKEN else "",
    "Accept": "application/vnd.github.v3+json"
}

def get_github_stats(username):
    # Fetch user data
    user_resp = requests.get(f"https://api.github.com/users/{username}", headers=headers_github)
    user_data = user_resp.json()
    public_repos = user_data.get("public_repos", 0)

    # Fetch all repos to calculate total stars
    repos_url = f"https://api.github.com/users/{username}/repos?per_page=100"
    repos_resp = requests.get(repos_url, headers=headers_github)
    repos = repos_resp.json()
    
    total_stars = 0
    if isinstance(repos, list):
        total_stars = sum(repo.get("stargazers_count", 0) for repo in repos)
    else:
        repos = []
    
    return public_repos, total_stars, repos

def get_vercel_views():
    if not VERCEL_TOKEN or not VERCEL_PROJECT_ID:
        return None

    # Fetch total visits count
    url = "https://api.vercel.com/v1/query/web-analytics/visits/count"
    headers = {
        "Authorization": f"Bearer {VERCEL_TOKEN}"
    }
    params = {
        "projectId": VERCEL_PROJECT_ID
    }
    
    try:
        resp = requests.get(url, headers=headers, params=params)
        data = resp.json()
        if "count" in data:
            return data["count"]
        return None
    except Exception as e:
        print(f"Error fetching Vercel Analytics: {e}")
        return None

def generate_projects_table(repos):
    # Filter out forks and sort by pushed_at descending (most recently active)
    active_repos = [r for r in repos if not r.get("fork", False) and r.get("pushed_at")]
    active_repos.sort(key=lambda x: datetime.strptime(x["pushed_at"], "%Y-%m-%dT%H:%M:%SZ"), reverse=True)
    
    # Pick top 7 projects
    top_repos = active_repos[:7]
    
    table = "| Project | Description | Tech Stack | Links |\n"
    table += "|---|---|---|---|\n"
    
    for repo in top_repos:
        name = repo.get("name", "")
        description = repo.get("description", "") or "No description provided."
        url = repo.get("html_url", "")
        homepage = repo.get("homepage", "")
        
        # Determine Tech Stack (Using language and topics)
        language = repo.get("language")
        topics = repo.get("topics", [])
        tech_stack = []
        if language: tech_stack.append(language)
        tech_stack.extend([t.replace("-", " ").title() for t in topics[:3]]) # limit to 3 topics
        
        tech_stack_str = ", ".join(tech_stack) if tech_stack else "N/A"
        
        # Links
        links = f"[GitHub]({url})"
        if homepage:
            links = f"[Live]({homepage}) · " + links
            
        table += f"| **{name}** | {description} | {tech_stack_str} | {links} |\n"
        
    return table

# Custom PR Descriptions
CUSTOM_PR_DESCRIPTIONS = {
    "https://github.com/emmabostian/developer-portfolios/pull/3882": "Added DevHQ to the open-source developer portfolio directory",
    "https://github.com/Evavic44/portfolio-ideas/pull/677": "Added DevHQ to an open-source repository for inspiration of awesome portfolio ideas",
    "https://github.com/Quills-n-Stills-IIIT-KOTA/Q-n-S-Wbsite/pull/1": "Implemented the 'Connect-with-Us' Section and Enhanced the STRUCTURE.md file",
    "https://github.com/Quills-n-Stills-IIIT-KOTA/Interactive-Live-quiz-for-events-/pull/1": "Enhanced UI/UX Modernization, Independence Day Theme, and Performance Fixes"
}

def get_merged_prs(username):
    url = f"https://api.github.com/search/issues?q=is:pr+is:merged+author:{username}+-user:{username}&sort=updated&order=desc&per_page=10"
    try:
        resp = requests.get(url, headers=headers_github)
        data = resp.json()
        items = data.get("items", [])
        
        if not items:
            return ""
            
        table = "| Repository | Contribution | Status | Pull Request |\n"
        table += "|---|---|---|---|\n"
        
        for item in items:
            pr_url = item.get("html_url")
            pr_title = item.get("title")
            pr_number = item.get("number")
            repo_url = item.get("repository_url", "").replace("api.github.com/repos/", "github.com/")
            repo_name = repo_url.split("github.com/")[-1]
            
            # Use custom description if available, otherwise fallback to PR title
            description = CUSTOM_PR_DESCRIPTIONS.get(pr_url, pr_title)
            
            table += f"| [`{repo_name}`]({repo_url}) | {description} | Merged | [#{pr_number}]({pr_url}) |\n"
            
        return table
    except Exception as e:
        print(f"Error fetching PRs: {e}")
        return ""

def update_readme():
    # Use GITHUB_REPOSITORY_OWNER if available (in GitHub Actions), else default to 'arshbibhaw'
    username = os.getenv("GITHUB_REPOSITORY_OWNER", "arshbibhaw")
    
    print("Fetching GitHub Stats...")
    public_repos, total_stars, repos = get_github_stats(username)
    
    print("Fetching Vercel Analytics...")
    vercel_views = get_vercel_views()
    
    print("Fetching Open Source PRs...")
    prs_table = get_merged_prs(username)
    
    # Generate new content
    projects_table = generate_projects_table(repos)
    
    # Read README
    with open("README.md", "r", encoding="utf-8") as f:
        readme = f.read()
    
    # Replace Projects
    projects_pattern = re.compile(r"<!-- START_PROJECTS -->.*?<!-- END_PROJECTS -->", re.DOTALL)
    new_projects_section = f"<!-- START_PROJECTS -->\n{projects_table}<!-- END_PROJECTS -->"
    readme = projects_pattern.sub(new_projects_section, readme)
    
    # Replace Open Source PRs
    if prs_table:
        prs_pattern = re.compile(r"<!-- START_OPEN_SOURCE -->.*?<!-- END_OPEN_SOURCE -->", re.DOTALL)
        new_prs_section = f"<!-- START_OPEN_SOURCE -->\n{prs_table}<!-- END_OPEN_SOURCE -->"
        readme = prs_pattern.sub(new_prs_section, readme)
    
    # Update GitHub Repositories count dynamically in the stats table
    repo_row_pattern = re.compile(r"\| GitHub Repositories \| .*? \| Public \|")
    readme = repo_row_pattern.sub(f"| GitHub Repositories | {public_repos} | Public |", readme)
    
    if vercel_views is not None:
        # Update Portfolio Page Views
        views_row_pattern = re.compile(r"\| Portfolio Page Views \| .*? \| Page Views \(Last 30 days\) \|")
        # Format the number with commas (e.g., 5,750)
        formatted_views = f"{vercel_views:,}"
        readme = views_row_pattern.sub(f"| Portfolio Page Views | {formatted_views}+ | Page Views (Last 30 days) |", readme)
    
    # Write back
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme)
    
    print("README.md updated successfully!")

if __name__ == "__main__":
    update_readme()
