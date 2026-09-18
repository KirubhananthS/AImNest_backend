class AssistantService:
    """Application boundary for assistant replies until a provider is configured."""

    @staticmethod
    def generate_reply(user_content: str) -> str:
        return f"AImNest AI: I can help you plan your next step for '{user_content[:60]}'."
