"""
Core Music Player Logic
Extended Wavelink Player with queue, loop, shuffle
"""

import wavelink
import random
from typing import Optional, List
import logging

log = logging.getLogger(__name__)


class MusicPlayer:
    """Extended player with custom features"""

    def __init__(self, player: wavelink.Player):
        self.player = player
        self.queue: List[wavelink.Playable] = []
        self.history: List[wavelink.Playable] = []
        self.loop_mode = "off"  # off | track | queue
        self.shuffle_enabled = False
        self.now_playing_message = None
        self.auto_play = True

    @property
    def current(self) -> Optional[wavelink.Playable]:
        return self.player.current

    @property
    def is_playing(self) -> bool:
        return self.player.playing

    @property
    def is_paused(self) -> bool:
        return self.player.paused

    async def add_track(self, track: wavelink.Playable):
        self.queue.append(track)

    async def add_tracks(self, tracks: List[wavelink.Playable]):
        self.queue.extend(tracks)

    async def play_next(self) -> Optional[wavelink.Playable]:
        """Play next track from queue"""
        track = None

        # Handle loop mode
        if self.loop_mode == "track" and self.current:
            track = self.current
            log.info(f"🎵 Loop track: {track.title}")

        elif self.loop_mode == "queue" and self.current:
            self.queue.append(self.current)
            track = self.queue.pop(0) if self.queue else None
            log.info(f"🎵 Loop queue: {track.title if track else 'empty'}")

        else:
            if not self.queue:
                log.info("🎵 Queue empty — nothing to play next")

                # Notify channel that queue is done
                if self.now_playing_message:
                    try:
                        import discord
                        embed = discord.Embed(
                            description=(
                                "⏹️ Queue selesai! Tambahkan lagu lagi "
                                "atau bot akan disconnect dalam 2 menit."
                            ),
                            color=0x95a5a6
                        )
                        await self.now_playing_message.channel.send(
                            embed=embed, delete_after=120
                        )
                    except Exception as e:
                        log.debug(f"Could not send queue-end message: {e}")
                return None

            if self.shuffle_enabled:
                track = random.choice(self.queue)
                self.queue.remove(track)
            else:
                track = self.queue.pop(0)

        if track:
            # Save current to history before switching
            if self.current:
                self.history.append(self.current)
                if len(self.history) > 50:
                    self.history = self.history[-50:]

            try:
                await self.player.play(track)
                log.info(f"🎵 Now playing: {track.title} by {track.author}")
                return track
            except Exception as e:
                log.error(f"🎵 Failed to play '{track.title}': {e}")
                # Try next track if this one fails
                if self.queue:
                    log.info("🎵 Skipping failed track, trying next...")
                    return await self.play_next()
                return None

        return None

    async def play_previous(self) -> Optional[wavelink.Playable]:
        if not self.history:
            return None
        track = self.history.pop()
        if self.current:
            self.queue.insert(0, self.current)
        await self.player.play(track)
        return track

    async def toggle_loop(self) -> str:
        modes = ["off", "track", "queue"]
        idx = modes.index(self.loop_mode)
        self.loop_mode = modes[(idx + 1) % len(modes)]
        log.info(f"🎵 Loop mode: {self.loop_mode}")
        return self.loop_mode

    async def toggle_shuffle(self) -> bool:
        self.shuffle_enabled = not self.shuffle_enabled
        if self.shuffle_enabled and self.queue:
            random.shuffle(self.queue)
        return self.shuffle_enabled

    async def skip(self, count: int = 1):
        for _ in range(count - 1):
            if self.queue:
                skipped = self.queue.pop(0)
                log.info(f"🎵 Skipped from queue: {skipped.title}")
        await self.play_next()

    async def clear_queue(self):
        self.queue.clear()
        log.info("🎵 Queue cleared")

    async def remove_track(self, index: int) -> Optional[wavelink.Playable]:
        if 0 <= index < len(self.queue):
            return self.queue.pop(index)
        return None

    def get_queue_display(self, max_tracks: int = 10) -> List[str]:
        if not self.queue:
            return ["Queue is empty"]
        lines = []
        for i, track in enumerate(self.queue[:max_tracks], 1):
            duration = self._format_time(track.length)
            lines.append(
                f"`{i}.` **{track.title}** - {track.author} `[{duration}]`"
            )
        if len(self.queue) > max_tracks:
            lines.append(f"*...and {len(self.queue) - max_tracks} more*")
        return lines

    @staticmethod
    def _format_time(ms: int) -> str:
        seconds = ms // 1000
        mins, secs = divmod(seconds, 60)
        if mins >= 60:
            hours, mins = divmod(mins, 60)
            return f"{hours}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"


# ── Global player storage ──
_players = {}


def get_player(guild_id: int) -> Optional[MusicPlayer]:
    return _players.get(guild_id)


def set_player(guild_id: int, player: MusicPlayer):
    _players[guild_id] = player


def remove_player(guild_id: int):
    _players.pop(guild_id, None)
