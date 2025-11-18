import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Product, Order, OrderItem

app = FastAPI(title="Luxury Fashion Store API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----- Utilities -----

def to_str_id(doc: dict) -> dict:
    if not doc:
        return doc
    d = dict(doc)
    if d.get("_id") is not None:
        d["id"] = str(d.pop("_id"))
    return d


def ensure_object_id(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")


# ----- Health -----
@app.get("/")
def read_root():
    return {"message": "Luxury Fashion Store API running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                response["collections"] = db.list_collection_names()[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    import os as _os
    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


# ----- Products -----
@app.get("/api/products")
def list_products():
    docs = get_documents("product")
    return [to_str_id(d) for d in docs]


@app.post("/api/products")
def create_product(product: Product):
    # Normalize title and price
    data = product.model_dump()
    inserted_id = create_document("product", data)
    doc = db["product"].find_one({"_id": ObjectId(inserted_id)})
    return to_str_id(doc)


@app.get("/api/products/{product_id}")
def get_product(product_id: str):
    _id = ensure_object_id(product_id)
    doc = db["product"].find_one({"_id": _id})
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")
    return to_str_id(doc)


# ----- Checkout / Orders -----
class CartItem(BaseModel):
    product_id: str
    quantity: int


class CheckoutRequest(BaseModel):
    items: List[CartItem]


@app.post("/api/checkout")
def create_checkout(req: CheckoutRequest):
    if not req.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # Build order items from database to ensure trusted pricing
    order_items: List[OrderItem] = []
    subtotal_cents = 0

    # Track stock updates
    stock_updates = []

    for item in req.items:
        pid = ensure_object_id(item.product_id)
        prod = db["product"].find_one({"_id": pid})
        if not prod:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        if not prod.get("in_stock", True) or (prod.get("stock_qty", 0) < item.quantity):
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {prod.get('title','item')}")

        unit_amount = int(round(float(prod.get("price", 0)) * 100))
        subtotal_cents += unit_amount * item.quantity

        first_image = None
        imgs = prod.get("images") or []
        if isinstance(imgs, list) and imgs:
            first_image = imgs[0]

        order_items.append(OrderItem(
            product_id=str(prod["_id"]),
            title=prod.get("title", "Product"),
            unit_amount=unit_amount,
            quantity=item.quantity,
            image=first_image
        ))

        stock_updates.append((pid, item.quantity))

    order = Order(items=order_items, subtotal=subtotal_cents)

    # Create order
    order_id = create_document("order", order)

    # Update stock quantities after order creation
    for pid, qty in stock_updates:
        db["product"].update_one({"_id": pid}, {"$inc": {"stock_qty": -qty}})
        # If stock becomes zero, mark out of stock
        pdoc = db["product"].find_one({"_id": pid})
        if pdoc and pdoc.get("stock_qty", 0) <= 0:
            db["product"].update_one({"_id": pid}, {"$set": {"in_stock": False}})

    return {
        "order_id": order_id,
        "status": "confirmed",
        "subtotal": order.subtotal,
        "currency": order.currency,
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
