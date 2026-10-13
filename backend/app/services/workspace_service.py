from .workflow_service import observed, workflow
import os
import difflib
import json
import ast
import hashlib
from pathlib import Path, PureWindowsPath
from typing import Dict, Any, List, Optional
from .telemetry_service import telemetry_manager

WORKSPACE_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "sandbox")
os.makedirs(WORKSPACE_ROOT, exist_ok=True)

class WorkspaceService:
    def validate_repo(self, repo_path: str) -> str:
        """Resolve repositories against operator-controlled roots, never client input."""
        root = Path(repo_path).resolve()
        allowed = [Path(self.root_dir).resolve()]
        allowed.extend(Path(p).resolve() for p in os.environ.get('AGENTEVAL_ALLOWED_REPO_ROOTS', '').split(os.pathsep) if p)
        if not any(root == base or root.is_relative_to(base) for base in allowed):
            raise ValueError('Repository is outside the allowed workspace roots')
        return str(root)

    @staticmethod
    def resolve_path(repo_path: str, relative_file_path: str) -> Path:
        root = Path(repo_path).resolve()
        portable = relative_file_path.replace('\\', '/')
        if not portable or PureWindowsPath(portable).drive or portable.startswith('/'):
            raise ValueError('Expected a workspace-relative path')
        parts = portable.split('/')
        reserved = {'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1, 10)), *(f'lpt{i}' for i in range(1, 10))}
        if any(p.casefold() in ('..', '.git', '.evaluator') or ':' in p or p.endswith((' ', '.')) or p.split('.')[0].casefold() in reserved for p in parts):
            raise ValueError('Path is outside the permitted workspace files')
        target = (root / portable).resolve()
        if target == root or not target.is_relative_to(root):
            raise ValueError('Path escapes the workspace')
        return target

    def digest(self, repo_path: str) -> str:
        """Fingerprint observable source state; generated reports/caches are excluded."""
        root = Path(repo_path).resolve()
        if not root.is_dir():
            raise ValueError('Workspace does not exist')
        digest = hashlib.sha256()
        for path in sorted(root.rglob('*')):
            relative = path.relative_to(root)
            if any(p.casefold() in {'.git', '.evaluator', '.pytest_cache', '__pycache__', '.venv', 'node_modules'} for p in relative.parts):
                continue
            if path.is_file():
                # Read existing names portably, without imposing write-name rules.
                # Symlinks are never followed into other repositories.
                if path.is_symlink() or not path.resolve().is_relative_to(root):
                    continue
                digest.update(relative.as_posix().encode())
                digest.update(path.read_bytes())
        return digest.hexdigest()
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

    def create_task_workspace(self, task_id: str, run_id: Optional[str] = None) -> str:
        """Creates a brand-new clean isolated workspace folder for a new coding task."""
        clean_id = run_id or task_id or "task_default"
        folder_name = f"workspace_{clean_id}"
        workspace_path = os.path.join(self.root_dir, folder_name)
        os.makedirs(workspace_path, exist_ok=True)
        os.makedirs(os.path.join(workspace_path, "app"), exist_ok=True)
        os.makedirs(os.path.join(workspace_path, "tests"), exist_ok=True)

        req_file = os.path.join(workspace_path, "requirements.txt")
        if not os.path.exists(req_file):
            with open(req_file, "w", encoding="utf-8") as f:
                f.write("fastapi>=0.100.0\nuvicorn>=0.23.0\npyjwt>=2.8.0\npasslib[bcrypt]>=1.7.4\npytest>=7.4.0\npytest-asyncio>=0.21.0\nhttpx>=0.24.0\n")

        pytest_ini = os.path.join(workspace_path, "pytest.ini")
        if not os.path.exists(pytest_ini):
            with open(pytest_ini, "w", encoding="utf-8") as f:
                f.write("[pytest]\npythonpath = . app\n")

        main_file = os.path.join(workspace_path, "app", "main.py")
        if not os.path.exists(main_file):
            with open(main_file, "w", encoding="utf-8") as f:
                f.write('''from fastapi import FastAPI

app = FastAPI(title="Task Service API", version="1.0.0")

@app.get("/health")
def health():
    return {"status": "healthy"}
''')

        app_init = os.path.join(workspace_path, "app", "__init__.py")
        if not os.path.exists(app_init):
            with open(app_init, "w", encoding="utf-8") as f:
                f.write("")

        tests_init = os.path.join(workspace_path, "tests", "__init__.py")
        if not os.path.exists(tests_init):
            with open(tests_init, "w", encoding="utf-8") as f:
                f.write("")

        return workspace_path

    @observed('inspect_directory', 'tool', reason=None)
    def inspect_directory(self, target_path: Optional[str] = None, run_id: Optional[str] = None) -> Dict[str, Any]:
        path = self.validate_repo(target_path or self.get_default_repo_path())
        if not os.path.isdir(path):
            raise ValueError('Workspace does not exist or is not a directory')

        files_list = []
        languages = set()
        total_loc = 0

        ignore_dirs = {".git", "__pycache__", "node_modules", ".pytest_cache", ".venv", "venv", ".idea", ".vscode"}

        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not Path(root, d).is_symlink()]
            rel_dir = os.path.relpath(root, path)
            
            for file in files:
                if file.endswith((".pyc", ".lock", ".png", ".jpg", ".ico")):
                    continue
                full_path = os.path.join(root, file)
                if Path(full_path).is_symlink():
                    continue
                rel_path = os.path.relpath(full_path, path).replace("\\", "/")
                try:
                    size = os.path.getsize(full_path)
                except OSError:
                    continue
                
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

        if run_id:
            tracker = telemetry_manager.get(run_id)
            if tracker:
                tracker.record_files_inspected(len(files_list))

        return {
            "repo_path": path,
            "exists": True,
            "total_files": len(files_list),
            "total_lines_of_code": total_loc,
            "detected_languages": list(languages) or ["Python"],
            "test_framework": "pytest" if has_pytest else ("jest/npm" if has_npm else "pytest"),
            "files": files_list
        }

    @observed('inspect_targeted', 'tool', reason=None)
    def inspect_targeted(self, target_path: Optional[str] = None, file_list: Optional[List[str]] = None, run_id: Optional[str] = None) -> Dict[str, Any]:
        """Lightweight targeted inspection for isolated changes: stats only relevant files."""
        path = self.validate_repo(target_path or self.get_default_repo_path())
        if not os.path.isdir(path):
            raise ValueError('Workspace does not exist or is not a directory')

        files_list = []
        languages = set()
        total_loc = 0

        targets = file_list or []
        for rel_file in targets:
            rel_norm = rel_file.replace("\\", "/")
            full_path = self.resolve_path(path, rel_norm)
            if os.path.exists(full_path) and os.path.isfile(full_path):
                size = os.path.getsize(full_path)
                ext = os.path.splitext(rel_norm)[1].lower()
                lang = "Python" if ext == ".py" else ("JavaScript" if ext in (".js", ".jsx") else "Unknown")
                languages.add(lang)
                loc = 0
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                        loc = len(lines)
                        total_loc += loc
                except Exception:
                    pass
                files_list.append({
                    "path": rel_norm,
                    "name": os.path.basename(rel_norm),
                    "language": lang,
                    "size_bytes": size,
                    "lines_of_code": loc
                })
            else:
                # Target file to be created
                files_list.append({
                    "path": rel_norm,
                    "name": os.path.basename(rel_norm),
                    "language": "Python" if rel_norm.endswith(".py") else "Unknown",
                    "size_bytes": 0,
                    "lines_of_code": 0
                })

        has_pytest = os.path.exists(os.path.join(path, "pytest.ini")) or os.path.exists(os.path.join(path, "requirements.txt")) or any("test" in f["name"] for f in files_list)

        if run_id:
            tracker = telemetry_manager.get(run_id)
            if tracker:
                tracker.record_files_inspected(len(files_list))

        return {
            "repo_path": path,
            "exists": True,
            "total_files": len(files_list),
            "total_lines_of_code": total_loc,
            "detected_languages": list(languages) or ["Python"],
            "test_framework": "pytest" if has_pytest else "pytest",
            "files": files_list
        }

    @observed('file_read', 'tool', reason=None)
    def read_file(self, repo_path: str, relative_file_path: str) -> Optional[str]:
        full_path = self.resolve_path(repo_path, relative_file_path)
        if not os.path.exists(full_path):
            return None
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError as exc:
            raise ValueError(f'Cannot read workspace file: {relative_file_path}') from exc

    @observed('file_write', 'tool', reason=None)
    def write_file(self, repo_path: str, relative_file_path: str, content: str) -> bool:
        full_path = self.resolve_path(repo_path, relative_file_path)
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
            "diff_patch": diff_text,
            "lines_added": lines_added,
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
