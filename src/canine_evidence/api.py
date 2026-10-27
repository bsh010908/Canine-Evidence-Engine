"""FastAPI boundary; one NCBI connection pool/limiter per application process."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from canine_evidence.clients.ncbi import (
    NCBIClient, NCBIError, NCBINetworkError, NCBIRateLimitError,
    NCBIResponseError, NCBIServerError, NCBITimeoutError,
)
from canine_evidence.config import Settings
from canine_evidence.models.search import ErrorResponse, SearchRequest, SearchResponse
from canine_evidence.search_service import EFetchAllFailed, TRANSIENT_FAILURES, search


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings.from_env()
    async with NCBIClient(settings.email, settings.api_key) as client:
        app.state.ncbi_client = client
        try:
            yield
        finally:
            del app.state.ncbi_client


def get_ncbi_client(request: Request) -> NCBIClient:
    return request.app.state.ncbi_client


def error_response(status: int, error_type: str, detail: str,
                   failures: dict[str, str] | None = None) -> JSONResponse:
    causes = failures or {}
    body = ErrorResponse(detail=detail, error_type=error_type,
                         failed_pmids=list(causes), failures=causes)
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"))


def create_app() -> FastAPI:
    app = FastAPI(title="Canine Evidence Engine", version="0.2.0", lifespan=lifespan)

    @app.exception_handler(NCBIError)
    async def upstream_error(request: Request, exc: NCBIError) -> JSONResponse:
        if isinstance(exc, EFetchAllFailed):
            status = 503 if set(exc.failures.values()) <= TRANSIENT_FAILURES else 502
            return error_response(status, "efetch_all_failed", str(exc), exc.failures)
        mapping = {
            NCBITimeoutError: (503, "timeout"),
            NCBINetworkError: (503, "network_error"),
            NCBIRateLimitError: (503, "rate_limit"),
            NCBIServerError: (502, "server_error"),
            NCBIResponseError: (502, "upstream_response_error"),
        }
        status, kind = mapping.get(type(exc), (502, "upstream_error"))
        return error_response(status, kind, "NCBI 요청을 완료하지 못했습니다.")

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Do not echo arbitrary input or request bodies back into error responses.
        return error_response(422, "validation_error", "검색 입력값의 형식과 범위를 확인해 주세요.")

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception) -> JSONResponse:
        return error_response(500, "internal_error", "검색 처리 중 내부 오류가 발생했습니다.")

    @app.post("/search", response_model=SearchResponse, responses={
        code: {"model": ErrorResponse} for code in (422, 500, 502, 503)
    })
    async def search_endpoint(
        body: SearchRequest, client: Annotated[NCBIClient, Depends(get_ncbi_client)],
    ) -> SearchResponse:
        return await search(body, client)

    return app


app = create_app()
