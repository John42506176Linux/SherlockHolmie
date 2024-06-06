from typing import Optional
from pydantic import BaseModel

class InsightParams(BaseModel):
    space: str
    query: str
    fast: Optional[bool] = True
    threshold: Optional[float] = 0.55