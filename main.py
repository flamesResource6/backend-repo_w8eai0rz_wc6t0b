import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document
from schemas import Product as ProductSchema, Category as CategorySchema, CartItem as CartItemSchema, Order as OrderSchema, User as UserSchema

app = FastAPI(title="Clothing Store API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Utility
class ProductResponse(BaseModel):
    id: str
    title: str
    slug: str
    description: Optional[str] = None
    price: float
    compare_at_price: Optional[float] = None
    images: List[str] = []
    category: str
    gender: Optional[str] = None
    tags: List[str] = []
    sizes: List[str] = []
    colors: List[str] = []
    in_stock: bool = True
    is_new: bool = False
    is_sale: bool = False
    rating: Optional[float] = None


def serialize(doc: dict):
    if not doc:
        return None
    d = doc.copy()
    if d.get("_id"):
        d["id"] = str(d.pop("_id"))
    return d


@app.get("/")
def root():
    return {"name": "Clothing Store API", "status": "ok"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "❌ Not Set",
        "database_name": "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                response["collections"] = db.list_collection_names()
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but error: {str(e)[:80]}"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:120]}"
    return response


# Seed minimal data if empty (idempotent)
@app.post("/seed")
@app.post("/api/seed")
def seed():
    if db is None:
        raise HTTPException(500, "Database not configured")

    if db["category"].count_documents({}) == 0:
        categories = [
            {"name": "Men", "slug": "men", "image": "/images/men-hero.jpg"},
            {"name": "Women", "slug": "women", "image": "/images/women-hero.jpg"},
            {"name": "Accessories", "slug": "accessories", "image": "/images/accessories-hero.jpg"},
            {"name": "Kids", "slug": "kids", "image": "/images/kids-hero.jpg"},
            {"name": "Bags", "slug": "bags", "parent": "accessories"},
            {"name": "Caps", "slug": "caps", "parent": "accessories"},
            {"name": "Belts", "slug": "belts", "parent": "accessories"},
            {"name": "Jewelry", "slug": "jewelry", "parent": "accessories"},
            {"name": "Socks", "slug": "socks", "parent": "accessories"}
        ]
        db["category"].insert_many(categories)

    if db["product"].count_documents({}) == 0:
        sample_products = []
        for i in range(1, 40):
            sample_products.append({
                "title": f"Premium Tee {i}",
                "slug": f"premium-tee-{i}",
                "description": "Ultra-soft cotton tee with a relaxed silhouette.",
                "price": 39 + (i % 5) * 10,
                "compare_at_price": 69 if i % 4 == 0 else None,
                "images": [
                    "https://images.unsplash.com/photo-1520975898319-5f35d9d60b86?auto=format&fit=crop&w=1200&q=60",
                    "https://images.unsplash.com/photo-1520974735194-9e8b6e4f1cd7?auto=format&fit=crop&w=1200&q=60",
                ],
                "category": "men" if i % 2 == 0 else "women",
                "gender": "men" if i % 2 == 0 else "women",
                "tags": ["tee", "cotton", "minimal"] + (["trending"] if i % 3 == 0 else []),
                "sizes": ["XS", "S", "M", "L", "XL"],
                "colors": ["black", "white", "grey"],
                "in_stock": True,
                "is_new": i > 30,
                "is_sale": i % 4 == 0,
                "rating": 4.0 + (i % 5) * 0.2
            })
        db["product"].insert_many(sample_products)

    return {"status": "ok"}


# Categories
@app.get("/categories", response_model=List[CategorySchema])
@app.get("/api/categories", response_model=List[CategorySchema])
def list_categories(parent: Optional[str] = None):
    filt = {"parent": parent} if parent is not None else {}
    cats = list(db["category"].find(filt)) if db else []
    return [{k: v for k, v in c.items() if k != "_id"} for c in cats]


# Products listing with filters and sort
@app.get("/products", response_model=List[ProductResponse])
@app.get("/api/products", response_model=List[ProductResponse])
def list_products(
    q: Optional[str] = None,
    category: Optional[str] = None,
    gender: Optional[str] = None,
    tag: Optional[str] = None,
    size: Optional[str] = None,
    color: Optional[str] = None,
    is_new: Optional[bool] = None,
    is_sale: Optional[bool] = None,
    sort: Optional[str] = Query(None, description="newest|price-asc|price-desc"),
    page: int = 1,
    limit: int = 24,
):
    if db is None:
        return []
    filt = {}
    if q:
        filt["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"tags": {"$regex": q, "$options": "i"}},
        ]
    if category:
        filt["category"] = category
    if gender:
        filt["gender"] = gender
    if tag:
        filt["tags"] = tag
    if size:
        filt["sizes"] = size
    if color:
        filt["colors"] = color
    if is_new is not None:
        filt["is_new"] = is_new
    if is_sale is not None:
        filt["is_sale"] = is_sale

    cursor = db["product"].find(filt)
    if sort == "newest":
        cursor = cursor.sort("created_at", -1)
    elif sort == "price-asc":
        cursor = cursor.sort("price", 1)
    elif sort == "price-desc":
        cursor = cursor.sort("price", -1)

    if page < 1:
        page = 1
    skip = (page - 1) * limit
    cursor = cursor.skip(skip).limit(limit)
    return [serialize(p) for p in cursor]


@app.get("/products/new", response_model=List[ProductResponse])
@app.get("/api/new-arrivals", response_model=List[ProductResponse])
def new_arrivals(limit: int = 24):
    if db is None:
        return []
    cursor = db["product"].find({"is_new": True}).sort("created_at", -1).limit(limit)
    return [serialize(p) for p in cursor]


@app.get("/products/sale", response_model=List[ProductResponse])
@app.get("/api/sale", response_model=List[ProductResponse])
def sale_products(limit: int = 48):
    if db is None:
        return []
    cursor = db["product"].find({"is_sale": True}).sort("compare_at_price", -1).limit(limit)
    return [serialize(p) for p in cursor]


@app.get("/product/{slug}", response_model=Optional[ProductResponse])
@app.get("/api/product/{slug}", response_model=Optional[ProductResponse])
def product_by_slug(slug: str):
    if db is None:
        return None
    p = db["product"].find_one({"slug": slug})
    if not p:
        raise HTTPException(404, "Product not found")
    return serialize(p)


@app.get("/product/id/{id}", response_model=Optional[ProductResponse])
@app.get("/api/product/id/{id}", response_model=Optional[ProductResponse])
def product_by_id(id: str):
    if db is None:
        return None
    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    p = db["product"].find_one({"_id": oid})
    if not p:
        raise HTTPException(404, "Product not found")
    return serialize(p)


@app.get("/products/recommended/{id}", response_model=List[ProductResponse])
@app.get("/api/recommended/{id}", response_model=List[ProductResponse])
def recommended(id: str, limit: int = 8):
    if db is None:
        return []
    try:
        oid = ObjectId(id)
    except Exception:
        return []
    prod = db["product"].find_one({"_id": oid})
    if not prod:
        return []
    filt = {"category": prod.get("category")}
    cursor = db["product"].find(filt).limit(limit)
    return [serialize(p) for p in cursor]


# Cart endpoints (session based)
@app.get("/cart/{session_id}")
@app.get("/api/cart/{session_id}")
def get_cart(session_id: str):
    if db is None:
        return {"items": [], "count": 0}
    items = list(db["cartitem"].find({"session_id": session_id}))
    detailed = []
    for it in items:
        prod = db["product"].find_one({"_id": ObjectId(it["product_id"])}) if ObjectId.is_valid(it.get("product_id", "")) else None
        d = serialize(it)
        d["product"] = serialize(prod) if prod else None
        detailed.append(d)
    count = sum(i.get("quantity", 1) for i in items)
    subtotal = sum((i.get("quantity", 1)) * float((db["product"].find_one({"_id": ObjectId(i["product_id"])}) or {}).get("price", 0)) for i in items if ObjectId.is_valid(i.get("product_id", "")))
    return {"items": detailed, "count": count, "subtotal": round(subtotal, 2)}


@app.post("/cart")
@app.post("/api/cart")
def add_to_cart(item: CartItemSchema):
    if db is None:
        raise HTTPException(500, "Database not configured")
    existing = db["cartitem"].find_one({
        "session_id": item.session_id,
        "product_id": item.product_id,
        "size": item.size,
        "color": item.color,
    })
    if existing:
        db["cartitem"].update_one({"_id": existing["_id"]}, {"$inc": {"quantity": item.quantity}})
        return {"status": "updated"}
    else:
        create_document("cartitem", item)
        return {"status": "added"}


class UpdateCartQty(BaseModel):
    id: str
    quantity: int


@app.put("/cart")
@app.put("/api/cart")
def update_cart(body: UpdateCartQty):
    if db is None:
        raise HTTPException(500, "Database not configured")
    try:
        oid = ObjectId(body.id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    if body.quantity <= 0:
        db["cartitem"].delete_one({"_id": oid})
        return {"status": "removed"}
    db["cartitem"].update_one({"_id": oid}, {"$set": {"quantity": body.quantity}})
    return {"status": "updated"}


@app.delete("/cart/{id}")
@app.delete("/api/cart/{id}")
def remove_from_cart(id: str):
    if db is None:
        raise HTTPException(500, "Database not configured")
    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    db["cartitem"].delete_one({"_id": oid})
    return {"status": "removed"}


# Profile basics
@app.get("/profile/{email}")
@app.get("/api/profile/{email}")
def get_profile(email: str):
    if db is None:
        return {"email": email, "orders": [], "addresses": [], "saved_items": []}
    user = db["user"].find_one({"email": email})
    if not user:
        db["user"].insert_one({"email": email, "addresses": [], "saved_items": []})
        user = db["user"].find_one({"email": email})
    orders = list(db["order"].find({"email": email}).sort("created_at", -1))
    u = serialize(user)
    u["orders"] = [serialize(o) for o in orders]
    return u


class SaveItemBody(BaseModel):
    email: str
    product_id: str


@app.post("/profile/save")
@app.post("/api/profile/save")
def save_item(body: SaveItemBody):
    if db is None:
        raise HTTPException(500, "Database not configured")
    db["user"].update_one({"email": body.email}, {"$addToSet": {"saved_items": body.product_id}}, upsert=True)
    return {"status": "saved"}


# Search endpoint
@app.get("/search", response_model=List[ProductResponse])
@app.get("/api/search", response_model=List[ProductResponse])
def search(q: str, page: int = 1, limit: int = 24, sort: Optional[str] = None):
    return list_products(q=q, page=page, limit=limit, sort=sort)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
