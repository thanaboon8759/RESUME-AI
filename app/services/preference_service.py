from app.schemas.preference import Preferences
from app.repositories import preference_repository

def get_preferences(user_id: str) -> Preferences | None:
    return preference_repository.get_preferences(user_id)

def update_preferences(prefs: Preferences, user_id: str) -> Preferences:
    preference_repository.update_preferences(prefs, user_id)
    return prefs
