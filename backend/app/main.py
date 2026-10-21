from datetime import datetime, timezone
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.database import get_database
from app.models import (
    StartCallRequest,
    StageResultRequest,
    CloseCallRequest,
    CoachRequest,
)
from app.llm_service import get_coaching


app = FastAPI(
    title="Cold-Call Assistant API",
    description="Guided eight-stage cold-call workflow",
    version="1.3.0",
)

# Support the different local Vite ports.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


STAGES = [
    {
        "number": 1,
        "name": "Opening",
        "purpose": "Reach the right person and introduce yourself clearly.",
        "prospect_says": [
            "Hello, who is this?",
            "What is this regarding?",
            "I'm busy right now.",
        ],
    },
    {
        "number": 2,
        "name": "Purpose",
        "purpose": "Explain why you called in one or two clear sentences.",
        "prospect_says": [
            "What does your company do?",
            "How did you get my number?",
            "Is this a sales call?",
        ],
    },
    {
        "number": 3,
        "name": "Permission",
        "purpose": "Find out whether the prospect is willing to talk now.",
        "prospect_says": [
            "I have a minute.",
            "Call me after two.",
            "I'm busy at the moment.",
        ],
    },
    {
        "number": 4,
        "name": "Their business",
        "purpose": "Understand the prospect's company before pitching.",
        "prospect_says": [
            "Let me explain what we do.",
            "Tell me about your company first.",
            "That's not the department I manage.",
        ],
    },
    {
        "number": 5,
        "name": "Their need, in their words",
        "purpose": "Understand the prospect's goals and record their exact words.",
        "prospect_says": [
            "We want to reach new customers.",
            "Our current process takes too much time.",
            "Everything is working fine right now.",
        ],
    },
    {
        "number": 6,
        "name": "Objection",
        "purpose": "Understand the reason for a no and respond respectfully.",
        "prospect_says": [
            "We already have an agency.",
            "We don't have the budget.",
            "Send me something in writing.",
        ],
    },
    {
        "number": 7,
        "name": "Next step",
        "purpose": "Agree on one specific next step, time, or channel.",
        "prospect_says": [
            "Call me next week.",
            "Send the details by email.",
            "Speak to my colleague.",
        ],
    },
    {
        "number": 8,
        "name": "Close",
        "purpose": "Confirm the outcome and end the conversation professionally.",
        "prospect_says": [
            "Thank you, goodbye.",
            "I'm not interested at the moment.",
            "Let's discuss this next week.",
        ],
    },
]


OPEN_STATUSES = {"in_progress", "active", "open", "started"}


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def get_db():
    """Return the configured database client."""
    try:
        return get_database()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Database configuration error: {exc}",
        ) from exc


def get_call_or_404(db, call_id: UUID):
    """Look up a call by its actual primary key in the calls table."""
    normalized_id = str(call_id)

    try:
        result = (
            db.table("calls")
            .select("*")
            .eq("id", normalized_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not look up call {normalized_id}: {exc}",
        ) from exc

    rows = getattr(result, "data", None) or []

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Call {normalized_id} was not found in the calls table. "
                "Use the ID from the latest POST /api/calls response and "
                "verify that the backend uses the correct Supabase project."
            ),
        )

    return rows[0]


def ensure_call_is_open(call):
    status = str(
        call.get("status") or "in_progress"
    ).strip().lower()

    if status not in OPEN_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"This call is not open. Current status: {status}.",
        )


@app.get("/")
def home():
    return {
        "message": "Cold-Call Assistant API",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "cold-call-assistant-api",
    }


@app.get("/api/stages")
def list_stages():
    return {"stages": STAGES}


@app.post("/api/calls", status_code=201)
def start_call(payload: StartCallRequest):
    """Create a new call and return its real database ID."""

    prospect_name = str(
        getattr(payload, "prospect_name", "") or ""
    ).strip()

    company_name = str(
        getattr(payload, "company_name", "")
        or getattr(payload, "company", "")
        or ""
    ).strip()

    caller_name = str(
        getattr(payload, "caller_name", "") or ""
    ).strip()

    if not prospect_name:
        raise HTTPException(
            status_code=422,
            detail="Please enter the prospect's name.",
        )

    # Company and caller name are optional in the frontend.
    call_data = {
        "prospect_name": prospect_name,
        "company_name": company_name or None,
        "caller_name": caller_name or None,
        "status": "in_progress",
        "current_stage": 1,
        "updated_at": utc_now_iso(),
    }

    db = get_db()

    try:
        result = db.table("calls").insert(call_data).execute()
        rows = getattr(result, "data", None) or []

        if not rows:
            raise HTTPException(
                status_code=500,
                detail=(
                    "The call insert returned no record. "
                    "Check the calls table schema and database permissions."
                ),
            )

        created_call = rows[0]
        created_id = created_call.get("id")

        if not created_id:
            raise HTTPException(
                status_code=500,
                detail="The database did not return a call ID.",
            )

        # Return the ID directly so the frontend can use it reliably.
        return {
            "message": "Call started successfully.",
            "call_id": str(created_id),
            "call": created_call,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not start call: {exc}",
        ) from exc


@app.post("/api/calls/{call_id}/stages")
def save_stage(call_id: UUID, payload: StageResultRequest):
    """Save a stage against an existing open call."""

    db = get_db()

    # This verifies the parent call exists before saving a stage.
    call = get_call_or_404(db, call_id)
    ensure_call_is_open(call)

    stage_number = int(payload.stage_number)

    if not 1 <= stage_number <= len(STAGES):
        raise HTTPException(
            status_code=422,
            detail="Stage number must be between 1 and 8.",
        )

    stage_name = str(
        getattr(payload, "stage_name", "") or ""
    ).strip()

    if not stage_name:
        stage_name = STAGES[stage_number - 1]["name"]

    outcome = str(
        getattr(payload, "what_happened", "")
        or getattr(payload, "response", "")
        or ""
    ).strip()

    exact_words = str(
        getattr(payload, "prospect_words", "")
        or getattr(payload, "prospect_exact_words", "")
        or ""
    ).strip()

    notes = str(
        getattr(payload, "notes", "") or ""
    ).strip()

    stage_data = {
        "call_id": str(call_id),
        "stage_number": stage_number,
        "response": outcome,
        "prospect_exact_words": exact_words,
        "notes": notes,
        "outcome": outcome,
        "updated_at": utc_now_iso(),
    }

    try:
        saved = (
            db.table("stage_results")
            .upsert(
                stage_data,
                on_conflict="call_id,stage_number",
            )
            .execute()
        )

        saved_rows = getattr(saved, "data", None) or []

        if not saved_rows:
            raise HTTPException(
                status_code=500,
                detail=(
                    "The stage result was not returned after saving. "
                    "Check the stage_results table and its unique constraint."
                ),
            )

        next_stage = min(stage_number + 1, len(STAGES))

        current_stage = max(
            int(call.get("current_stage") or 1),
            next_stage,
        )

        db.table("calls").update(
            {
                "current_stage": current_stage,
                "updated_at": utc_now_iso(),
            }
        ).eq("id", str(call_id)).execute()

        return {
            "message": "Stage result saved successfully.",
            "call_id": str(call_id),
            "stage_number": stage_number,
            "stage_name": stage_name,
            "stage_result": saved_rows[0],
            "current_stage": current_stage,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not save stage: {exc}",
        ) from exc


@app.put("/api/calls/{call_id}/stages")
def update_stage(call_id: UUID, payload: StageResultRequest):
    """Support clients that use PUT instead of POST."""
    return save_stage(call_id, payload)


@app.post("/api/calls/{call_id}/close")
def close_call(call_id: UUID, payload: CloseCallRequest):
    """Close an open call and record its final outcome."""

    db = get_db()
    call = get_call_or_404(db, call_id)
    ensure_call_is_open(call)

    outcome = str(
        getattr(payload, "outcome", "completed") or "completed"
    ).strip()

    now = utc_now_iso()

    try:
        result = (
            db.table("calls")
            .update(
                {
                    "status": "completed",
                    "outcome": outcome,
                    "closed_at": now,
                    "updated_at": now,
                }
            )
            .eq("id", str(call_id))
            .execute()
        )

        rows = getattr(result, "data", None) or []

        if not rows:
            raise HTTPException(
                status_code=409,
                detail=(
                    "The call was found but could not be closed. "
                    "Refresh the history and check its status."
                ),
            )

        return {
            "message": "Call closed successfully.",
            "call_id": str(call_id),
            "call": rows[0],
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not close call: {exc}",
        ) from exc


@app.get("/api/calls")
def list_calls(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Return call history, including saved stage results."""

    db = get_db()

    try:
        result = (
            db.table("calls")
            .select("*, stage_results(*)")
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

        return {
            "calls": getattr(result, "data", None) or [],
            "limit": limit,
            "offset": offset,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not list calls: {exc}",
        ) from exc


@app.get("/api/calls/{call_id}")
def get_call(call_id: UUID):
    """Return one call and its stage results."""

    db = get_db()
    get_call_or_404(db, call_id)

    try:
        result = (
            db.table("calls")
            .select("*, stage_results(*)")
            .eq("id", str(call_id))
            .limit(1)
            .execute()
        )

        rows = getattr(result, "data", None) or []

        if not rows:
            raise HTTPException(
                status_code=404,
                detail="Call not found.",
            )

        return {"call": rows[0]}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not retrieve call: {exc}",
        ) from exc


@app.post("/api/coach")
def coach(payload: CoachRequest):
    """Generate AI coaching suggestions for a call stage."""

    stage_number = int(
        getattr(payload, "stage_number", 1) or 1
    )

    if not 1 <= stage_number <= len(STAGES):
        raise HTTPException(
            status_code=422,
            detail="Stage number must be between 1 and 8.",
        )

    stage_name = str(
        getattr(payload, "stage_name", "")
        or STAGES[stage_number - 1]["name"]
    )

    prospect_words = str(
        getattr(payload, "prospect_words", "")
        or getattr(payload, "prospect_exact_words", "")
        or ""
    )

    notes = str(
        getattr(payload, "notes", "") or ""
    )

    try:
        advice = get_coaching(
            stage_number=stage_number,
            stage_name=stage_name,
            prospect_words=prospect_words,
            notes=notes,
        )

        return {"coaching": advice}

    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"AI coaching configuration error: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"AI coaching failed: {exc}",
        ) from exc