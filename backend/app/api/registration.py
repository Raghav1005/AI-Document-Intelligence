from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.registrations.service import RegistrationService, get_registration_service
from app.schemas.registration import (
    RegistrationPendingResponse,
    RegistrationRequest,
    RegistrationVerifiedResponse,
    ResendOtpRequest,
    ResendOtpResponse,
    VerifyOtpRequest,
)

router = APIRouter(prefix="/api/v1/auth", tags=["registration"])
ServiceDep = Annotated[RegistrationService, Depends(get_registration_service)]


def client_ip(request: Request) -> str:
    # Trust the direct socket peer; forwarded headers are deliberately not accepted.
    return request.client.host if request.client else "unknown"


@router.post(
    "/register",
    response_model=RegistrationPendingResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def register(
    payload: RegistrationRequest,
    request: Request,
    service: ServiceDep,
) -> dict[str, object]:
    return await service.register(payload, client_ip(request))


@router.post(
    "/verify-otp",
    response_model=RegistrationVerifiedResponse,
    status_code=status.HTTP_200_OK,
)
async def verify_otp(
    payload: VerifyOtpRequest,
    request: Request,
    service: ServiceDep,
) -> dict[str, str]:
    return await service.verify(payload.registration_id, payload.otp, client_ip(request))


@router.post(
    "/resend-otp",
    response_model=ResendOtpResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def resend_otp(
    payload: ResendOtpRequest,
    request: Request,
    response: Response,
    service: ServiceDep,
) -> dict[str, int]:
    result = await service.resend(payload.registration_id, client_ip(request))
    response.headers["Retry-After"] = str(result["resend_in_seconds"])
    return result
