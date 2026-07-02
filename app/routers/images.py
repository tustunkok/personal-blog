from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Image

router = APIRouter(prefix="/admin/images")


@router.post("/upload")
def upload_image(file: UploadFile, db: Session = Depends(get_db)):
    image = Image(
        filename=file.filename or "image",
        content_type=file.content_type or "application/octet-stream",
        data=file.file.read(),
    )
    db.add(image)
    db.commit()
    db.refresh(image)
    return {"id": image.id}


public_router = APIRouter()


@public_router.get("/images/{image_id}")
def serve_image(image_id: int, db: Session = Depends(get_db)):
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        return Response(status_code=404)
    return Response(content=image.data, media_type=image.content_type)
