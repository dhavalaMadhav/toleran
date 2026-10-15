from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.dependencies import get_db, get_current_user
from app.database.models import CopilotConversation, CopilotMessage, User
from app.schemas.copilot import CopilotChatRequest, CopilotChatResponse
from app.schemas.common import APIResponse
from app.services.copilot_service import copilot_service

router = APIRouter(prefix="/copilot", tags=["copilot"])


@router.post("/chat", response_model=APIResponse[CopilotChatResponse])
def chat_with_copilot(
    data: CopilotChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        response = copilot_service.process_query(
            db=db,
            project_id=data.project_id,
            query=data.message,
            conversation_id=data.conversation_id,
            user_id=current_user.id
        )
        return APIResponse(data=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Copilot query failed: {str(e)}")


@router.get("/conversations/{project_id}", response_model=APIResponse[List[Dict[str, Any]]])
def list_conversations(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    convs = db.query(CopilotConversation).filter(
        CopilotConversation.project_id == project_id
    ).order_by(CopilotConversation.updated_at.desc()).all()

    return APIResponse(data=[
        {
            "id": c.id,
            "title": c.title,
            "created_at": c.created_at,
            "message_count": len(c.messages)
        }
        for c in convs
    ])


@router.get("/messages/{conversation_id}", response_model=APIResponse[List[Dict[str, Any]]])
def get_conversation_history(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    msgs = db.query(CopilotMessage).filter(
        CopilotMessage.conversation_id == conversation_id
    ).order_by(CopilotMessage.created_at.asc()).all()

    return APIResponse(data=[
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "citations": m.citations_json,
            "tools_called": m.tools_called_json,
            "created_at": m.created_at
        }
        for m in msgs
    ])
