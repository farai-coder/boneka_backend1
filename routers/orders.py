from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import or_ # Import or_ for correct OR conditions
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, status # Added status
from models import Offer, Order, RequestPost, User
from uuid import UUID
from schemas.orders_schema import OrderAction, OrderOut # Assuming OrderOut is defined
from fastapi.responses import JSONResponse # Import JSONResponse for consistent responses


# Create a new router for orders
orders_router = APIRouter(prefix="/orders", tags=["orders"])

# Get all placed/active orders for a user (customer or supplier)
@orders_router.get("/{user_id}", response_model=List[OrderOut]) # Corrected path, added response_model
def get_all_active_orders_for_user(user_id: UUID, db: Session = Depends(get_db)): # Renamed function for clarity
    # Using or_() for proper SQLAlchemy OR condition
    orders = (
        db.query(Order)
        .filter(
            or_(
                Order.customer_id == user_id,
                Order.supplier_id == user_id
            ),
            Order.status == "placed" # Filter for "placed" orders (active, not completed or cancelled)
        )
        .all()
    )
    return orders

# Mark order as delivered or as cancelled
@orders_router.patch("/{order_id}/status") # Using PATCH for updating status, more RESTful; included order_id in path
def update_order_status(
    order_id: UUID, # Use order_id from path
    action: OrderAction, # action.user_id should be used for validation
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    
    user = db.query(User).filter(User.id == action.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Check user role and allowed action
    if user.role == "customer" and action.action == "cancelled":
        if order.customer_id != user.id: # Ensure the customer owns this order
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to cancel this order.")
        if order.status != "placed": # Only allow cancellation of placed orders
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Order status is '{order.status}', cannot be cancelled.")
        order.status = "cancelled"
        
    elif user.role == "supplier" and action.action == "delivered":
        if order.supplier_id != user.id: # Ensure the supplier owns this order
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to mark this order as delivered.")
        if order.status != "placed": # Only allow marking placed orders as delivered
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Order status is '{order.status}', cannot be marked as delivered.")
        order.status = "delivered" # Corrected spelling from "deliverd"
    else:
        # If the user role is incorrect for the action, or the action itself is invalid
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not allowed to perform this action or action is invalid for current order status.")
    
    db.commit()
    db.refresh(order) # Refresh the order to reflect its updated status
    return JSONResponse(status_code=status.HTTP_200_OK, content={"message": f"Order status updated successfully to '{order.status}'"})

# Get all delivered orders (history) for a customer
@orders_router.get("/history/{user_id}", response_model=List[OrderOut]) # Corrected path to include user_id
def get_all_completed_orders(user_id: UUID, db: Session = Depends(get_db)): # Added user_id parameter for filtering
    orders = (
        db.query(Order)
        .filter(Order.status == "delivered", Order.customer_id == user_id) # Filter by user_id
        .all()
    )
    return orders