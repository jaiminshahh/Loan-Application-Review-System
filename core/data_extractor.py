"""
LAYER 1: Data Extractor

Pure Python - reads Excel file and extracts clean, typed values.
No LLM involved - this is deterministic.
"""
import pandas as pd
import re
from datetime import datetime
from dataclasses import dataclass
from typing import Optional


@dataclass
class ExtractedData:
    """Clean, typed data extracted from loan application."""
    
    # Applicant Info
    applicant_name: str = ""
    application_date: str = ""
    loan_amount: float = 0.0
    loan_term_months: int = 0
    loan_purpose: str = ""
    
    # Credit Factors
    credit_score: int = 0
    payment_history_pct: float = 0.0
    credit_utilization_pct: float = 0.0
    hard_inquiries: int = 0
    
    # Income Factors
    employment_status: str = ""
    employment_duration_years: float = 0.0
    annual_income: float = 0.0
    
    # Debt Factors
    monthly_debt_payments: float = 0.0
    monthly_income: float = 0.0
    dti_ratio: float = 0.0
    existing_loan_count: int = 0
    
    # Asset Factors
    liquid_assets: float = 0.0
    liquid_assets_ratio: float = 0.0
    collateral_offered: str = ""
    
    # Banking Factors
    bank_relationship_years: float = 0.0
    nsf_count: int = 0
    monthly_cash_flow: float = 0.0
    
    # Document Factors
    total_docs: int = 0
    verified_docs: int = 0
    docs_verified_pct: float = 0.0
    identity_verified: bool = False


class DataExtractor:
    """Extracts clean data from loan application Excel file."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.sheets = pd.read_excel(file_path, sheet_name=None)
    
    def extract(self) -> ExtractedData:
        """Extract all data and return clean typed object."""
        data = ExtractedData()
        
        # Extract from each sheet
        self._extract_personal_info(data)
        self._extract_credit_report(data)
        self._extract_employment(data)
        self._extract_income(data)
        self._extract_debts(data)
        self._extract_assets(data)
        self._extract_bank_statements(data)
        self._extract_loan_request(data)
        self._extract_documents(data)
        
        # Calculate derived fields
        self._calculate_derived(data)
        
        return data
    
    def _extract_personal_info(self, data: ExtractedData):
        """Extract personal information."""
        df = self.sheets.get("Personal Information", pd.DataFrame())
        info = self._sheet_to_dict(df)
        
        data.applicant_name = info.get("Full Legal Name", "")
    
    def _extract_credit_report(self, data: ExtractedData):
        """Extract credit report data."""
        df = self.sheets.get("Credit Report", pd.DataFrame())
        info = self._sheet_to_dict(df)
        
        # Credit Score - use Experian as primary
        data.credit_score = self._parse_int(info.get("Experian FICO Score", 0))
        
        # Payment History
        pmt_history = info.get("On-Time Payments", "0%")
        data.payment_history_pct = self._parse_percent(pmt_history)
        
        # Credit Utilization
        util = info.get("Overall Utilization", "0%")
        data.credit_utilization_pct = self._parse_percent(util)
        
        # Hard Inquiries
        data.hard_inquiries = self._parse_int(info.get("Hard Inquiries", 0))
    
    def _extract_employment(self, data: ExtractedData):
        """Extract employment history."""
        df = self.sheets.get("Employment History", pd.DataFrame())
        
        if df.empty:
            return
        
        # Get current job (first row after header, where End Date is "Present")
        for _, row in df.iterrows():
            end_date = str(row.get("End Date", "")).strip()
            if end_date.lower() == "present":
                data.employment_status = str(row.get("Employment Type", ""))
                
                # Calculate duration
                start_date = row.get("Start Date", "")
                if pd.notna(start_date):
                    try:
                        if isinstance(start_date, str):
                            start = datetime.strptime(start_date, "%Y-%m-%d")
                        else:
                            start = pd.to_datetime(start_date)
                        years = (datetime.now() - start).days / 365.25
                        data.employment_duration_years = round(years, 1)
                    except:
                        pass
                break
    
    def _extract_income(self, data: ExtractedData):
        """Extract and calculate total income."""
        df = self.sheets.get("Income Sources", pd.DataFrame())
        
        if df.empty:
            return
        
        total_annual = 0.0
        total_monthly = 0.0
        
        for _, row in df.iterrows():
            # Skip unverified income
            verified = str(row.get("Verified", "")).lower()
            if verified not in ["yes", "true", "1"]:
                continue
            
            frequency = str(row.get("Frequency", "")).lower()
            amount_str = str(row.get("Gross Amount", "0"))
            amount = self._parse_money(amount_str)
            
            if "month" in frequency:
                total_monthly += amount
                total_annual += amount * 12
            elif "annual" in frequency or "year" in frequency:
                total_annual += amount
                total_monthly += amount / 12
            elif "quarter" in frequency:
                total_annual += amount * 4
                total_monthly += amount / 3
            elif "bi-week" in frequency or "biweek" in frequency:
                total_annual += amount * 26
                total_monthly += amount * 26 / 12
        
        data.annual_income = round(total_annual, 2)
        data.monthly_income = round(total_monthly, 2)
    
    def _extract_debts(self, data: ExtractedData):
        """Extract existing debts."""
        df = self.sheets.get("Existing Debts", pd.DataFrame())
        
        if df.empty:
            return
        
        total_monthly = 0.0
        active_count = 0
        
        for _, row in df.iterrows():
            status = str(row.get("Payment Status", "")).lower()
            
            # Skip paid off accounts
            if "paid" in status and "off" in status:
                continue
            
            # Count active accounts
            if status in ["current", "active", "open", "open/available"]:
                # Only count if there's a balance
                balance = self._parse_money(str(row.get("Current Balance", "0")))
                if balance > 0:
                    active_count += 1
            
            # Sum monthly payments
            payment_str = str(row.get("Monthly Payment", "0"))
            payment = self._parse_money(payment_str)
            total_monthly += payment
        
        data.monthly_debt_payments = round(total_monthly, 2)
        data.existing_loan_count = active_count
    
    def _extract_assets(self, data: ExtractedData):
        """Extract asset information."""
        df = self.sheets.get("Assets", pd.DataFrame())
        
        if df.empty:
            return
        
        liquid_total = 0.0
        liquid_types = ["checking", "savings", "money market", "brokerage"]
        
        for _, row in df.iterrows():
            asset_type = str(row.get("Asset Type", "")).lower()
            
            if any(lt in asset_type for lt in liquid_types):
                value = self._parse_money(str(row.get("Current Value", "0")))
                liquid_total += value
        
        data.liquid_assets = round(liquid_total, 2)
    
    def _extract_bank_statements(self, data: ExtractedData):
        """Extract bank statement data."""
        df = self.sheets.get("Bank Statements", pd.DataFrame())
        info = self._sheet_to_dict(df)
        
        # Bank relationship duration
        account_date = info.get("Account Open Date", "")
        if account_date:
            try:
                if isinstance(account_date, str):
                    # Try to parse date
                    open_date = datetime.strptime(account_date, "%Y-%m-%d")
                else:
                    open_date = pd.to_datetime(account_date)
                years = (datetime.now() - open_date).days / 365.25
                data.bank_relationship_years = round(years, 1)
            except:
                # Try to find "Years with Bank" field
                years_str = info.get("Years with Bank", "0")
                data.bank_relationship_years = self._parse_float(years_str)
        
        # NSF Count
        nsf_str = info.get("NSF/Overdrafts (12 months)", "0")
        # Extract just the number
        nsf_match = re.search(r'(\d+)', str(nsf_str))
        data.nsf_count = int(nsf_match.group(1)) if nsf_match else 0
        
        # Cash Flow
        deposits = self._parse_money(info.get("Average Monthly Deposits", "0"))
        withdrawals = self._parse_money(info.get("Average Monthly Withdrawals", "0"))
        data.monthly_cash_flow = round(deposits - withdrawals, 2)
    
    def _extract_loan_request(self, data: ExtractedData):
        """Extract loan request details."""
        df = self.sheets.get("Loan Request", pd.DataFrame())
        info = self._sheet_to_dict(df)
        
        data.loan_amount = self._parse_money(info.get("Requested Loan Amount", "0"))
        
        term_str = info.get("Requested Term", "0")
        term_match = re.search(r'(\d+)', str(term_str))
        data.loan_term_months = int(term_match.group(1)) if term_match else 0
        
        data.loan_purpose = info.get("Loan Purpose", "")
        data.collateral_offered = info.get("Collateral Offered", "No")
    
    def _extract_documents(self, data: ExtractedData):
        """Extract document verification status."""
        df = self.sheets.get("Documents Submitted", pd.DataFrame())
        
        if df.empty:
            return
        
        total = 0
        verified = 0
        identity_docs_verified = True
        
        for _, row in df.iterrows():
            total += 1
            status = str(row.get("Verification Status", "")).lower()
            doc_type = str(row.get("Document Type", "")).lower()
            
            if status == "verified":
                verified += 1
            
            # Check identity documents specifically
            if "government id" in doc_type or "passport" in doc_type:
                if status != "verified":
                    identity_docs_verified = False
        
        data.total_docs = total
        data.verified_docs = verified
        data.docs_verified_pct = round((verified / total * 100) if total > 0 else 0, 1)
        data.identity_verified = identity_docs_verified
    
    def _calculate_derived(self, data: ExtractedData):
        """Calculate derived fields."""
        # DTI Ratio
        if data.monthly_income > 0:
            data.dti_ratio = round((data.monthly_debt_payments / data.monthly_income) * 100, 1)
        
        # Liquid Assets Ratio
        if data.loan_amount > 0:
            data.liquid_assets_ratio = round((data.liquid_assets / data.loan_amount) * 100, 1)
    
    def _sheet_to_dict(self, df: pd.DataFrame) -> dict:
        """Convert a 2-column sheet to dictionary."""
        result = {}
        for _, row in df.iterrows():
            if len(row) >= 2:
                key = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
                value = row.iloc[1] if pd.notna(row.iloc[1]) else ""
                if key and not key.isupper():  # Skip section headers
                    result[key] = value
        return result
    
    def _parse_money(self, value: str) -> float:
        """Parse money string to float."""
        if pd.isna(value):
            return 0.0
        value = str(value)
        # Remove $, commas, and other non-numeric chars except . and -
        cleaned = re.sub(r'[^\d.\-]', '', value)
        try:
            return float(cleaned) if cleaned else 0.0
        except ValueError:
            return 0.0
    
    def _parse_percent(self, value: str) -> float:
        """Parse percentage string to float."""
        if pd.isna(value):
            return 0.0
        value = str(value)
        cleaned = re.sub(r'[^\d.]', '', value)
        try:
            return float(cleaned) if cleaned else 0.0
        except ValueError:
            return 0.0
    
    def _parse_int(self, value) -> int:
        """Parse value to integer."""
        if pd.isna(value):
            return 0
        try:
            return int(float(str(value).replace(',', '')))
        except (ValueError, TypeError):
            return 0
    
    def _parse_float(self, value) -> float:
        """Parse value to float."""
        if pd.isna(value):
            return 0.0
        cleaned = re.sub(r'[^\d.]', '', str(value))
        try:
            return float(cleaned) if cleaned else 0.0
        except ValueError:
            return 0.0


def extract_loan_data(file_path: str) -> ExtractedData:
    """Convenience function to extract data from Excel file."""
    extractor = DataExtractor(file_path)
    return extractor.extract()
