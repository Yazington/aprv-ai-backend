from typing import List, Optional

from pydantic import BaseModel


class File(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    size: Optional[int] = None


class FileResponse(BaseModel):
    design: Optional[File] = None
    guidelines: List[File] = []
