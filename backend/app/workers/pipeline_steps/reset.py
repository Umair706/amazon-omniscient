"""Pipeline step: delete derived rows so a forced re-analysis does not duplicate them."""

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competitor import Competitor
from app.models.financial_projection import FinancialProjection
from app.models.keyword import PPCKeyword
from app.models.recommendation import Recommendation
from app.models.supplier import LandedCostCalculation, Supplier

# Order matters: landed_cost_calculations references suppliers.
RESET_TABLES = (LandedCostCalculation, Supplier, Competitor, FinancialProjection, Recommendation, PPCKeyword)


async def reset_niche_analysis_data(db: AsyncSession, niche_id: int) -> None:
    """Remove everything a previous run derived for this niche. Products and reviews are kept."""
    for model in RESET_TABLES:
        await db.execute(delete(model).where(model.niche_id == niche_id))
    await db.flush()
