# -*- coding: utf-8 -*-
"""Multi-Agent System for BeverageOps AI (Mixue 39 Tôn Quang Phiệt).

Specialized Autonomous Agents:
- QueryClassifier: NLU intent and entity extraction
- RepoDocsAgent: Full repository, documentation, SOP, and audit report search
- DatabaseAnalyticsAgent: Deep SQL and JSON data analytics (Sales, Shifts, Stock, HR)
- OperationsBOMAgent: Recipe BOM, SOP bar rules, Prep, PO, and Cup Sticker decoder
- NLPSynthesizer: Context synthesis into natural, comprehensive Vietnamese responses
- MultiAgentOrchestrator: High-level supervisor routing and aggregating multi-agent findings
"""

from .multi_agent_orchestrator import MultiAgentOrchestrator

__all__ = ["MultiAgentOrchestrator"]
