from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.dependencies import ManagerContext, StaffContext, staff_context

router = APIRouter(prefix="/api/v1/staff", tags=["staff"])


@router.get("/context")
async def context(value: Annotated[StaffContext, Depends(staff_context)]) -> dict[str, str]:
    return {
        "staff_id": str(value.staff_id),
        "business_id": str(value.business_id),
        "business_name": value.business_name,
        "role": value.role,
        "timezone": value.timezone,
    }


@router.get("/management-check")
async def management_check(value: ManagerContext) -> dict[str, str]:
    return {"status": "authorized", "role": value.role}
