# -*- coding: utf-8 -*-
from mcp_server.data_skills.generic import GENERIC_RULES
from mcp_server.data_skills.behavior_analysis import BEHAVIOR_ANALYSIS_RULES
from mcp_server.data_skills.time_series import TIME_SERIES_RULES

ALL_SKILLS = {
    "generic": GENERIC_RULES,
    "behavior_analysis": BEHAVIOR_ANALYSIS_RULES,
    "time_series": TIME_SERIES_RULES,
}


def get_rules_for_type(project_type: str) -> list[dict]:
    skills = [GENERIC_RULES]
    type_map = {
        "behavior_analysis": BEHAVIOR_ANALYSIS_RULES,
        "time_series": TIME_SERIES_RULES,
        "business_report": GENERIC_RULES,
    }
    domain = type_map.get(project_type)
    if domain and domain not in skills:
        skills.append(domain)
    return skills
