from app.agent.nodes.check_citations import NOT_FOUND_MESSAGE
from app.agent.state import AgentState


def refuse(state: AgentState) -> AgentState:
    """Nothing was retrieved: answer honestly instead of letting the model guess."""
    return {"answer": NOT_FOUND_MESSAGE, "citations": [], "refused": True, "flags": ["no_passages"]}
