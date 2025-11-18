"""
Database Schemas

Luxury fashion storefront models.
Each Pydantic model corresponds to a MongoDB collection (lowercased class name).
"""
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional

class Product(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in USD")
    category: Optional[str] = Field(None, description="Category, e.g., 'bags', 'scarves', 'shoes'")
    images: List[HttpUrl] = Field(default_factory=list, description="Array of image URLs")
    sku: Optional[str] = Field(None, description="Stock keeping unit")
    in_stock: bool = Field(True, description="Whether available for purchase")
    stock_qty: Optional[int] = Field(10, ge=0, description="Available quantity")

class OrderItem(BaseModel):
    product_id: str
    title: str
    unit_amount: int = Field(..., ge=0, description="Unit price in cents")
    quantity: int = Field(..., ge=1)
    image: Optional[HttpUrl] = None

class Order(BaseModel):
    items: List[OrderItem]
    currency: str = Field("usd", description="ISO currency code")
    subtotal: int = Field(..., ge=0, description="Subtotal in cents")
    status: str = Field("pending", description="Order status")
    checkout_session_id: Optional[str] = None
