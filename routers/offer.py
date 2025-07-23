from typing import List
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from models import Offer, Order, RequestPost, User
from schemas.offer_schema import OfferAction, OfferCreate, OfferRead, OfferAccept
from schemas.user_schema import SuccessMessage
from uuid import UUID

offer_router = APIRouter(prefix="/offers", tags=["offers"])

# 1) Put the static route /accept_request/ BEFORE the dynamic /{request_id}/ route
@offer_router.post("/accept_request/", response_model=SuccessMessage)
def accept_request(offer_in: OfferAccept, db: Session = Depends(get_db)):
    req = db.query(RequestPost).filter_by(id=offer_in.request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found or not open")

    supplier = db.query(User).filter(User.id == offer_in.supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")

    # supplier_categories = {p.category for p in supplier.products}
    # if req.category not in supplier_categories:
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't carry that category or product for this request.")

    existing_offer = db.query(Offer).filter_by(request_id=req.id, supplier_id=supplier.id).first()
    if existing_offer:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An offer from this supplier for this request already exists.")

    offer = Offer(
        request_id=req.id,
        supplier_id=supplier.id,
        proposed=req.offer_price,
        status="accepted"
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return SuccessMessage(message="Offer accepted successfully")

# 1) Put the static route /accept_request/ BEFORE the dynamic /{request_id}/ route
@offer_router.post("/reject_request/", response_model=SuccessMessage)
def reject_request(offer_in: OfferAccept, db: Session = Depends(get_db)):
    req = db.query(RequestPost).filter_by(id=offer_in.request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found or not open")

    supplier = db.query(User).filter(User.id == offer_in.supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")

    # supplier_categories = {p.category for p in supplier.products}
    # if req.category not in supplier_categories:
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't carry that category or product for this request.")

    existing_offer = db.query(Offer).filter_by(request_id=req.id, supplier_id=supplier.id).first()
    if existing_offer:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An offer from this supplier for this request already exists.")

    offer = Offer(
        request_id=req.id,
        supplier_id=supplier.id,
        proposed=req.offer_price,
        status="rejected"
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return SuccessMessage(message="Offer rejected successfully")

# 2) Dynamic route with UUID parameter comes next
@offer_router.post("/{request_id}/", response_model=OfferRead)
def make_offer(request_id: UUID, offer_in: OfferCreate, db: Session = Depends(get_db)):
    req = db.query(RequestPost).filter_by(id=request_id, status="open").first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found or not open")

    supplier = db.query(User).filter(User.id == offer_in.supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")

    supplier_categories = {p.category for p in supplier.products}
    if req.category not in supplier_categories:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't carry that category or product for this request.")

    offer = Offer(
        request_id=req.id,
        supplier_id=supplier.id,
        proposed=offer_in.proposed,
    )

    db.add(offer)
    db.commit()
    db.refresh(offer)
    return offer


# 3) List offers for a request
@offer_router.get("/requests/{request_id}/offers/", response_model=List[OfferRead])
def list_offers(request_id: UUID, db: Session = Depends(get_db)):
    req = db.query(RequestPost).filter_by(id=request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found.")
    return req.offers


# 4) Respond to an offer
@offer_router.patch("/responds/offer/{offer_id}/")
def respond_to_offer(offer_id: UUID, action: OfferAction, db: Session = Depends(get_db)):
    offer = db.query(Offer).filter(Offer.id == offer_id).first()
    if not offer or not offer.request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found.")

    # Uncomment and implement this when auth is ready:
    # if offer.request.customer_id != action.customer_id:
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Offer not associated with your request.")

    if action.action == "accept":
        if offer.status != "pending":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Offer already responded to.")
        offer.status = "accepted"
        offer.request.status = "accepted"
        other_offers = (
            db.query(Offer)
            .filter(Offer.request_id == offer.request.id)
            .filter(Offer.id != offer.id)
            .filter(Offer.status == "pending")
            .all()
        )
        for other_offer in other_offers:
            other_offer.status = "rejected"
        db.commit()
        db.refresh(offer)
        db.refresh(offer.request)
        return {"msg": "Offer accepted"}

    elif action.action == "confirm":
        if offer.status != "accepted":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Offer must be accepted before confirming.")
        order = db.query(Order).filter(Order.offer_id == offer.id).first()
        if not order:
            order = Order(
                request_id=offer.request.id,
                offer_id=offer.id,
                customer_id=offer.request.customer_id,
                supplier_id=offer.supplier_id,
                status="placed",
                total_price=offer.proposed,
                quantity=offer.request.quantity,
            )
            db.add(order)
        if order.status == "confirmed":
            return JSONResponse(status_code=status.HTTP_200_OK, content={"msg": "Order already confirmed."})
        order.status = "confirmed"
        db.commit()
        db.refresh(order)
        return JSONResponse(status_code=status.HTTP_200_OK, content={"msg": "Order confirmed successfully"})

    elif action.action == "reject":
        if offer.status != "pending":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Offer already responded to.")
        offer.status = "rejected"
        db.commit()
        db.refresh(offer)
        return JSONResponse(status_code=status.HTTP_200_OK, content={"msg": "Offer rejected"})

    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid action.")
