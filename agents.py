from langchain.agents import create_agent
from dotenv import load_dotenv
from github import Github
from github import Auth
import os

load_dotenv() 

def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"It's always sunny in {city}!"

agent = create_agent(
    model="google_genai:gemini-3.5-flash-lite",
    tools=[get_weather],
    system_prompt="You are a helpful assistant",
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "What's the weather in New Brunswick?"}]}
)
#print(result["messages"][-1].content_blocks)

def get_username() -> str:
    """Get the GitHub username of the authenticated user."""
    auth = Auth.Token(os.getenv("PAT"))
    g = Github(auth=auth)
    username = g.get_user().login
    g.close()
    return username

def get_user_repos() -> list:
    """Get the list of repositories for the authenticated user."""
    auth = Auth.Token(os.getenv("PAT"))
    g = Github(auth=auth)
    repos = [repo for repo in g.get_user().get_repos()]
    g.close()
    return repos

def get_all_repo_files(repo) -> list:
    """Get all files in the specified repository."""
    auth = Auth.Token(os.getenv("PAT"))
    g = Github(auth=auth)
    user = g.get_user()  # Get the first repository
    branch = repo.get_branch("main")
    tree = repo.get_git_tree(branch.commit.sha, recursive=True)
    
    files_list = []
    for element in tree.tree:
        if element.type == "blob":
            files_list.append(element.path)
    
    g.close()
    return files_list


print(get_username())
all_repos = get_user_repos()

repos_hash = {}
for repo in all_repos:
    repos_hash[repo.name] = repo

class Code_review_agent:
    def __init__(self, repo_name: str):
        self.repo_name = repo_name
        self.repo = repos_hash[repo_name]
        self.files = get_all_repo_files(self.repo)

    def review_code(self):
        """Review code in the repository."""
        system_prompt = """
        You are a Staff Software Engineer conducting a thorough code review.

        Your objective: Review the provided code or Git diff for logical correctness, maintainability, performance bottlenecks, and adherence to clean architecture principles.

        Evaluation Criteria:
        - Algorithmic efficiency and resource leaks (e.g., O(N^2) iterations, unclosed file/DB handles)
        - Exception handling, unhandled edge cases (None/null references, boundary off-by-one errors)
        - Concurrency risks (race conditions, unhandled async tasks)
        - Code clarity, modularity, and adherence to language-idiomatic standards (PEP 8 for Python, etc.)

        Instructions:
        1. Do not flag trivial aesthetic preferences as blockers.
        2. Mark an issue as "BLOCKING" only if it results in runtime crashes, logic bugs, data corruption, or severe performance degradation. Mark maintainability/readability as "NON_BLOCKING".
        3. Output MUST be valid JSON matching the schema below. Do not include introductory text.

        Output Schema:
        {
        "agent": "code_quality_agent",
        "has_blocking_issues": boolean,
        "findings": [
            {
            "id": "QUAL-001",
            "category": "CORRECTNESS" | "PERFORMANCE" | "MAINTAINABILITY",
            "severity": "BLOCKING" | "NON_BLOCKING",
            "file_path": "string",
            "line_range": [start_line, end_line],
            "issue": "Concise statement of the flaw",
            "explanation": "Why this causes a bug, leak, or degradation",
            "suggested_fix": "Concrete refactoring proposal"
            }
        ]
        }
        """
        for file_path in self.files:
            print(f"Reviewing file: {file_path}")
            # Here you can add logic to read the file content and perform code review
            # For example, you can use the agent to analyze the code and provide feedback