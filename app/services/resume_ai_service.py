import os
from dotenv import load_dotenv
import asyncio
from app.schemas.candidate import ResumeAIResponse
from app.schemas.core import DecisionEnum

load_dotenv()

class ResumeAIClient:
    def __init__(self):
        self.api_url = os.getenv("RESUMEAI_API_URL", "https://api.dumbdog.ai")
        self.api_key = os.getenv("RESUMEAI_API_KEY")
        
    async def evaluate_candidate(self, candidate_name: str, position: str, resume_text: str) -> ResumeAIResponse:
        """
        Calls the ResumeAI API to evaluate a candidate based on their resume.
        Currently using mock data if the real API is not connected.
        """
        # If no API key is set, or if we want to mock it for development
        # we return a mock response that matches the expected AI output.
        if not self.api_key or self.api_key == "mock":
            # Simulate network latency
            await asyncio.sleep(1)
            
            # Simple logic for mock response
            score = 82
            decision = DecisionEnum.shortlisted
            if "junior" in position.lower():
                score = 70
            elif "senior" in position.lower():
                score = 90
                
            return ResumeAIResponse(
                score=score,
                decision=decision,
                reasons=[
                    "Python experience",
                    "FastAPI experience",
                    "Database experience"
                ]
            )
            
        # Implementation for the real API call would go here
        # import httpx
        # async with httpx.AsyncClient() as client:
        #     response = await client.post(
        #         f"{self.api_url}/v1/evaluate",
        #         json={"name": candidate_name, "position": position, "text": resume_text},
        #         headers={"Authorization": f"Bearer {self.api_key}"}
        #     )
        #     data = response.json()
        #     return ResumeAIResponse(**data)
        
        raise NotImplementedError("Real ResumeAI API integration not yet implemented")

# Singleton instance
resume_ai_client = ResumeAIClient()
