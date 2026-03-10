from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from easy_ecom.api.dependencies import (
    RequestUser,
    ServiceContainer,
    get_container,
    get_current_user,
    require_page_access,
)
from easy_ecom.api.schemas.customers import (
    CustomerCreateRequest,
    CustomerListResponse,
    CustomerMutationResponse,
    CustomerRecord,
    CustomerUpdateRequest,
)

router = APIRouter(prefix="/customers", tags=["customers"])


def _to_record(row: dict[str, str]) -> CustomerRecord:
    return CustomerRecord(
        customer_id=str(row.get("customer_id", "")),
        full_name=str(row.get("full_name", "")),
        phone=str(row.get("phone", "")),
        email=str(row.get("email", "")),
        address_line1=str(row.get("address_line1", "")),
        city=str(row.get("city", "")),
        notes=str(row.get("notes", "")),
        is_active=str(row.get("is_active", "true")).strip().lower() == "true",
        created_at=str(row.get("created_at", "")),
        updated_at=str(row.get("updated_at", row.get("created_at", ""))),
    )


@router.get("", response_model=CustomerListResponse)
def list_customers(
    q: str = Query(default="", max_length=255),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> CustomerListResponse:
    require_page_access(user, "Customers")
    rows = container.customers.list_for_client(client_id=user.client_id, query=q)
    if rows.empty:
        return CustomerListResponse(items=[])
    items = [_to_record(row) for row in rows.to_dict(orient="records")]
    items.sort(key=lambda item: item.full_name.lower())
    return CustomerListResponse(items=items)


@router.post("", response_model=CustomerMutationResponse, status_code=201)
def create_customer(
    payload: CustomerCreateRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> CustomerMutationResponse:
    require_page_access(user, "Customers")
    created = container.customers.create(
        client_id=user.client_id,
        full_name=payload.full_name,
        phone=payload.phone,
        email=payload.email,
        address_line1=payload.address_line1,
        city=payload.city,
        notes=payload.notes,
    )
    return CustomerMutationResponse(customer=_to_record(created))


@router.get("/{customer_id}", response_model=CustomerMutationResponse)
def get_customer(
    customer_id: str,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> CustomerMutationResponse:
    require_page_access(user, "Customers")
    customer = container.customers.get_for_client(client_id=user.client_id, customer_id=customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return CustomerMutationResponse(customer=_to_record(customer))


@router.patch("/{customer_id}", response_model=CustomerMutationResponse)
def update_customer(
    customer_id: str,
    payload: CustomerUpdateRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> CustomerMutationResponse:
    require_page_access(user, "Customers")
    patch = payload.model_dump(exclude_none=True)
    if not patch:
        raise HTTPException(status_code=400, detail="No fields provided")
    updated = container.customers.update_for_client(
        client_id=user.client_id,
        customer_id=customer_id,
        patch=patch,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return CustomerMutationResponse(customer=_to_record(updated))
