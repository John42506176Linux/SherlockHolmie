from typing import Optional
from pydantic import BaseModel

class SpaceParams(BaseModel):
    space: str
    perspective: str
    context: str
    fast: Optional[bool] = True
    threshold: Optional[float] = 0.55
    batch_size: Optional[int] = 50