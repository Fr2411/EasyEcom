from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from typing import Optional
import csv
import io

from easy_ecom.api.dependencies import ServiceContainer, get_authenticated_user, get_container, require_page_access
from easy_ecom.api.schemas.common import ModuleOverviewResponse
from easy_ecom.api.schemas.reports import (
    SalesReport,
    InventoryReport,
    ProductsReport,
    FinanceReport,
    ReturnsReport,
    PurchasesReport,
    ReportsOverview,
)
from easy_ecom.domain.models.auth import AuthenticatedUser

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/overview", response_model=ReportsOverview)
def reports_overview(
    from_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    to_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ReportsOverview:
    require_page_access(user, "Reports")
    return container.reports.get_reports_overview(user, from_date, to_date)


@router.get("/sales", response_model=SalesReport)
def sales_report(
    from_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    to_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> SalesReport:
    require_page_access(user, "Reports")
    return container.reports.get_sales_report(user, from_date, to_date)


@router.get("/inventory", response_model=InventoryReport)
def inventory_report(
    from_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    to_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> InventoryReport:
    require_page_access(user, "Reports")
    return container.reports.get_inventory_report(user, from_date, to_date)


@router.get("/purchases", response_model=PurchasesReport)
def purchases_report(
    from_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    to_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> PurchasesReport:
    require_page_access(user, "Reports")
    return container.reports.get_purchases_report(user, from_date, to_date)


@router.get("/finance", response_model=FinanceReport)
def finance_report(
    from_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    to_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> FinanceReport:
    require_page_access(user, "Reports")
    return container.reports.get_finance_report(user, from_date, to_date)


@router.get("/returns", response_model=ReturnsReport)
def returns_report(
    from_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    to_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ReturnsReport:
    require_page_access(user, "Reports")
    return container.reports.get_returns_report(user, from_date, to_date)


@router.get("/products", response_model=ProductsReport)
def products_report(
    from_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    to_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ProductsReport:
    require_page_access(user, "Reports")
    return container.reports.get_products_report(user, from_date, to_date)


@router.get("/export")
def export_reports(
    from_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    to_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
):
    """
    Export reports overview as CSV.
    """
    require_page_access(user, "Reports")
    overview = container.reports.get_reports_overview(user, from_date, to_date)
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        "from_date", "to_date", 
        "sales_revenue_total", "sales_count", 
        "expense_total", "returns_total", "purchases_total"
    ])
    
    # Write data
    writer.writerow([
        overview.from_date, overview.to_date,
        overview.sales_revenue_total, overview.sales_count,
        overview.expense_total, overview.returns_total, overview.purchases_total
    ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=reports_overview.csv"}
    )


# Legacy endpoint for backward compatibility
@router.get("/overview", response_model=ModuleOverviewResponse, include_in_schema=False)
def reports_summary_legacy(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ModuleOverviewResponse:
    require_page_access(user, "Reports")
    return container.overview.reports(user)