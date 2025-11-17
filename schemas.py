"""
Database Schemas for the Clothing Store

Each Pydantic model maps to a MongoDB collection using the lowercased class name.

Conventions:
- class Product -> collection "product"
- class Category -> collection "category"
- class Order -> collection "order"

These schemas are used for validation and for the built-in database helper utilities.
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

AccentColor = Literal["neutral", "black", "white", "slate", "stone", "zinc"]

class Category(BaseModel):
    name: str = Field(..., description="Category display name")
    slug: str = Field(..., description="URL slug, unique")
    gender: Optional[Literal["men", "women", "kids", "unisex", "accessories"]] = None
    banner_image: Optional[str] = Field(None, description="Hero image URL")
    accent: Optional[AccentColor] = "neutral"

class Product(BaseModel):
    title: str
    description: Optional[str] = None
    price: float = Field(..., ge=0)
    category: str = Field(..., description="Category slug, e.g., 'men' or 'women' or 'accessories'")
    subcategory: Optional[str] = Field(None, description="More specific type e.g. 'shirts', 'outerwear'")
    gender: Optional[Literal["men", "women", "kids", "unisex"]] = None
    sizes: List[str] = Field(default_factory=list)
    colors: List[str] = Field(default_factory=list)
    images: List[str] = Field(default_factory=list)
    in_stock: bool = True
    is_new: bool = False
    is_on_sale: bool = False
    sale_percent: Optional[int] = Field(None, ge=0, le=90)
    tags: List[str] = Field(default_factory=list)
    rating: Optional[float] = Field(None, ge=0, le=5)

class Address(BaseModel):
    full_name: str
    line1: str
    line2: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country: str
    phone: Optional[str] = None

class OrderItem(BaseModel):
    product_id: str
    title: str
    price: float
    quantity: int = Field(..., ge=1)
    size: Optional[str] = None
    color: Optional[str] = None
    image: Optional[str] = None

class Order(BaseModel):
    user_id: str
    items: List[OrderItem]
    total: float
    status: Literal["pending","paid","shipped","delivered","cancelled"] = "pending"
    shipping_address: Address

class SavedItem(BaseModel):
    user_id: str
    product_id: str

class CartItem(BaseModel):
    cart_id: str
    product_id: str
    quantity: int = Field(..., ge=1)
    size: Optional[str] = None
    color: Optional[str] = None

class User(BaseModel):
    name: str
    email: str
    is_active: bool = True
    default_address: Optional[Address] = None
