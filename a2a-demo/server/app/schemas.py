from typing import TypedDict, Optional, List

class AgentState(TypedDict):
    input: str
    route: Optional[List[str]]
    reason: Optional[str]
    logs_result: Optional[str]
    metrics_result: Optional[str]
    final_answer: Optional[str]