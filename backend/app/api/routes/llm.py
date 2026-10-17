from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_llm_service
from app.services.llm import LLMService, LLMStatus

router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("")
def llm_status(llm: Annotated[LLMService, Depends(get_llm_service)]) -> LLMStatus:
    """Whether AI features are on and which model each tier uses."""
    return llm.status()
