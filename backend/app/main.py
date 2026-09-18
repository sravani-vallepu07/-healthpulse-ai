import uuid
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
import app.models # Register all models

from app.routers import (
    auth_routes,
    hospital_routes,
    doctor_routes,
    availability_routes,
    appointment_routes,
    questionnaire_routes,
    ai_routes,
    integration_routes,
    workflow_routes,
    audit_routes,
    ops_routes,
    telephony_routes
)

# Initialize database schema
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Autonomous Multi-Hospital Patient Intake, Scheduling & Pre-Visit Voice Agent API",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Correlation ID Middleware
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    corr_id = request.headers.get("X-Correlation-ID") or f"CORR-{uuid.uuid4().hex[:8].upper()}"
    request.state.correlation_id = corr_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = corr_id
    return response

# Standardized Error Handler
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    corr_id = getattr(request.state, "correlation_id", "CORR-UNKNOWN")
    detail = exc.detail
    if isinstance(detail, dict):
        error_code = detail.get("error_code", "ERROR")
        message = detail.get("message", "An error occurred")
        cid = detail.get("correlation_id", corr_id)
    else:
        error_code = "HTTP_ERROR"
        message = str(detail)
        cid = corr_id

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error_code": error_code,
            "message": message,
            "correlation_id": cid
        }
    )

import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Include Routers
app.include_router(auth_routes.router, prefix=settings.API_V1_STR)
app.include_router(hospital_routes.router, prefix=settings.API_V1_STR)
app.include_router(doctor_routes.router, prefix=settings.API_V1_STR)
app.include_router(availability_routes.router, prefix=settings.API_V1_STR)
app.include_router(appointment_routes.router, prefix=settings.API_V1_STR)
app.include_router(questionnaire_routes.router, prefix=settings.API_V1_STR)
app.include_router(ai_routes.router, prefix=settings.API_V1_STR)
app.include_router(integration_routes.router, prefix=settings.API_V1_STR)
app.include_router(workflow_routes.router, prefix=settings.API_V1_STR)
app.include_router(audit_routes.router, prefix=settings.API_V1_STR)
app.include_router(ops_routes.router, prefix=settings.API_V1_STR)
app.include_router(telephony_routes.router, prefix=settings.API_V1_STR)

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "database": "connected"
    }

# Mount frontend directory for SPA
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend"))
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/")
    def serve_frontend_index():
        index_file = os.path.join(frontend_dir, "index.html")
        return FileResponse(index_file)

    @app.get("/app.jsx")
    def serve_frontend_jsx():
        jsx_file = os.path.join(frontend_dir, "app.jsx")
        return FileResponse(jsx_file, media_type="application/javascript")

