from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.disruption_parser import parse_disruption
from backend.entity_resolver import resolve_disruption
from backend.impact_engine import assess_impact
from backend.response_engine import generate_response_options
from backend.recommendation_engine import recommend_response


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="RippleX",
    description="AI Supply Chain Disruption Command Center",
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# REQUEST MODEL
# ============================================================

class AnalyzeRequest(BaseModel):
    notice: str = Field(
        ...,
        min_length=1,
        description="Unstructured supply-chain disruption notice",
    )


# ============================================================
# FRONTEND
# ============================================================

@app.get("/")
def home():
    return FileResponse(
        FRONTEND_DIR / "index.html"
    )


@app.get("/static/{filename}")
def static_files(filename: str):
    allowed_files = {
        "style.css": FRONTEND_DIR / "style.css",
        "app.js": FRONTEND_DIR / "app.js",
    }

    file_path = allowed_files.get(filename)

    if file_path is None or not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Frontend file not found",
        )

    return FileResponse(file_path)


# ============================================================
# HEALTH
# ============================================================

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "RippleX",
    }


# ============================================================
# ANALYZE
# ============================================================

@app.post("/api/analyze")
def analyze(request: AnalyzeRequest):

    try:

        # ----------------------------------------------------
        # 1. Gemini extracts facts from the notice.
        # ----------------------------------------------------

        event = parse_disruption(
            request.notice
        )

        # ----------------------------------------------------
        # 2. Resolve entities against database.
        # ----------------------------------------------------

        resolved = resolve_disruption(
            event
        )

        # ----------------------------------------------------
        # 3. Deterministic impact calculation.
        # ----------------------------------------------------

        impact = assess_impact(
            resolved
        )

        # ----------------------------------------------------
        # 4. No confirmed impact / human review.
        # ----------------------------------------------------

        if not impact.has_impact:

            return {
                "success": True,

                "notice": request.notice,

                "event": event.model_dump(),

                "resolution": resolved.to_dict(),

                "impact": impact.to_dict(),

                "response_options": [],

                "recommendation": None,
            }

        # ----------------------------------------------------
        # 5. Generate response options.
        # ----------------------------------------------------

        response_options = generate_response_options(
            impact
        )

        # ----------------------------------------------------
        # 6. Select recommendation.
        # ----------------------------------------------------

        recommendation = recommend_response(
            impact,
            response_options,
        )

        # ----------------------------------------------------
        # 7. Return complete result.
        # ----------------------------------------------------

        return {
            "success": True,

            "notice": request.notice,

            "event": event.model_dump(),

            "resolution": resolved.to_dict(),

            "impact": impact.to_dict(),

            "response_options": [
                option.to_dict()
                for option in response_options
            ],

            "recommendation": recommendation.to_dict(),
        }

    except Exception as exc:
        import traceback

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail={
                "error": "Analysis failed",
                "message": str(exc),
            },
        ) from exc


# ============================================================
# LOCAL / CLOUD SERVER
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
    )