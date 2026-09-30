from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_current_user
from app.repositories.rag_repository import clear_rag_history
from app.schemas.ai import RagQueryRequest
from app.ai.event_fetcher import answer_rag_query
from app.workers.tasks import generate_ai_posts_task
from app.repositories.rag_repository import clear_rag_history as clear_rag_history_repo
router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/generate")
def trigger_ai_generation(current_user: dict = Depends(get_current_user)):
    generate_ai_posts_task.delay(current_user["user_id"])
    return {"message": "AI post generation started ✅ Check your email shortly."}


@router.post("/rag")
def rag_query(req: RagQueryRequest, current_user: dict = Depends(get_current_user)):
    result = answer_rag_query(current_user["user_id"], req.query)
    if not result:
        raise HTTPException(status_code=500, detail="RAG query failed")
    return {
        "query": req.query,
        "answer": result.get("answer", ""),
        "sources": result.get("sources", [])
    }


@router.delete("/rag/history")
def clear_rag_history(current_user: dict = Depends(get_current_user)):
    clear_rag_history_repo(current_user["user_id"])

    return {"message": "Chat history cleared ✅"}