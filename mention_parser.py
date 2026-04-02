import re
from config import CLI_CONFIGS

SUPPORTED_TARGETS = list(CLI_CONFIGS.keys())

def parse(text: str) -> dict:
    text = text.strip()
    # 멘션 패턴: 문자열 시작 부분에서 @로 시작하고 지원되는 타겟 중 하나인 경우
    # 예: @claude 리팩토링해줘 -> target: claude, text: 리팩토링해줘
    pattern = rf"^@({'|'.join(SUPPORTED_TARGETS)})\b\s*(.*)"
    match = re.match(pattern, text, re.IGNORECASE)
    
    if match:
        target = match.group(1).lower()
        remaining_text = match.group(2)
        return {"target": target, "text": remaining_text}
    
    return {"target": None, "text": text}
