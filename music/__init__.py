"""
Music Module - Lavalink Integration
Spotify-style music player with favorites & multi-link support
"""

from .player import MusicPlayer
from .views import MusicControlView, create_now_playing_embed
from .commands import setup as setup_music_commands
from .favorites import FavoritesManager

__all__ = [
    'MusicPlayer',
    'MusicControlView', 
    'create_now_playing_embed',
    'setup_music_commands',
    'FavoritesManager'
]
