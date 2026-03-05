"""FastAPI application entry point for Jetson Nano Remote Web App."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import connection_router, terminal_router
from routers.fingerprint import router as fingerprint_router
from services.terminal_service import terminal_service
from services.fingerprint_service import fingerprint_service


# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting Jetson Nano Remote Web App")
    yield
    # Cleanup on shutdown
    logger.info("Shutting down...")
    await terminal_service.close_all()
    await fingerprint_service.disconnect()


app = FastAPI(
    title="Jetson Nano Remote",
    description="Web application for remote control of Jetson Nano via USB/SSH",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(connection_router, prefix=settings.api_prefix)
app.include_router(fingerprint_router, prefix=settings.api_prefix)
app.include_router(terminal_router)


@app.get("/")
async def root():
    """Root endpoint returning API information."""
    return {
        "name": "Jetson Nano Remote API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "usb_check": f"{settings.api_prefix}/connection/usb/check",
            "ping": f"{settings.api_prefix}/connection/ping",
            "ssh_test": f"{settings.api_prefix}/connection/ssh/test",
            "terminal": "/ws/terminal",
            "fingerprint_status": f"{settings.api_prefix}/fingerprint/status",
            "fingerprint_diagnostic": f"{settings.api_prefix}/fingerprint/diagnostic",
            "fingerprint_stream": f"{settings.api_prefix}/fingerprint/ws/stream",
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
