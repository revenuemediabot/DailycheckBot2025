# models/onboarding.py

from dataclasses import dataclass

@dataclass
class OnboardingProgress:
    passed: bool = False
    current_step: int = 0
