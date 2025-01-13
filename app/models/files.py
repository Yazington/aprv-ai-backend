from typing import List, Optional

from odmantic import Model
from pydantic import BaseModel


class File(Model):
    name: Optional[str] = None
    type: Optional[str] = None
    size: Optional[int] = None


class FileResponse(Model):
    design: Optional[File] = None
    guidelines: List[File] = []
