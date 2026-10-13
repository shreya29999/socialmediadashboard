from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_current_user
from app.repositories.rag_repository import clear_rag_history
from app.schemas.ai import RagQueryRequest
from app.ai.event_fetcher import answer_rag_query
from app.workers.tasks import generate_ai_posts_task
from app.repositories.rag_repository import (
    clear_rag_history as clear_rag_history_repo,
)

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/generate")
def trigger_ai_generation(
    current_user: dict = Depends(get_current_user),
):
    try:
        task = generate_ai_posts_task.delay(
            current_user["user_id"]
        )

        return {
            "message": "AI post generation started ✅",
            "status": "queued",
            "task_id": task.id,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start AI generation: {str(e)}",
        )


@router.get("/generate/status/{task_id}")
def get_ai_generation_status(
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    from celery.result import AsyncResult

    task = AsyncResult(task_id)

    response = {
        "task_id": task_id,
        "status": task.status,
    }

    if task.status == "SUCCESS":
        response["result"] = task.result

    elif task.status == "FAILURE":
        response["error"] = str(task.result)

    elif task.status == "PROGRESS":
        response["progress"] = task.info

    return response


@router.post("/rag")
def rag_query(
    req: RagQueryRequest,
    current_user: dict = Depends(get_current_user),
):
    result = answer_rag_query(
        current_user["user_id"],
        req.query,
    )

    if not result:
        raise HTTPException(
            status_code=500,
            detail="RAG query failed",
        )

    return {
        "query": req.query,
        "answer": result.get("answer", ""),
        "sources": result.get("sources", []),
    }


@router.delete("/rag/history")
def clear_rag_history(
    current_user: dict = Depends(get_current_user),
):
    clear_rag_history_repo(
        current_user["user_id"]
    )

    return {
        "message": "Chat history cleared ✅"
    }