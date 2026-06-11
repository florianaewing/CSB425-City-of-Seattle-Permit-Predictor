"""
SDCI Permit History Scraper

Uses searchEcm endpoint to fetch documents/permits indexed by address.
"""

import requests
from typing import Optional, Dict, List, Any
from dataclasses import dataclass

SDCI_BASE = "https://maps.seattle.gov/sdcipermithistory/proxy"

@dataclass
class Document:
    doc_id: str
    title: str
    doc_type: str
    accel_record_type: str
    doc_date: str
    scan_date: str
    profile: str
    subject: str

@dataclass
class SDCIReport:
    success: bool
    address: str
    documents: Optional[List[Document]] = None
    error: Optional[str] = None

class SDCIScraper:
    @staticmethod
    def parse_address(address: str) -> Optional[Dict[str, str]]:
        import re
        addr = address.split(",")[0].strip().upper()
        match = re.match(r"(\d+)\s+(.+?)\s+(AVE|ST|RD|BLVD|LN|WAY|CT|DR|PL|TER|PKWY)\s*(N|S|E|W|NE|NW|SE|SW)?$", addr)
        if not match:
            return None
        return {
            "stNum": match.group(1),
            "stName": match.group(2).strip(),
            "stType": match.group(3),
            "stSfx": (match.group(4) or "").strip()
        }

    @staticmethod
    def search_address(address: str) -> SDCIReport:
        try:
            parsed = SDCIScraper.parse_address(address)
            if not parsed:
                return SDCIReport(success=False, address=address, error="Invalid address format")
            
            resp = requests.get(f"{SDCI_BASE}/searchEcm", params=parsed, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            
            if not isinstance(data, list) or len(data) == 0:
                return SDCIReport(success=False, address=address, error=f"No records found for {address}")
            
            documents = []
            for doc in data:
                if isinstance(doc, dict):
                    documents.append(Document(
                        doc_id=doc.get("id", ""),
                        title=doc.get("documentTitle", ""),
                        doc_type=doc.get("documentType", ""),
                        accel_record_type=doc.get("accelaRecordType", ""),
                        doc_date=doc.get("documentDate", ""),
                        scan_date=doc.get("scanDate", ""),
                        profile=doc.get("documentProfile", ""),
                        subject=doc.get("documentSubject", "")
                    ))
            
            return SDCIReport(success=True, address=address, documents=documents)
        except Exception as e:
            return SDCIReport(success=False, address=address, error=str(e))

    @staticmethod
    def format_report(report: SDCIReport) -> Dict[str, Any]:
        categories = {
            "Permits": [], "Violations": [], "Inspections": [], 
            "Rental Registration": [], "Other": []
        }
        
        if report.documents:
            for doc in report.documents:
                t = (doc.accel_record_type + " " + doc.doc_type + " " + doc.title).lower()
                if "permit" in t:
                    categories["Permits"].append(doc)
                elif "violation" in t or "nov" in t:
                    categories["Violations"].append(doc)
                elif "inspection" in t:
                    categories["Inspections"].append(doc)
                elif "rental" in t:
                    categories["Rental Registration"].append(doc)
                else:
                    categories["Other"].append(doc)
        
        return {
            "success": report.success,
            "address": report.address,
            "documents": [{
                "doc_id": d.doc_id,
                "title": d.title,
                "doc_type": d.doc_type,
                "record_type": d.accel_record_type,
                "doc_date": d.doc_date,
                "scan_date": d.scan_date
            } for d in (report.documents or [])],
            "categories": {k: len(v) for k, v in categories.items()},
            "document_count": len(report.documents) if report.documents else 0,
            "error": report.error
        }
