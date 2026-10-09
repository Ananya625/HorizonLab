import os
import difflib
import json
import ast
from typing import Dict, Any, List, Optional

WORKSPACE_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "sandbox")
os.makedirs(WORKSPACE_ROOT, exist_ok=True)

class WorkspaceService:
    def __init__(self, root_dir: str = WORKSPACE_ROOT):
        self.root_dir = root_dir
        self.ensure_default_sandboxes()

    def ensure_default_sandboxes(self):
        """Pre-populates sample project repositories in sandbox for immediate testing."""
        login_sandbox = os.path.join(self.root_dir, "auth_service_repo")
        os.makedirs(login_sandbox, exist_ok=True)
        os.makedirs(os.path.join(login_sandbox, "app"), exist_ok=True)
        os.makedirs(os.path.join(login_sandbox, "tests"), exist_ok=True)

        req_file = os.path.join(login_sandbox, "requirements.txt")
        if not os.path.exists(req_file):
            with open(req_file, "w", encoding="utf-8") as f:
                f.write("fastapi>=0.100.0\nuvicorn>=0.23.0\npyjwt>=2.8.0\npasslib[bcrypt]>=1.7.4\npytest>=7.4.0\npytest-asyncio>=0.21.0\nhttpx>=0.24.0\n")

        main_file = os.path.join(login_sandbox, "app", "main.py")
        if not os.path.exists(main_file):
            with open(main_file, "w", encoding="utf-8") as f:
                f.write("""from fastapi import FastAPI

app = FastAPI(title="Authentication Service API", version="1.0.0")

@app.get("/health")
def health():
    return {"status": "healthy"}
""")

    def get_default_repo_path(self, preset_id: Optional[str] = None) -> str:
        return os.path.join(self.root_dir, "auth_service_repo")

    def inspect_directory(self, target_path: Optional[str] = None) -> Dict[str, Any]:
        path = target_path or self.get_default_repo_path()
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)

        files_list = []
        languages = set()
        total_loc = 0
        file_tree = []

        ignore_dirs = {".git", "__pycache__", "node_modules", ".pytest_cache", ".venv", "venv", ".idea", ".vscode"}

        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            rel_dir = os.path.relpath(root, path)
            
            for file in files:
                if file.endswith((".pyc", ".lock", ".png", ".jpg", ".ico")):
                    continue
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, path).replace("\\", "/")
                size = os.path.getsize(full_path)
                
                ext = os.path.splitext(file)[1].lower()
                lang = "Unknown"
                if ext == ".py": lang = "Python"; languages.add("Python")
                elif ext in (".js", ".jsx"): lang = "JavaScript"; languages.add("JavaScript")
                elif ext in (".ts", ".tsx"): lang = "TypeScript"; languages.add("TypeScript")
                elif ext in (".json", ".yaml", ".yml"): lang = "Config"; languages.add("Config")
                elif ext in (".md", ".txt"): lang = "Documentation"
                elif ext == ".html": lang = "HTML"
                elif ext == ".css": lang = "CSS"

                loc = 0
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                        loc = len(lines)
                        total_loc += loc
                except Exception:
                    pass

                files_list.append({
                    "path": rel_path,
                    "name": file,
                    "language": lang,
                    "size_bytes": size,
                    "lines_of_code": loc
                })

        # Detect package managers / test runners
        has_pytest = os.path.exists(os.path.join(path, "pytest.ini")) or any(f["name"] == "requirements.txt" or "test" in f["name"] for f in files_list)
        has_npm = os.path.exists(os.path.join(path, "package.json"))

        return {
            "repo_path": path,
            "exists": True,
            "total_files": len(files_list),
            "total_lines_of_code": total_loc,
            "detected_languages": list(languages) or ["Python"],
            "test_framework": "pytest" if has_pytest else ("jest/npm" if has_npm else "pytest"),
            "files": files_list
        }

    def read_file(self, repo_path: str, relative_file_path: str) -> Optional[str]:
        full_path = os.path.join(repo_path, relative_file_path)
        if not os.path.exists(full_path):
            return None
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return None

    def write_file(self, repo_path: str, relative_file_path: str, content: str) -> bool:
        full_path = os.path.join(repo_path, relative_file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True

    def compute_diff(self, original_content: Optional[str], new_content: str, filename: str) -> Dict[str, Any]:
        orig_lines = (original_content or "").splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            orig_lines,
            new_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
            lineterm=""
        )
        diff_text = "\n".join(list(diff))

        lines_added = sum(1 for line in diff_text.splitlines() if line.startswith("+") and not line.startswith("+++"))
        lines_removed = sum(1 for line in diff_text.splitlines() if line.startswith("-") and not line.startswith("---"))

        # AST syntax check for Python files
        ast_valid = True
        if filename.endswith(".py"):
            try:
                ast.parse(new_content)
                ast_valid = True
            except SyntaxError:
                ast_valid = False

        return {
            "diff_patch": diff_text if diff_text else f"--- a/{filename}\n+++ b/{filename}\n@@ -0,0 +1,{len(new_lines)} @@\n" + "\n".join([f"+{l.rstrip()}" for l in new_lines]),
            "lines_added": lines_added or len(new_lines),
            "lines_removed": lines_removed,
            "ast_valid": ast_valid
        }

    def list_sample_repositories(self) -> List[Dict[str, str]]:
        return [
            {
                "id": "sandbox_auth_repo",
                "name": "Auth Service Repository (FastAPI + JWT + Bcrypt)",
                "path": os.path.join(self.root_dir, "auth_service_repo"),
                "description": "Clean modern FastAPI microservice repository for Authentication & Access Control."
            },
            {
                "id": "sandbox_concurrency_repo",
                "name": "ConnectionPool Concurrency Sandbox",
                "path": os.path.join(self.root_dir, "connection_pool_repo"),
                "description": "High-throughput async socket and connection pool codebase with stress test suites."
            },
            {
                "id": "sandbox_sqlalchemy_repo",
                "name": "Database Handler SQLAlchemy 2.0 Sandbox",
                "path": os.path.join(self.root_dir, "db_handler_repo"),
                "description": "SQLAlchemy 2.0 async repository pattern migration sandbox."
            }
        ]

workspace_service = WorkspaceService()
