from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


Status = Literal["Applied", "Pending", "Won", "Lost"]
EntryType = Literal["Government Tender", "Quotation"]
Cadence = Literal["weekly", "biweekly", "none"]
AssetKind = Literal["logo", "signature"]


class RegistryEntryBase(BaseModel):
    title: str
    ref_number: str
    department: str
    type: EntryType = "Government Tender"
    status: Status = "Pending"
    date_applied: Optional[date] = None
    deadline: Optional[date] = None
    amount: Optional[float] = None
    currency: str = "INR"
    contact_person: str = ""
    notes: str = ""
    follow_up_cadence: Cadence = "none"
    last_follow_up: Optional[date] = None


class RegistryEntryCreate(RegistryEntryBase):
    pass


class RegistryEntryUpdate(RegistryEntryBase):
    pass


class RegistryEntryOut(RegistryEntryBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime


class QuotationLetterhead(BaseModel):
    company_name: str = ""
    tagline: str = ""
    address: str = ""
    gstin: str = ""
    mobile: str = ""
    logo_asset_id: Optional[str] = None


class QuotationMeta(BaseModel):
    ref_number: str = ""
    date: str = ""
    currency: str = "INR"
    party_name: str = ""
    party_address: str = ""
    attention: str = ""
    subject: str = "Quotation"
    intro: str = ""


class QuotationLineItem(BaseModel):
    description: str = ""
    qty: str = "1"
    rate: str = "0"
    amount: str = "0"
    auto: bool = True


class QuotationTerms(BaseModel):
    payment_terms: str = ""
    delivery: str = ""
    warranty: str = ""
    validity_days: int = 30
    tax_note: str = ""


class QuotationSignature(BaseModel):
    name: str = ""
    designation: str = ""
    phone: str = ""
    signature_asset_id: Optional[str] = None


class QuotationDraft(BaseModel):
    id: str = "draft"
    letterhead: QuotationLetterhead = Field(default_factory=QuotationLetterhead)
    meta: QuotationMeta = Field(default_factory=QuotationMeta)
    line_items: list[QuotationLineItem] = Field(default_factory=list)
    terms: QuotationTerms = Field(default_factory=QuotationTerms)
    signature: QuotationSignature = Field(default_factory=QuotationSignature)


class AssetOut(BaseModel):
    id: str = Field(alias="_id")
    kind: AssetKind
    content_type: str
    data_url: str


class StatsOut(BaseModel):
    total: int
    awaiting_result: int
    due_for_follow_up: int
    won: int
    win_rate: float
    total_quoted_value: float
