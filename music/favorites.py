"""
Favorites System
Save and manage favorite tracks per user
"""

import json
import os
from typing import List, Dict, Optional
import logging

log = logging.getLogger(__name__)

class FavoritesManager:
    """Manage user favorites"""
    
    def __init__(self, db_path: str = "data/favorites.json"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Load existing data
        if os.path.exists(db_path):
            try:
                with open(db_path, 'r') as f:
                    self.data = json.load(f)
            except:
                self.data = {}
        else:
            self.data = {}
    
    def _save(self):
        """Save to disk"""
        try:
            with open(self.db_path, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            log.error(f"Error saving favorites: {e}")
    
    async def add_favorite(self, user_id: int, uri: str, title: str, artist: str = None) -> bool:
        """Add track to user favorites"""
        user_key = str(user_id)
        
        if user_key not in self.data:
            self.data[user_key] = []
        
        # Check if already exists
        for fav in self.data[user_key]:
            if fav['uri'] == uri:
                return False
        
        # Add new favorite
        self.data[user_key].append({
            'uri': uri,
            'title': title,
            'artist': artist or 'Unknown'
        })
        
        self._save()
        return True
    
    async def remove_favorite(self, user_id: int, index: int) -> bool:
        """Remove favorite by index"""
        user_key = str(user_id)
        
        if user_key not in self.data:
            return False
        
        if 0 <= index < len(self.data[user_key]):
            self.data[user_key].pop(index)
            self._save()
            return True
        
        return False
    
    async def get_favorites(self, user_id: int) -> List[Dict]:
        """Get all favorites for user"""
        user_key = str(user_id)
        return self.data.get(user_key, [])
    
    async def clear_favorites(self, user_id: int):
        """Clear all favorites for user"""
        user_key = str(user_id)
        if user_key in self.data:
            self.data[user_key] = []
            self._save()
