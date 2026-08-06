from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.api.dependencies.auth import get_current_user
from app.models.core import User
from app.services.global_access import GlobalAccessService
from app.services.media_variables import list_variables, sample_data, validate_tokens

router = APIRouter(tags=["Media Variables"])

class ValidateIn(BaseModel):
    schema: str = "common"
    tokens: list[str] = Field(default_factory=list)

def require_superadmin(user: User) -> None:
    GlobalAccessService.require_superadmin(user)

@router.get("/platform/media/variables")
async def variables(schema: str = "common", current_user: User = Depends(get_current_user)):
    require_superadmin(current_user)
    return {"schema": schema, "items": list_variables(schema), "sample": sample_data(schema), "schemas": ["common", "voting", "ranks"]}

@router.post("/platform/media/variables/validate")
async def validate(payload: ValidateIn, current_user: User = Depends(get_current_user)):
    require_superadmin(current_user)
    return validate_tokens(payload.schema, payload.tokens)
