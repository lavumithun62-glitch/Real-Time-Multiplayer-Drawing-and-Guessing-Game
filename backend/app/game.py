
import asyncio
import random
import time

from .config import settings
from .database import SessionLocal
from .models import GameRoom, Player, GameRound, now


WORDS = [
    "rainbow",
    "elephant",
    "bicycle",
    "sunflower",
    "castle",
    "pizza",
    "rocket",
    "guitar",
    "turtle",
    "waterfall",
    "airplane",
    "lighthouse",
    "dragon",
    "snowman",
    "pineapple",
    "umbrella",
]


def score_for_guess(seconds_left: int, round_number: int) -> int:
    """Calculate points for a correct guess."""
    return max(
        10,
        100 + max(0, seconds_left) + max(0, round_number - 1) * 10,
    )


class LiveRoom:
    def __init__(self, code):
        self.code = code
        self.sockets = {}
        self.ready = set()
        self.names = {}
        self.scores = {}

        self.round_index = 0
        self.total_rounds = settings.total_rounds
        self.drawer_id = None
        self.word = None
        self.deadline = 0
        self.active = False
        self.solved = set()
        self.operations = []
        self.task = None
        self.host_id = None
        self.db_room_id = None

    async def send(self, pid, event, data=None):
        """Send an event to one connected player."""
        pid = str(pid)
        ws = self.sockets.get(pid)

        if ws is None:
            return False

        try:
            await ws.send_json({"type": event, **(data or {})})
            return True
        except Exception:
            # Do not remove a socket here: a failed send may be transient.
            return False

    async def broadcast(self, event, data=None, exclude=None):
        """Broadcast an event to connected players."""
        excluded_pid = str(exclude) if exclude is not None else None

        for pid in list(self.sockets.keys()):
            if pid != excluded_pid:
                await self.send(pid, event, data)

    def lobby(self):
        """Return the current lobby state."""
        players = []

        for pid, display_name in self.names.items():
            players.append(
                {
                    "id": int(pid),
                    "display_name": display_name,
                    "score": self.scores.get(pid, 0),
                    "ready": pid in self.ready,
                    "connected": pid in self.sockets,
                }
            )

        return {
            "room_code": self.code,
            "status": "playing" if self.active else "lobby",
            "current_round": self.round_index,
            "total_rounds": self.total_rounds,
            "players": players,
        }

    async def lobby_update(self):
        """Send a fresh lobby state after a player changes status."""
        await self.broadcast("lobby_state", self.lobby())

    async def start(self):
        """Start the game when enough connected players are ready."""
        connected_players = list(self.sockets.keys())

        if self.active:
            await self.broadcast(
                "error",
                {"message": "The game has already started."},
            )
            return

        if len(connected_players) < settings.room_min_players:
            await self.broadcast(
                "error",
                {
                    "message": (
                        f"At least {settings.room_min_players} "
                        "connected players are required."
                    )
                },
            )
            return

        if not all(pid in self.ready for pid in connected_players):
            await self.broadcast(
                "error",
                {"message": "All connected players must be ready."},
            )
            return

        self.active = True
        self.round_index = 0

        db = SessionLocal()
        try:
            room = (
                db.query(GameRoom)
                .filter_by(room_code=self.code)
                .first()
            )

            if room:
                room.status = "playing"
                room.started_at = now()
                room.total_rounds = self.total_rounds
                db.commit()
                self.db_room_id = room.id
        finally:
            db.close()

        await self.broadcast(
            "game_started",
            {"total_rounds": self.total_rounds},
        )

        await self.next_round()

    async def next_round(self):
        """Start the next round or finish the game."""
        connected_players = list(self.sockets.keys())

        if len(connected_players) < settings.room_min_players:
            self.active = False
            await self.finish()
            return

        if self.round_index >= self.total_rounds:
            self.active = False
            await self.finish()
            return

        self.round_index += 1
        self.solved.clear()
        self.operations.clear()

        # Choose the drawer from connected players only.
        order = connected_players
        self.drawer_id = order[
            (self.round_index - 1) % len(order)
        ]

        self.word = random.choice(WORDS)
        self.deadline = time.monotonic() + settings.round_seconds

        db = SessionLocal()
        round_id = None

        try:
            room = (
                db.query(GameRoom)
                .filter_by(room_code=self.code)
                .first()
            )

            if room:
                room.current_round = self.round_index

                game_round = GameRound(
                    room_id=room.id,
                    round_number=self.round_index,
                    drawer_player_id=int(self.drawer_id),
                    word=self.word,
                    started_at=now(),
                )

                db.add(game_round)
                db.commit()
                round_id = game_round.id
        finally:
            db.close()

        await self.broadcast(
            "round_started",
            {
                "round_number": self.round_index,
                "total_rounds": self.total_rounds,
                "drawer_id": int(self.drawer_id),
                "duration": settings.round_seconds,
                "word_length": len(self.word),
                "scores": self.scores,
            },
        )

        # Only the drawer receives the secret word.
        await self.send(
            self.drawer_id,
            "drawer_word",
            {"word": self.word},
        )

        if self.task and not self.task.done():
            self.task.cancel()

        self.task = asyncio.create_task(self.countdown(round_id))

    async def countdown(self, round_id):
        """Broadcast the timer and end the round when time expires."""
        try:
            while self.active and time.monotonic() < self.deadline:
                await self.broadcast(
                    "timer",
                    {
                        "seconds_left": max(
                            0,
                            int(self.deadline - time.monotonic()),
                        )
                    },
                )
                await asyncio.sleep(1)

            if self.active:
                await self.end_round(round_id, "time_up")

        except asyncio.CancelledError:
            pass

    async def end_round(self, round_id, reason):
        """Finish the current round and continue to the next one."""
        if not self.active:
            return

        self.active = False

        db = SessionLocal()
        try:
            game_round = (
                db.query(GameRound).filter_by(id=round_id).first()
                if round_id
                else None
            )

            if game_round:
                game_round.ended_at = now()
                db.commit()
        finally:
            db.close()

        await self.broadcast(
            "round_ended",
            {
                "reason": reason,
                "word": self.word,
                "scores": self.scores,
            },
        )

        await asyncio.sleep(3)

        # Do not start another round if the game was stopped.
        self.active = True
        await self.next_round()

    async def finish(self):
        """Persist scores and finish the game."""
        if self.task and self.task is not asyncio.current_task():
            if not self.task.done():
                self.task.cancel()

        db = SessionLocal()

        try:
            room = (
                db.query(GameRoom)
                .filter_by(room_code=self.code)
                .first()
            )

            if room:
                room.status = "completed"
                room.ended_at = now()

            for pid, score in self.scores.items():
                player = (
                    db.query(Player)
                    .filter_by(id=int(pid))
                    .first()
                )

                if player:
                    player.score = score

            db.commit()
        finally:
            db.close()

        leaderboard = sorted(
            [
                {
                    "player_id": int(pid),
                    "display_name": self.names.get(pid, "Player"),
                    "score": score,
                }
                for pid, score in self.scores.items()
            ],
            key=lambda item: item["score"],
            reverse=True,
        )

        await self.broadcast(
            "game_finished",
            {"leaderboard": leaderboard},
        )
