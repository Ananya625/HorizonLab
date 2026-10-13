import uuid
from typing import Dict, Optional, List, Any
from datetime import datetime
from ..models.schema import GoalModel, AuditEntry, RunRecord
from .db import db_service

class StorageService:
    def generate_run_id(self) -> str:
        return f"run_{uuid.uuid4().hex[:8]}"

    def generate_task_id(self) -> str:
        return f"task_{uuid.uuid4().hex}"

    def save_goal_model(self, model: GoalModel) -> GoalModel:
        return db_service.save_goal_model(model)

    def get_goal_model(self, run_id: str) -> Optional[GoalModel]:
        return db_service.get_goal_model(run_id)

    def get_run_history(self, run_id: str) -> List[Dict[str, Any]]:
        return db_service.get_goal_model_history(run_id)

    def list_all_runs(self) -> List[Dict[str, Any]]:
        return db_service.list_all_runs()

storage_service = StorageService()
