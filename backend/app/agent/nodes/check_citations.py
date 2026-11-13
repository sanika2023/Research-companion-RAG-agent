import re

from app.agent import prompts
from app.agent.state import AgentState, Citation

NOT_FOUND_MESSAGE = "I couldn't find the answer to this question in the selected paper."

# "[2]" or "[1, 3]", with any whitespace before it (so a removed marker leaves no gap).
_MARKER = re.compile(r"(\s*)\[(\d+(?:\s*,\s*\d+)*)\]")


def check_citations(state: AgentState) -> AgentState:
    """Keep only citations to passages the model was actually shown; map them to pages."""
    draft = state["draft"].strip()
    if draft == prompts.NOT_FOUND:
        return {"answer": NOT_FOUND_MESSAGE, "citations": [], "refused": True, "flags": []}

    passages = state["passages"]
    cited: list[int] = []  # valid numbers, in order of first use
    removed = False

    def keep_valid(match: re.Match[str]) -> str:
        nonlocal removed
        numbers = [int(n) for n in match.group(2).split(",")]
        valid = [n for n in numbers if 1 <= n <= len(passages)]
        removed = removed or len(valid) < len(numbers)
        cited.extend(n for n in valid if n not in cited)
        return f"{match.group(1)}[{', '.join(map(str, valid))}]" if valid else ""

    answer = _MARKER.sub(keep_valid, draft)
    citations = [_citation(n, state) for n in cited]
    flags = (["invalid_citations_removed"] if removed else []) + ([] if cited else ["uncited"])
    return {"answer": answer, "citations": citations, "refused": False, "flags": flags}


def _citation(number: int, state: AgentState) -> Citation:
    passage = state["passages"][number - 1]
    return Citation(
        number=number,
        chunk_id=passage.chunk_id,
        page=passage.page,
        text=passage.text,
        bbox=passage.bbox,
    )
