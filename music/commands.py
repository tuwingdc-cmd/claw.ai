"""
Music Prefix Commands
.play, .skip, .fav, etc.
"""

import discord
from discord.ext import commands
import wavelink
from typing import Optional
import logging

log = logging.getLogger(__name__)

async def setup(bot):
    """Register music commands"""
    
    import logging
    log = logging.getLogger(__name__)
    log.info("🎵 Starting music commands registration...")
    
    from music.player import MusicPlayer, get_player, set_player, remove_player
    from music.views import create_now_playing_embed, MusicControlView
    from music.favorites import FavoritesManager
    
    # ============================================================
    # MAIN MUSIC COMMANDS
    # ============================================================
    
    @bot.command(name="play", aliases=["p"])
    async def play(ctx: commands.Context, *, query: str):
        """
        🎵 Play music from URL or search query
        Supports: YouTube, Spotify, SoundCloud playlists!
        
        Usage:
          .play never gonna give you up
          .play https://www.youtube.com/playlist?list=...
          .play https://open.spotify.com/playlist/...
        """
        
        # Check voice channel
        if not ctx.author.voice:
            return await ctx.send("❌ Join a voice channel first!")
        
        msg = await ctx.send("🔍 Searching...")
        
        # Get or create player
        player: wavelink.Player = ctx.guild.voice_client
        
        if not player:
            try:
                player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
                music_player = MusicPlayer(player)
                set_player(ctx.guild.id, music_player)
            except Exception as e:
                return await msg.edit(content=f"❌ Failed to connect: {e}")
        else:
            music_player = get_player(ctx.guild.id)
            if not music_player:
                music_player = MusicPlayer(player)
                set_player(ctx.guild.id, music_player)
        
        # Search tracks
        try:
            tracks: wavelink.Search = await wavelink.Playable.search(query)
            
            if not tracks:
                return await msg.edit(content="❌ No results found!")
            
            # Check if playlist
            if isinstance(tracks, wavelink.Playlist):
                # Multi-track playlist
                for track in tracks.tracks:
                    track.requester = ctx.author
                
                await music_player.add_tracks(tracks.tracks)
                
                embed = discord.Embed(
                    title="📋 Playlist Added",
                    description=f"**{tracks.name}**\n\n{len(tracks.tracks)} tracks added to queue",
                    color=0x1DB954
                )
                
                if tracks.artwork:
                    embed.set_thumbnail(url=tracks.artwork)
                
                await msg.edit(content=None, embed=embed)
                
                # Start playing if not already
                if not player.playing:
                    await music_player.play_next()
                    
            else:
                # Single track
                track = tracks[0]
                track.requester = ctx.author
                
                if player.playing:
                    # Add to queue
                    await music_player.add_track(track)
                    
                    embed = discord.Embed(
                        title="➕ Added to Queue",
                        description=f"**[{track.title}]({track.uri})**\n{track.author}",
                        color=0x1DB954
                    )
                    
                    if track.artwork:
                        embed.set_thumbnail(url=track.artwork)
                    
                    embed.add_field(name="Duration", value=MusicPlayer._format_time(track.length), inline=True)
                    embed.add_field(name="Position", value=f"#{len(music_player.queue)}", inline=True)
                    
                    await msg.edit(content=None, embed=embed)
                else:
                    # Play immediately
                    await player.play(track)
                    
                    embed = create_now_playing_embed(track, player)
                    view = MusicControlView(player)
                    
                    await msg.delete()
                    np_msg = await ctx.send(embed=embed, view=view)
                    music_player.now_playing_message = np_msg
        
        except Exception as e:
            log.error(f"Play error: {e}")
            await msg.edit(content=f"❌ Error: {e}")
    
    @bot.command(name="skip", aliases=["s", "next"])
    async def skip(ctx: commands.Context, count: Optional[int] = 1):
        """
        ⏭️ Skip current track(s)
        
        Usage:
          .skip      → Skip 1 track
          .skip 3    → Skip 3 tracks
        """
        
        music_player = get_player(ctx.guild.id)
        
        if not music_player or not music_player.player.playing:
            return await ctx.send("❌ Nothing is playing!")
        
        if count < 1:
            return await ctx.send("❌ Count must be at least 1!")
        
        current = music_player.current
        await music_player.skip(count)
        
        if count == 1:
            await ctx.send(f"⏭️ Skipped: **{current.title}**")
        else:
            await ctx.send(f"⏭️ Skipped {count} tracks!")
    
    @bot.command(name="queue", aliases=["q"])
    async def queue(ctx: commands.Context):
        """
        📋 Show music queue
        
        Usage: .queue
        """
        
        music_player = get_player(ctx.guild.id)
        
        if not music_player or not music_player.player.playing:
            return await ctx.send("❌ Nothing is playing!")
        
        queue_lines = music_player.get_queue_display(15)
        
        embed = discord.Embed(
            title="📋 Music Queue",
            description="\n".join(queue_lines),
            color=0x1DB954
        )
        
        # Add now playing
        if music_player.current:
            embed.insert_field_at(
                0,
                name="🎵 Now Playing",
                value=f"**{music_player.current.title}** - {music_player.current.author}",
                inline=False
            )
        
        total_duration = sum(t.length for t in music_player.queue)
        embed.set_footer(text=f"Total: {len(music_player.queue)} tracks • {MusicPlayer._format_time(total_duration)}")
        
        await ctx.send(embed=embed)
    
    @bot.command(name="nowplaying", aliases=["np", "current"])
    async def nowplaying(ctx: commands.Context):
        """
        🎵 Show current track
        
        Usage: .np
        """
        
        music_player = get_player(ctx.guild.id)
        
        if not music_player or not music_player.player.playing:
            return await ctx.send("❌ Nothing is playing!")
        
        embed = create_now_playing_embed(music_player.current, music_player.player)
        view = MusicControlView(music_player.player)
        
        await ctx.send(embed=embed, view=view)
    
    @bot.command(name="stop", aliases=["disconnect", "dc", "leave"])
    async def stop(ctx: commands.Context):
        """
        ⏹️ Stop music and disconnect
        
        Usage: .stop
        """
        
        player: wavelink.Player = ctx.guild.voice_client
        
        if not player:
            return await ctx.send("❌ Not connected!")
        
        music_player = get_player(ctx.guild.id)
        if music_player:
            await music_player.clear_queue()
        
        await player.disconnect()
        remove_player(ctx.guild.id)
        
        await ctx.send("⏹️ Stopped and disconnected!")
    
    @bot.command(name="clearqueue", aliases=["cq", "clq"])
    async def clear_queue(ctx: commands.Context):
        """
        🗑️ Clear the queue
        
        Usage: .clearqueue atau .cq
        """
        
        music_player = get_player(ctx.guild.id)
        
        if not music_player:
            return await ctx.send("❌ No active player!")
        
        count = len(music_player.queue)
        await music_player.clear_queue()
        
        await ctx.send(f"🗑️ Cleared {count} track(s) from queue!")
    
    @bot.command(name="shuffle", aliases=["sh"])
    async def shuffle(ctx: commands.Context):
        """
        🔀 Toggle shuffle mode
        
        Usage: .shuffle
        """
        
        music_player = get_player(ctx.guild.id)
        
        if not music_player:
            return await ctx.send("❌ No active player!")
        
        enabled = await music_player.toggle_shuffle()
        status = "On 🔀" if enabled else "Off ➡️"
        await ctx.send(f"🔀 Shuffle: **{status}**")
    
    @bot.command(name="loop", aliases=["repeat"])
    async def loop(ctx: commands.Context):
        """
        🔁 Toggle loop mode (off → track → queue)
        
        Usage: .loop
        """
        
        music_player = get_player(ctx.guild.id)
        
        if not music_player:
            return await ctx.send("❌ No active player!")
        
        mode = await music_player.toggle_loop()
        mode_text = {"off": "Off ➡️", "track": "Track 🔂", "queue": "Queue 🔁"}
        await ctx.send(f"🔁 Loop: **{mode_text[mode]}**")
    
    @bot.command(name="pause")
    async def pause(ctx: commands.Context):
        """
        ⏸️ Pause playback
        
        Usage: .pause
        """
        
        player: wavelink.Player = ctx.guild.voice_client
        
        if not player or not player.playing:
            return await ctx.send("❌ Nothing is playing!")
        
        await player.pause(True)
        await ctx.send("⏸️ Paused!")
    
    @bot.command(name="resume", aliases=["unpause"])
    async def resume(ctx: commands.Context):
        """
        ▶️ Resume playback
        
        Usage: .resume
        """
        
        player: wavelink.Player = ctx.guild.voice_client
        
        if not player or not player.paused:
            return await ctx.send("❌ Player is not paused!")
        
        await player.pause(False)
        await ctx.send("▶️ Resumed!")
    
    @bot.command(name="volume", aliases=["vol", "v"])
    async def volume(ctx: commands.Context, vol: Optional[int] = None):
        """
        🔊 Set or show volume (0-100)
        
        Usage:
          .volume       → Show current volume
          .volume 50    → Set volume to 50%
        """
        
        player: wavelink.Player = ctx.guild.voice_client
        
        if not player:
            return await ctx.send("❌ Not connected!")
        
        if vol is None:
            return await ctx.send(f"🔊 Volume: **{player.volume}%**")
        
        if vol < 0 or vol > 100:
            return await ctx.send("❌ Volume must be between 0-100!")
        
        await player.set_volume(vol)
        await ctx.send(f"🔊 Volume set to **{vol}%**")
    
    @bot.command(name="lyrics", aliases=["ly"])
    async def lyrics(ctx: commands.Context, *, query: str = None):
        """
        📝 Show lyrics for current/specific track
        
        Usage:
          .lyrics                    → Lyrics lagu yang sedang main
          .lyrics shape of you       → Lyrics lagu spesifik
        """
        
        from music.lyrics import fetch_lyrics
        
        if query:
            # Manual search
            msg = await ctx.send(f"🔍 Searching lyrics: **{query}**...")
            lyrics_text = await fetch_lyrics(query)
            track_name = query
            
        else:
            # Current track
            music_player = get_player(ctx.guild.id)
            
            if not music_player or not music_player.current:
                return await ctx.send(
                    "❌ No track playing!\n"
                    "💡 Usage: `.lyrics <judul lagu>` untuk cari lyrics manual"
                )
            
            current = music_player.current
            title = clean_title(current.title)
            artist = clean_artist(current.author) if current.author else None
            track_name = f"{title}{f' - {artist}' if artist else ''}"
            
            msg = await ctx.send(f"🔍 Searching lyrics: **{track_name}**...")
            lyrics_text = await fetch_lyrics(title, artist)
        
        if lyrics_text:
            # Split jika terlalu panjang (max 4000 chars per embed)
            chunks = []
            while len(lyrics_text) > 4000:
                # Potong di newline terdekat
                cut = lyrics_text.rfind("\n", 0, 4000)
                if cut == -1:
                    cut = 4000
                chunks.append(lyrics_text[:cut])
                lyrics_text = lyrics_text[cut:].strip()
            chunks.append(lyrics_text)
            
            # Kirim chunk pertama (edit pesan loading)
            embed = discord.Embed(
                title=f"📝 {track_name}",
                description=chunks[0],
                color=0x1DB954
            )
            
            if len(chunks) > 1:
                embed.set_footer(text=f"Part 1/{len(chunks)} — ketik .lyrics lagi untuk lihat semua")
            
            await msg.edit(content=None, embed=embed)
            
            # Kirim chunk berikutnya (kalau ada)
            for i, chunk in enumerate(chunks[1:], 2):
                embed = discord.Embed(
                    description=chunk,
                    color=0x1DB954
                )
                embed.set_footer(text=f"Part {i}/{len(chunks)}")
                await ctx.send(embed=embed)
        
        else:
            await msg.edit(
                content=f"❌ Lyrics tidak ditemukan untuk: **{track_name}**\n"
                        f"💡 Coba: `.lyrics {track_name}` atau nama lagu yang lebih spesifik"
            )
    
    # ============================================================
    # FAVORITES COMMANDS GROUP
    # ============================================================
    
    @bot.group(name="favorite", aliases=["fav", "f"], invoke_without_command=True)
    async def favorite(ctx: commands.Context):
        """
        ❤️ Favorite commands
        
        Usage:
          .fav          → Add current track to favorites
          .fav list     → List your favorites
          .fav play 3   → Play favorite #3
          .fav rm 2     → Remove favorite #2
          .fav clear    → Clear all favorites
        """
        
        # Default: add current track
        await ctx.invoke(bot.get_command('favorite add'))
    
    @favorite.command(name="add", aliases=["a", "save"])
    async def fav_add(ctx: commands.Context):
        """❤️ Add current track to favorites"""
        
        music_player = get_player(ctx.guild.id)
        
        if not music_player or not music_player.current:
            return await ctx.send("❌ No track playing!")
        
        fav = FavoritesManager()
        track = music_player.current
        
        success = await fav.add_favorite(
            ctx.author.id,
            track.uri,
            track.title,
            track.author
        )
        
        if success:
            await ctx.send(f"❤️ Added to favorites: **{track.title}**")
        else:
            await ctx.send("⚠️ Already in favorites!")
    
    @favorite.command(name="list", aliases=["ls", "show", "all"])
    async def fav_list(ctx: commands.Context):
        """📋 Show your favorite tracks"""
        
        fav = FavoritesManager()
        favorites = await fav.get_favorites(ctx.author.id)
        
        if not favorites:
            return await ctx.send("❤️ No favorites yet!\nUse `.fav` while playing a track to add it.")
        
        lines = []
        for i, track in enumerate(favorites[:20], 1):
            lines.append(f"`{i}.` **{track['title']}** - {track['artist']}")
        
        embed = discord.Embed(
            title=f"❤️ {ctx.author.display_name}'s Favorites",
            description="\n".join(lines),
            color=0xFF1744
        )
        
        if len(favorites) > 20:
            embed.set_footer(text=f"Showing 20 of {len(favorites)} favorites")
        else:
            embed.set_footer(text=f"{len(favorites)} favorite(s)")
        
        await ctx.send(embed=embed)
    
    @favorite.command(name="play", aliases=["p"])
    async def fav_play(ctx: commands.Context, number: int):
        """▶️ Play a favorite track by number"""
        
        if not ctx.author.voice:
            return await ctx.send("❌ Join a voice channel first!")
        
        fav = FavoritesManager()
        favorites = await fav.get_favorites(ctx.author.id)
        
        if not favorites:
            return await ctx.send("❌ No favorites! Add some first with `.fav`")
        
        if number < 1 or number > len(favorites):
            return await ctx.send(f"❌ Invalid number! Use 1-{len(favorites)}")
        
        track_data = favorites[number - 1]
        
        # Use play command with URI
        await ctx.invoke(bot.get_command('play'), query=track_data['uri'])
    
    @favorite.command(name="remove", aliases=["rm", "delete", "del"])
    async def fav_remove(ctx: commands.Context, number: int):
        """🗑️ Remove a favorite by number"""
        
        fav = FavoritesManager()
        favorites = await fav.get_favorites(ctx.author.id)
        
        if not favorites:
            return await ctx.send("❌ No favorites!")
        
        if number < 1 or number > len(favorites):
            return await ctx.send(f"❌ Invalid number! Use 1-{len(favorites)}")
        
        track_data = favorites[number - 1]
        success = await fav.remove_favorite(ctx.author.id, number - 1)
        
        if success:
            await ctx.send(f"🗑️ Removed: **{track_data['title']}**")
        else:
            await ctx.send("❌ Failed to remove!")
    
    @favorite.command(name="clear", aliases=["deleteall", "removeall"])
    async def fav_clear(ctx: commands.Context):
        """🗑️ Clear all your favorites"""
        
        fav = FavoritesManager()
        favorites = await fav.get_favorites(ctx.author.id)
        
        if not favorites:
            return await ctx.send("❌ No favorites to clear!")
        
        count = len(favorites)
        await fav.clear_favorites(ctx.author.id)
        
        await ctx.send(f"🗑️ Cleared {count} favorite(s)!")
    
    @favorite.command(name="playall", aliases=["queue", "queueall"])
    async def fav_playall(ctx: commands.Context):
        """📋 Add all favorites to queue"""
        
        if not ctx.author.voice:
            return await ctx.send("❌ Join a voice channel first!")
        
        fav = FavoritesManager()
        favorites = await fav.get_favorites(ctx.author.id)
        
        if not favorites:
            return await ctx.send("❤️ No favorites!")
        
        msg = await ctx.send(f"📋 Adding {len(favorites)} favorites to queue...")
        
        # Get or create player
        player: wavelink.Player = ctx.guild.voice_client
        
        if not player:
            try:
                player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
                music_player = MusicPlayer(player)
                set_player(ctx.guild.id, music_player)
            except Exception as e:
                return await msg.edit(content=f"❌ Failed to connect: {e}")
        else:
            music_player = get_player(ctx.guild.id)
            if not music_player:
                music_player = MusicPlayer(player)
                set_player(ctx.guild.id, music_player)
        
        # Add all favorites
        added = 0
        for fav_track in favorites:
            try:
                tracks = await wavelink.Playable.search(fav_track['uri'])
                if tracks:
                    track = tracks[0] if not isinstance(tracks, wavelink.Playlist) else tracks.tracks[0]
                    track.requester = ctx.author
                    await music_player.add_track(track)
                    added += 1
            except:
                pass
        
        await msg.edit(content=f"✅ Added {added}/{len(favorites)} favorites to queue!")
        
        # Start playing if not already
        if not player.playing:
            await music_player.play_next()
    
    log.info(f"🎵 Registered commands: {[c.name for c in bot.commands if hasattr(c, 'cog_name') or c.name in ['play', 'skip', 'queue', 'stop', 'favorite']]}")
    log.info("🎵 Music prefix commands registered!")
