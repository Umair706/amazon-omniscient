"""Pydantic request/response schemas for Project Omniscient."""

from .common import ErrorResponse, HealthResponse, JobStatusResponse, PaginatedResponse
from .competitor import CompetitorListResponse, CompetitorResponse
from .financial import FinancialProjectionResponse, ProjectionListResponse
from .keyword import KeywordResponse, PPCKeywordResponse
from .niche import (
    NicheCreate,
    NicheListResponse,
    NicheResponse,
    NicheSummary,
    NicheUpdate,
)
from .product import ProductListResponse, ProductResponse, ProductSummary
from .recommendation import (
    RecommendationListResponse,
    RecommendationResponse,
    RecommendationSummary,
)
from .review import ReviewPainPointResponse, ReviewResponse
from .settings import UserSettingsResponse, UserSettingsUpdate
from .supplier import LandedCostResponse, SupplierListResponse, SupplierResponse

__all__ = [
    # Common
    "ErrorResponse",
    "HealthResponse",
    "JobStatusResponse",
    "PaginatedResponse",
    # Niche
    "NicheCreate",
    "NicheUpdate",
    "NicheResponse",
    "NicheListResponse",
    "NicheSummary",
    # Product
    "ProductResponse",
    "ProductListResponse",
    "ProductSummary",
    # Recommendation
    "RecommendationResponse",
    "RecommendationListResponse",
    "RecommendationSummary",
    # Financial
    "FinancialProjectionResponse",
    "ProjectionListResponse",
    # Competitor
    "CompetitorResponse",
    "CompetitorListResponse",
    # Supplier
    "SupplierResponse",
    "SupplierListResponse",
    "LandedCostResponse",
    # Keyword
    "KeywordResponse",
    "PPCKeywordResponse",
    # Review
    "ReviewResponse",
    "ReviewPainPointResponse",
    # Settings
    "UserSettingsUpdate",
    "UserSettingsResponse",
]
