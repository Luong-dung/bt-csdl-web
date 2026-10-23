"""Public request IDs must fit PostgreSQL INTEGER on every database backend."""

from typing import Annotated

from fastapi import Path
from pydantic import Field

INT_MAX = 2147483647
DbId = Annotated[int, Field(gt=0, le=INT_MAX)]
ResourceId = Annotated[int, Path(gt=0, le=INT_MAX)]
