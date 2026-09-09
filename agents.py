from langchain.agents import create_agent
from dotenv import load_dotenv
from github import Github
from github import Auth
import os
from langchain.tools import tool
from langchain.chat_models import init_chat_model
import subprocess
import json

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

username = get_username()
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
        self.username = get_username()

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

    
    def get_list_py_files(self) -> list:
        """Return a list of all Python files in the repository."""
        return [file for file in self.files if file.endswith(".py")]

    def get_py_file_content(self, file_path: str) -> str:
        """Get the content of a Python file in the repository."""
        auth = Auth.Token(os.getenv("PAT"))
        g = Github(auth=auth)
        repo = g.get_repo(self.username + '/' + self.repo_name)
        file_content = repo.get_contents(file_path).decoded_content.decode("utf-8")
        g.close()
        return file_content
    
    def code_review_tool_linter(self, code_string: str) -> list:
        """Run ruff on the input code_string and return output."""
        result = subprocess.run(
            ["ruff", "check", "-", "--output-format=json"],
            input=code_string,
            text=True,
            capture_output=True
        )
        if result.stdout:
            return_string = json.loads(result.stdout)
            return return_string
        return []

    def clean_code_review_data(self, code_review_data: list) -> list:
        """Cleans data from linter, extracting only needed information"""
        cleaned_findings = []
        for data in code_review_data:
            suggested_fix = None
            if data['fix'] != None:
                suggested_fix = data['fix']
            cleaned_findings.append({
                "line": data['location']['row'],
                "rule": data['code'],
                "message": data['message'],
                "suggested_fix": suggested_fix if suggested_fix else "REQUIRES_LLM_RESOLUTION"
            })
            print(cleaned_findings)
        return cleaned_findings

    model = init_chat_model(
        "gemini-3.5-flash-lite",
        model_provider="google-genai",
        temperature=0.5,
        timeout=600,
        max_tokens=25000,
        streaming=True,
    )

cra = Code_review_agent(repo_name="AreaCompAgent")
py_files = cra.get_list_py_files()
cra.get_py_file_content(py_files[0])
file_content = cra.get_py_file_content(py_files[2])
review_tool_data = cra.code_review_tool_linter(code_string=file_content)
cra.clean_code_review_data(review_tool_data)