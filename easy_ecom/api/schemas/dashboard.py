from pydantic import BaseModel


class DashboardSummaryResponse(BaseModel):
    Revenue: float
    Gross_Profit: float
    Net_Operating_Profit: float
    Gross_Margin_Pct: float
    Inventory_Value: float
    Outstanding_Receivables: float
    Data_Health_Score: float
