from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user
from ..models import Insight, User

router = APIRouter(prefix="/insights", tags=["insights"])


@router.post("/{insight_id}/dismiss")
def dismiss(
    insight_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    ins = db.get(Insight, insight_id)
    if not ins or ins.user_id != user.id:
        raise HTTPException(404)
    ins.dismissed = True
    db.commit()
    return {"ok": True}
