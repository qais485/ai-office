from enum import Enum
from typing import Dict, Any


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


RISK_CONFIG: Dict[RiskLevel, Dict[str, Any]] = {
    RiskLevel.LOW: {
        "auto_approve": True,
        "requires_ceo": False,
        "description": "Low risk actions that can be auto-approved",
        "examples": ["Read email", "Search customers", "View analytics"]
    },
    RiskLevel.MEDIUM: {
        "auto_approve": True,
        "requires_ceo": False,
        "description": "Medium risk actions that can be auto-approved but are logged",
        "examples": ["Send normal response", "Create ticket", "Update lead"]
    },
    RiskLevel.HIGH: {
        "auto_approve": False,
        "requires_ceo": True,
        "description": "High risk actions that require CEO approval",
        "examples": ["Refund customer", "Send proposal", "Issue refund > $100"]
    },
    RiskLevel.CRITICAL: {
        "auto_approve": False,
        "requires_ceo": True,
        "requires_2fa": True,
        "description": "Critical actions that require CEO approval and may need 2FA",
        "examples": ["Financial transfer", "Legal action", "Delete customer data"]
    }
}


def get_risk_config(level: RiskLevel) -> Dict[str, Any]:
    return RISK_CONFIG.get(level, RISK_CONFIG[RiskLevel.LOW])


def should_auto_approve(level: RiskLevel) -> bool:
    return RISK_CONFIG[level]["auto_approve"]


def requires_ceo_approval(level: RiskLevel) -> bool:
    return RISK_CONFIG[level]["requires_ceo"]


def get_risk_level_for_action(action: str, parameters: Dict[str, Any] = None) -> RiskLevel:
    action_risk_map = {
        "read_email": RiskLevel.LOW,
        "read_emails": RiskLevel.LOW,
        "search_customers": RiskLevel.LOW,
        "view_analytics": RiskLevel.LOW,
        "read_knowledge": RiskLevel.LOW,
        "read_calendar": RiskLevel.LOW,
        "read_tickets": RiskLevel.LOW,
        "read_leads": RiskLevel.LOW,
        
        "write_email": RiskLevel.MEDIUM,
        "send_email": RiskLevel.MEDIUM,
        "create_ticket": RiskLevel.MEDIUM,
        "update_ticket": RiskLevel.MEDIUM,
        "update_lead": RiskLevel.MEDIUM,
        "write_content": RiskLevel.MEDIUM,
        "schedule_post": RiskLevel.MEDIUM,
        
        "send_proposal": RiskLevel.HIGH,
        "publish_content": RiskLevel.HIGH,
        "issue_refund": RiskLevel.HIGH,
        "create_invoice": RiskLevel.HIGH,
        "schedule_meeting": RiskLevel.HIGH,
        
        "financial_transfer": RiskLevel.CRITICAL,
        "delete_customer": RiskLevel.CRITICAL,
        "legal_action": RiskLevel.CRITICAL,
        "delete_data": RiskLevel.CRITICAL
    }
    
    base_level = action_risk_map.get(action, RiskLevel.MEDIUM)
    
    if parameters:
        if "amount" in parameters:
            amount = float(parameters["amount"])
            if amount > 1000:
                return RiskLevel.CRITICAL
            elif amount > 100:
                return RiskLevel.HIGH
        
        if "delete" in action.lower():
            return RiskLevel.CRITICAL
    
    return base_level
