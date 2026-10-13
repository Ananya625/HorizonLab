import re
import os
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

def is_basic_addition_request(text: str) -> bool:
    """Only the fully specified small exercise; compound requests use analysis."""
    return re.fullmatch(
        r"(?:please\s+)?(?:write|create|implement)\s+(?:a\s+)?(?:simple\s+)?"
        r"python\s+(?:code|program|function)\s+to\s+add\s+(?:two|2)\s+numbers[.!]?",
        text.strip(), re.IGNORECASE,
    ) is not None

class RoutingDecision(BaseModel):
    task_tier: str  # "simple", "medium", "complex"
    reasoning: str
    target_files: List[str] = []
    target_test_files: List[str] = []
    relevant_inspection_files: List[str] = []
    use_fast_path: bool = False
    skip_separate_planner: bool = False
    single_coding_agent: bool = False
    run_targeted_tests_only: bool = False
    model_name: str = "qwen2.5-coder:1.5b"
    security_sensitive: bool = False
    concurrency_sensitive: bool = False
    architectural_scope: str = "isolated"  # "isolated", "modular", "systemic"

class TaskRouterService:
    def route_task(
        self,
        request_text: str,
        repo_path: str,
        available_models: Optional[List[str]] = None
    ) -> RoutingDecision:
        """Lightweight, deterministic task router executed before expensive LLM calls."""
        text_lower = request_text.lower()
        
        # 1. Detect explicit complex architectural keywords
        complex_keywords = [
            "jwt", "authentication", "bearer token", "oauth2", "login api",
            "password hash", "bcrypt", "pbkdf2",
            "race condition", "concurrency", "connection pool", "connectionpool", "asyncio.lock", "deadlock",
            "cwe-", "sql injection", "path traversal", "vulnerability remediation", "ast sanitization",
            "database failover", "sqlalchemy migration", "graphql schema", "dataloader",
            "microservice"
        ]
        
        has_complex_keyword = any(k in text_lower for k in complex_keywords)
        
        # 2. Extract explicitly mentioned files
        # Matches patterns like app/service.py, tests/test_service.py, src/core/connection_pool.py, etc.
        file_matches = re.findall(r'[\'"]?([a-zA-Z0-9_\-\.\/]+\.(?:py|js|ts|json|txt))[\'"]?', request_text)
        cleaned_files = []
        for f in file_matches:
            f_norm = f.strip("'\"").replace("\\", "/")
            if "/" in f_norm or f_norm.endswith(".py"):
                if f_norm not in cleaned_files:
                    cleaned_files.append(f_norm)
        
        # Categorize code files and test files
        test_files = [f for f in cleaned_files if "test" in f.lower()]
        code_files = [f for f in cleaned_files if "test" not in f.lower()]
        
        # 3. Assess security and concurrency sensitivity
        security_sensitive = any(k in text_lower for k in ["cwe", "security", "vulnerability", "jwt", "auth", "hash", "password"])
        concurrency_sensitive = any(k in text_lower for k in ["concurrency", "race", "lock", "thread", "coroutine", "pool"])

        # Select model: default to 1.5b for speed, 7b for complex if available
        models = available_models or ["qwen2.5-coder:1.5b", "qwen2.5-coder:7b"]
        has_1_5b = any("1.5b" in m for m in models)
        has_7b = any("7b" in m for m in models)

        # 4. Routing Decision Logic
        # Never classify as simple solely because prompt is short:
        # Check actual scope, dependencies, security impact and file count.
        if has_complex_keyword or len(cleaned_files) >= 3 or security_sensitive or concurrency_sensitive:
            # Complex Task Tier: Preserves existing multi-agent workflow
            chosen_model = "qwen2.5-coder:7b" if has_7b else (models[0] if models else "qwen2.5-coder:1.5b")
            return RoutingDecision(
                task_tier="complex",
                reasoning="Task involves multi-file architecture, cryptographic security, concurrency synchronization, or cross-subsystem orchestration. Full multi-agent evaluation pipeline required.",
                target_files=cleaned_files,
                target_test_files=test_files or ["tests"],
                relevant_inspection_files=cleaned_files,
                use_fast_path=False,
                skip_separate_planner=False,
                single_coding_agent=False,
                run_targeted_tests_only=False,
                model_name=chosen_model,
                security_sensitive=security_sensitive,
                concurrency_sensitive=concurrency_sensitive,
                architectural_scope="systemic"
            )

        elif len(cleaned_files) == 2 and any("test" in f.lower() for f in cleaned_files):
            # Simple Isolated Task Tier: Fast Path!
            # Exactly 1 implementation file + 1 test file (e.g. app/service.py and tests/test_service.py)
            chosen_model = "qwen2.5-coder:1.5b" if has_1_5b else (models[0] if models else "qwen2.5-coder:7b")
            return RoutingDecision(
                task_tier="simple",
                reasoning="Isolated change bounded to a single target implementation file and dedicated test file with zero cross-system security dependencies.",
                target_files=cleaned_files,
                target_test_files=test_files,
                relevant_inspection_files=cleaned_files,
                use_fast_path=True,
                skip_separate_planner=True,
                single_coding_agent=True,
                run_targeted_tests_only=True,
                model_name=chosen_model,
                security_sensitive=False,
                concurrency_sensitive=False,
                architectural_scope="isolated"
            )

        elif len(cleaned_files) <= 1:
            # Check if prompt describes a small function, bug fix, or utility
            simple_intent = is_basic_addition_request(request_text) or any(w in text_lower for w in [
                "add a function", "add function", "helper function", "fix bug", "small fix",
                "add method", "implement a function", "write a function", "multiply", "calculate",
                "format", "validate", "utility"
            ])
            
            if simple_intent and not security_sensitive and not concurrency_sensitive:
                target_code = code_files[0] if code_files else "app/service.py"
                target_test = test_files[0] if test_files else "tests/test_service.py"
                chosen_model = "qwen2.5-coder:1.5b" if has_1_5b else (models[0] if models else "qwen2.5-coder:7b")
                
                return RoutingDecision(
                    task_tier="simple",
                    reasoning="Single-function isolated implementation or bug fix. Can be cleanly satisfied with fast-path single-agent execution and targeted test verification.",
                    target_files=[target_code, target_test],
                    target_test_files=[target_test],
                    relevant_inspection_files=[target_code, target_test],
                    use_fast_path=True,
                    skip_separate_planner=True,
                    single_coding_agent=True,
                    run_targeted_tests_only=True,
                    model_name=chosen_model,
                    security_sensitive=False,
                    concurrency_sensitive=False,
                    architectural_scope="isolated"
                )

        # Default to Medium Task Tier (Modular)
        chosen_model = "qwen2.5-coder:1.5b" if has_1_5b else (models[0] if models else "qwen2.5-coder:7b")
        return RoutingDecision(
            task_tier="medium",
            reasoning="Multi-component modular modification requiring architectural alignment and comprehensive regression testing.",
            target_files=cleaned_files or ["app/service.py", "tests/test_service.py"],
            target_test_files=test_files or ["tests"],
            relevant_inspection_files=cleaned_files,
            use_fast_path=False,
            skip_separate_planner=False,
            single_coding_agent=True,
            run_targeted_tests_only=False,
            model_name=chosen_model,
            security_sensitive=security_sensitive,
            concurrency_sensitive=concurrency_sensitive,
            architectural_scope="modular"
        )

task_router_service = TaskRouterService()
