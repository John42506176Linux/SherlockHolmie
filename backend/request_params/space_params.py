from typing import Optional
from pydantic import BaseModel

class SpaceParams(BaseModel):
    space: str
    perspective: str
    context: str
    threshold: Optional[float] = 0.50
    batch_size: Optional[int] = 50
    concurrency: Optional[int] = 5
    perspective_specific: Optional[bool] = True
    request_id:int