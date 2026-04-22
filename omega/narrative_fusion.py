from typing import Dict, Any
import os
from .intelligence import generate_ai_briefing

def generate_narrative(argus_data: Dict[str, Any], reality_data: Dict[str, Any], action_class: str, dominant_scenario: str, horizon: str) -> str:
    """Generates a concise, analytical briefing. Prefers AI synthesis if available."""
    
    # ── Attempt AI Dynamic Synthesis ──
    if os.getenv("ANTHROPIC_API_KEY"):
        return generate_ai_briefing(argus_data, reality_data, action_class, dominant_scenario, horizon)

    # ── Fallback: Static Institutional Logic ──
    bias = argus_data["bias"].replace("_", " ")
    stability = argus_data["stability"]
    
    # Core scenario logic
    if dominant_scenario == "sweep_then_continuation":
        core = "Historical analogs favor expansion, while liquidity mapping suggests an initial sweep before durable resolution."
    elif dominant_scenario == "failed_breakout_trap":
        core = "The setup carries a high probability of apparent continuation failing into a trap sequence."
    elif dominant_scenario == "clean_continuation":
        core = "Subsystem alignment supports cleaner continuation than a typical distorted breakout."
    else:
        core = "The balance of evidence favors reversal after expansion quality degrades."
        
    return (
        f"{bias.capitalize()} pressure is present, but the structure remains {stability}. "
        f"{core} Deception is {reality_data['deception_score']:.2f}, with a projected horizon of {horizon}."
    )
