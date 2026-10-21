"""Public capability catalog only. No account lookup or credential ingestion."""
from fastapi import APIRouter
from app.services.account_import_contracts import account_provider_capabilities

router = APIRouter()

@router.get("/capabilities")
def capabilities():
    return account_provider_capabilities()
