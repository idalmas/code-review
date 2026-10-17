from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import get_github_service, get_llm_service
from app.api.errors import register_error_handlers
from app.api.routes import auth, links, llm, pulls, renders, stress
from app.config import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await get_github_service().aclose()
    await get_llm_service().aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Orbiter API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_credentials=True,
        allow_headers=["*"],
    )
    register_error_handlers(app)

    @app.get("/api/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth.router, prefix="/api")
    app.include_router(links.router, prefix="/api")
    app.include_router(llm.router, prefix="/api")
    app.include_router(renders.router, prefix="/api")
    app.include_router(stress.router, prefix="/api")
    app.include_router(pulls.router, prefix="/api")
    return app


app = create_app()
