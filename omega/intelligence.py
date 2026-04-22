import os
from anthropic import Anthropic
from typing import Dict, Any

def generate_ai_briefing(argus: Dict[str, Any], reality: Dict[str, Any], action: str, scenario: str, horizon: str) -> str:
    """
    Synthesizes Argus Omega fusion data into a high-fidelity institutional narrative using Claude-3.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return "Intelligence offline. Manual audit required."
        
    client = Anthropic(api_key=api_key)
    model = os.getenv("CLAUDE_MODEL", "claude-3-haiku-20240307") # Default to Haiku for speed
    
    prompt = f"""
    You are the Argus Omega Intelligence Core at ScriptMasterLabs™.
    Synthesize the following fusion data into a professional, concise market briefing (max 60 words).
    
    INPUT DATA:
    - Omega Score: {argus.get('omega_score', 'N/A')} (Institutional Conviction)
    - Action Class: {action}
    - Scenario: {scenario}
    - Deception Score: {reality.get('deception_score', 'N/A')}
    - Projected Horizon: {horizon}
    
    Output exactly one high-density paragraph explaining the strategic posture and the key structural risk.
    Do not use fluff. Return ONLY the briefing text.
    """
    
    try:
        message = client.messages.create(
            model=model,
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text.strip()
    except Exception as e:
        print(f"Argus AI Hook Failed: {e}")
        return "AI synthesis unavailable due to connection error."
