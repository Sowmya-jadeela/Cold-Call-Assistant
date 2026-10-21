from pydantic import BaseModel, Field, root_validator


class BaseRequest(BaseModel):
    """Shared configuration for API request models."""

    class Config:
        extra = "ignore"


class StartCallRequest(BaseRequest):
    """Request model for starting a new call."""

    prospect_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
    )
    company: str = ""
    company_name: str = ""
    caller_name: str = ""

    @root_validator(pre=True)
    def normalize_company_fields(cls, values):
        values = dict(values or {})

        company = (
            values.get("company_name")
            or values.get("company")
            or ""
        )

        values["company"] = company
        values["company_name"] = company

        return values


class StageResultRequest(BaseRequest):
    """Request model for saving a call stage."""

    stage_number: int = Field(..., ge=1, le=8)
    stage_name: str = ""
    what_happened: str = ""
    response: str = ""
    prospect_words: str = ""
    prospect_exact_words: str = ""
    notes: str = ""

    @root_validator(pre=True)
    def normalize_stage_fields(cls, values):
        values = dict(values or {})

        # Accept either name for the outcome.
        outcome = (
            values.get("what_happened")
            or values.get("response")
            or ""
        )

        values["what_happened"] = outcome
        values["response"] = outcome

        # Accept either name for the prospect's exact words.
        words = (
            values.get("prospect_words")
            or values.get("prospect_exact_words")
            or ""
        )

        values["prospect_words"] = words
        values["prospect_exact_words"] = words

        # Supply a stage name when one is not provided.
        stage_names = {
            1: "Opening",
            2: "Permission",
            3: "Reason for calling",
            4: "Problem",
            5: "Value proposition",
            6: "Objection handling",
            7: "Next step",
            8: "Close",
        }

        stage_number = values.get("stage_number")

        if not values.get("stage_name") and stage_number is not None:
            try:
                values["stage_name"] = stage_names.get(
                    int(stage_number),
                    "Unknown stage",
                )
            except (TypeError, ValueError):
                values["stage_name"] = "Unknown stage"

        return values


class CloseCallRequest(BaseRequest):
    """Request model for closing a call."""

    outcome: str = "completed"
    summary: str = ""


class CoachRequest(BaseRequest):
    """Request model for requesting AI coaching."""

    call_id: str = ""
    stage_number: int = Field(default=1, ge=1, le=8)
    stage_name: str = ""
    what_happened: str = ""
    response: str = ""
    prospect_words: str = ""
    prospect_exact_words: str = ""
    notes: str = ""
    prospect_name: str = ""
    company: str = ""
    company_name: str = ""

    @root_validator(pre=True)
    def normalize_coach_fields(cls, values):
        values = dict(values or {})

        # Normalize the outcome.
        outcome = (
            values.get("what_happened")
            or values.get("response")
            or ""
        )

        values["what_happened"] = outcome
        values["response"] = outcome

        # Normalize the prospect's exact words.
        words = (
            values.get("prospect_words")
            or values.get("prospect_exact_words")
            or ""
        )

        values["prospect_words"] = words
        values["prospect_exact_words"] = words

        # Support both company field names.
        company = (
            values.get("company_name")
            or values.get("company")
            or ""
        )

        values["company"] = company
        values["company_name"] = company

        return values