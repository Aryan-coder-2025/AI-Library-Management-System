from pydantic import BaseModel, ConfigDict
from typing import Optional


class HealthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    project_name: str
    environment: str
    database: str
