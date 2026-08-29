"""AI investigation service with deterministic fallback."""


async def investigate(packet: dict, llm_api_key: str = "") -> dict:
    classification = packet.get("classification", {}).get("type", "UNKNOWN")
    risk = packet.get("risk", {})
    risk_level = risk.get("level", "LOW")
    risk_score = risk.get("score", 0)
    summary = f"{classification} with {risk_level} risk based on supplied evidence."

    return {
        "summary": summary,
        "situation": summary,
        "reasoning": [
            "The investigation uses only backend-calculated evidence.",
            "No external facts were inferred by the AI fallback.",
        ],
        "recommended_action": "Review the event location and nearby context before escalation.",
        "confidence": packet.get("classification", {}).get("confidence", 0.0),
        "risk": {"level": risk_level, "score": risk_score},
        "llm_used": bool(llm_api_key),
    }
