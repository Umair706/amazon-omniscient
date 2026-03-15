"""SQLAlchemy ORM models for the Omniscient project.

Import all models here so that Alembic's ``target_metadata = Base.metadata``
picks up every table when generating migrations.
"""

from .base import Base, TimestampMixin
from .bsr_history import BSRHistory
from .competitor import Competitor
from .financial_projection import FinancialProjection
from .keyword import NicheKeyword, PPCKeyword
from .niche import Niche
from .price_history import PriceHistory
from .product import Product
from .recommendation import Recommendation
from .review import Review, ReviewPainPoint
from .supplier import LandedCostCalculation, Supplier
from .user_settings import UserSettings

__all__ = [
    "Base",
    "TimestampMixin",
    "BSRHistory",
    "Competitor",
    "FinancialProjection",
    "LandedCostCalculation",
    "Niche",
    "NicheKeyword",
    "PPCKeyword",
    "PriceHistory",
    "Product",
    "Recommendation",
    "Review",
    "ReviewPainPoint",
    "Supplier",
    "UserSettings",
]
