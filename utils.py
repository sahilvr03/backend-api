from models import Lead
from typing import List

def leads_to_csv(leads: List[Lead]) -> str:
    lines = ["name,company,email,phone"]
    for lead in leads:
        lines.append(f"{lead.name},{lead.company or ''},{lead.email or ''},{lead.phone or ''}")
    return "\n".join(lines)
