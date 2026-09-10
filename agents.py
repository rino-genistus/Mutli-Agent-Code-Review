from langchain.agents import create_agent
from dotenv import load_dotenv
from github import Github
from github import Auth
from github import Repository
import os
from langchain.tools import tool
from langchain.chat_models import init_chat_model
import subprocess
import json
import shutil
import tempfile
import ast

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

class GithubService:
    def __init__(self, token: str | None = None):
        self._token = token or os.getenv("PAT")
        if not self._token:
            raise ValueError("Need Token for Github Services")
        self.auth = Auth.Token(self._token)
        self.g = Github(auth=self.auth)
        self.username = self.g.get_user().login

    def get_user_repos(self):
        """Get the list of repositories for the authenticated user."""
        return [repo for repo in self.g.get_user().get_repos()]

    def get_repo(self, repo_name: str) -> Repository.Repository:
        """Get the full name of the repository name"""
        full_name = repo_name if "/" in repo_name else f"{self.username}/{repo_name}"
        return self.g.get_repo(full_name)

    def get_all_repo_files(self, repo, branch: str = "main") -> list:
        """Get all files in the specified repository."""
        repo_branch = repo.get_branch(branch)
        tree = repo.get_git_tree(repo_branch.commit.sha, recursive=True)

        files_list = []
        for element in tree.tree:
            if element.type == "blob":
                files_list.append(element.path)

        return files_list

    

    def close(self):
        """Closes the underlying HTTP session cleanly."""
        self.g.close()
        

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
        self.files_cache: dict[str, str] = {}
        self._temp_dir: str | None = None

    def populate_cache(self, files: dict[str, str]):
        """Call when downloading files from PyGithub"""
        self.files_cache = files

    def _ensure_local_workspace(self) -> str:
        """Writes in-memory files to an ephemeral disk directory for CLI tools."""
        if self._temp_dir and os.path.exists(self._temp_dir):
            return self._temp_dir

        self._temp_dir = tempfile.mkdtemp(prefix="agent_review_")

        for rel_path, content in self.files_cache.items():
            dest_path = os.path.join(self._temp_dir, rel_path)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, "w", encoding="utf-8") as f:
                f.write(content)

        return self._temp_dir

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

    
    def get_list_py_files(self) -> list: #Tested and Works
        """Return a list of all Python files in the repository."""
        return [file for file in self.files if file.endswith(".py")]

    def get_py_file_content(self, file_path: str) -> str: #Tested and Works
        """Get the content of a Python file in the repository."""
        auth = Auth.Token(os.getenv("PAT"))
        g = Github(auth=auth)
        repo = g.get_repo(self.username + '/' + self.repo_name)
        file_content = repo.get_contents(file_path).decoded_content.decode("utf-8")
        g.close()
        return file_content
    
    def code_review_tool_linter(self, code_string: str) -> list: #Tested and Works
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

    def clean_code_review_data(self, code_review_data: list) -> list: #Tested and Works
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

    def read_file_window(self, file_path: str, start_line: int, end_line: int) -> str: #Tested and Works
        """Gets requested context window from requested file"""
        return "\n".join(self.get_py_file_content(file_path).splitlines()[max(0, start_line - 1):end_line])

    def find_symbol_definition(self, symbol_name: str) -> list[dict]: #Tested and Works
        working_dir = self._ensure_local_workspace()
        pattern = rf"^\s*(def|class)\s+{symbol_name}\b"
        cmd = ["rg", "--json", "-e", pattern, working_dir]
        result = subprocess.run(cmd, capture_output=True, text=True)

        matches = []
        for line in result.stdout.splitlines():
            data = json.loads(line)
            if data.get("type") == "match":
                match_info = data["data"]
                raw_path = match_info["path"]["text"]

                # Convert back to clean repo-relative path
                relative_file = os.path.relpath(raw_path, working_dir)

                matches.append({
                    "symbol": symbol_name,
                    "file": relative_file,
                    "line": match_info["line_number"],
                    "line_text": match_info["lines"]["text"].strip(),
                })

        return matches

    def cleanup(self): #Tested and Works
        """Deletes temporary workspace when the review finishes."""
        if self._temp_dir and os.path.exists(self._temp_dir):
            shutil.rmtree(self._temp_dir)
            self._temp_dir = None

    def ast_extract_all_functions(self, code_string: str) -> list[dict]:
        """Yields every function in no particular order"""
        tree = ast.parse(code_string)
        functions = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append({
                    "function_name": node.name,
                    "start_line_number": node.lineno,
                    "end_line_number": node.end_lineno, 
                    "args": [a.arg for a in node.args.args if a.arg != "self"],
                    "docstring": ast.get_docstring(node)
                })
        return functions

    class OutlineVisitor(ast.NodeVisitor):
        def __init__(self):
            self.classes = []
            self.functions = []
            self._current_class = None

        def visit_ClassDef(self, node: ast.ClassDef):
            prev_class = self._current_class
            self._current_class = node.name
            self.classes.append({
                "class_name": node.name,
                "line": node.lineno,
                "methods": []
            })
            # Continue traversing inside the class body
            self.generic_visit(node)
            self._current_class = prev_class

        def visit_FunctionDef(self, node: ast.FunctionDef):
            fn_data = {
                "name": node.name,
                "line": node.lineno,
                "args": [arg.arg for arg in node.args.args]
            }
            if self._current_class:
                # Nested inside a class -> record as method
                self.classes[-1]["methods"].append(fn_data)
            else:
                # Top-level standalone function
                self.functions.append(fn_data)
            self.generic_visit(node)

    model = init_chat_model(
        "gemini-3.5-flash-lite",
        model_provider="google-genai",
        temperature=0.5,
        timeout=600,
        max_tokens=25000,
        streaming=True,
    )

cra = Code_review_agent(repo_name="AreaCompAgent")
python_files = cra.get_list_py_files()
file_dict = {}
for file in python_files:
    file_dict[file] = cra.get_py_file_content(file)
cra.populate_cache(file_dict) #Populate Cache for Ripgrep functions with the dictionary of file and file content
symbol_def_results = cra.find_symbol_definition("load_data")
print(symbol_def_results)
cra.cleanup()
cra.ast_code_structure()