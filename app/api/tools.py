from typing import Annotated, List, Dict, Any

from fastapi import APIRouter, Depends

from app.utils.llm_tools import LLMToolsService, get_llm_tools_service

router = APIRouter()

@router.get("/tools", response_model=List[Dict[str, Any]])
async def get_available_tools(
    llm_tools_service: Annotated[LLMToolsService, Depends(get_llm_tools_service)]
) -> List[Dict[str, Any]]:
    """
    Get a list of all available LLM tools with their descriptions and parameters.
    """
    return llm_tools_service.AVAILABLE_TOOLS
