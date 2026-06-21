"""ER schema CRUD endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from auth import get_current_user, require_teacher
from database import get_db
from dto import ERSchemaOut
from models import ERSchema, User
from s3_utils import read_uploaded_image, upload_image_to_s3
from serializers import serialize_er_schema

router = APIRouter()


@router.post("/api/schemas", response_model=ERSchemaOut, status_code=status.HTTP_201_CREATED)
async def create_schema(
    name: str = Form(...),
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new ER schema (teacher only)."""
    require_teacher(current_user)

    image_bytes, image_content_type = await read_uploaded_image(image)
    image_s3_key, image_url = upload_image_to_s3(image_bytes, image_content_type)

    schema = ERSchema(
        name=name,
        image_url=image_url,
        image_s3_key=image_s3_key,
        teacher_id=current_user.id,
    )
    db.add(schema)
    await db.commit()
    await db.refresh(schema)

    return serialize_er_schema(schema)


@router.get("/api/schemas", response_model=List[ERSchemaOut])
async def list_schemas(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all ER schemas visible to the current user."""
    result = await db.execute(select(ERSchema).order_by(ERSchema.id.desc()))
    return [serialize_er_schema(schema) for schema in result.scalars().all()]


@router.get("/api/schemas/{schema_id}", response_model=ERSchemaOut)
async def get_schema(
    schema_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific ER schema."""
    result = await db.execute(select(ERSchema).where(ERSchema.id == schema_id))
    schema = result.scalars().first()

    if schema is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schema not found")

    return serialize_er_schema(schema)


@router.put("/api/schemas/{schema_id}", response_model=ERSchemaOut)
async def update_schema(
    schema_id: int,
    name: str = Form(...),
    image: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an ER schema (teacher only)."""
    require_teacher(current_user)

    result = await db.execute(select(ERSchema).where(ERSchema.id == schema_id))
    schema = result.scalars().first()

    if schema is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schema not found")
    if schema.teacher_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner teacher can edit this schema")

    schema.name = name

    if image is not None and image.filename:
        image_bytes, image_content_type = await read_uploaded_image(image)
        image_s3_key, image_url = upload_image_to_s3(image_bytes, image_content_type)
        schema.image_s3_key = image_s3_key
        schema.image_url = image_url

    await db.commit()
    await db.refresh(schema)

    return serialize_er_schema(schema)


@router.delete("/api/schemas/{schema_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schema(
    schema_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an ER schema (teacher only)."""
    require_teacher(current_user)

    result = await db.execute(select(ERSchema).where(ERSchema.id == schema_id))
    schema = result.scalars().first()

    if schema is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schema not found")
    if schema.teacher_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner teacher can delete this schema")

    await db.delete(schema)
    await db.commit()
