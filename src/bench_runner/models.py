from pydantic import BaseModel, Field


class FailedCase(BaseModel):
    index: int
    reason: str


class RegressionReport(BaseModel):
    summary: str
    risk: str
    verdict: str
    failed_cases: list[FailedCase] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)