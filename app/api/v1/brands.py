from fastapi import APIRouter, Depends, HTTPException
from app.repositories.brand_repository import (
    create_brand,
    get_brands,
    get_brand_by_id,
    set_default_brand,
)
from app.api.dependencies import get_current_user
from app.repositories.brand_repository import create_brand
from app.schemas.brands import BrandCreate, BrandResponse


router = APIRouter(
    prefix="/brands",
    tags=["Brands"],
)


@router.post("/", response_model=BrandResponse)
def create_new_brand(
    req: BrandCreate,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]

    brand_name = req.name.strip()

    if not brand_name:
        raise HTTPException(
            status_code=400,
            detail="Brand name is required",
        )

    slug = brand_name.lower().replace(" ", "-")

    try:
        brand = create_brand(
            user_id=user_id,
            name=brand_name,
            slug=slug,
            description=req.description,
            logo_url=req.logo_url,
        )

        return brand

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

@router.get("/")
def get_user_brands(
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]

    return get_brands(user_id)    


@router.get("/{brand_id}")
def get_user_brand(
    brand_id: int,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]

    brand = get_brand_by_id(
        user_id=user_id,
        brand_id=brand_id,
    )

    if not brand:
        raise HTTPException(
            status_code=404,
            detail="Brand not found",
        )

    return brand

@router.patch("/{brand_id}/set-default")
def make_default_brand(
    brand_id: int,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]

    brand = set_default_brand(
        user_id=user_id,
        brand_id=brand_id,
    )

    if not brand:
        raise HTTPException(
            status_code=404,
            detail="Brand not found",
        )

    return brand


@router.get("/{brand_id}/workspace")
def get_brand_workspace(
    brand_id: int,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]

    brand = get_brand_by_id(
        user_id=user_id,
        brand_id=brand_id,
    )

    if not brand:
        raise HTTPException(
            status_code=404,
            detail="Brand not found",
        )

    return {
        "brand": brand,
    }


@router.post("/{brand_id}/switch")
def switch_brand(
    brand_id: int,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]

    brand = get_brand_by_id(
        user_id=user_id,
        brand_id=brand_id,
    )

    if not brand:
        raise HTTPException(
            status_code=404,
            detail="Brand not found",
        )

    return {
        "message": "Brand switched successfully",
        "brand": brand,
    }