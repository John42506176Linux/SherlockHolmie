from pydantic import BaseModel
from datetime import datetime
from typing import List

class PainPoint(BaseModel):
    PainPoint: str
    Description: str
    Reasoning: str
    Quote: str
    Link: str
    Time: datetime

class PainPointsModel(BaseModel):
    PainPoints: List[PainPoint]