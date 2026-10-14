from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base
def now(): return datetime.now(timezone.utc).replace(tzinfo=None)
class GameRoom(Base):
    __tablename__="game_rooms"
    id: Mapped[int]=mapped_column(primary_key=True)
    room_code: Mapped[str]=mapped_column(String(8), unique=True, index=True)
    status: Mapped[str]=mapped_column(String(20), default="lobby")
    current_round: Mapped[int]=mapped_column(Integer, default=0)
    total_rounds: Mapped[int]=mapped_column(Integer, default=3)
    created_at: Mapped[datetime]=mapped_column(DateTime, default=now)
    started_at: Mapped[datetime|None]=mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime|None]=mapped_column(DateTime, nullable=True)
    players: Mapped[list["Player"]]=relationship(back_populates="room", cascade="all, delete-orphan")
    rounds: Mapped[list["GameRound"]]=relationship(back_populates="room", cascade="all, delete-orphan")
class Player(Base):
    __tablename__="players"
    id: Mapped[int]=mapped_column(primary_key=True)
    room_id: Mapped[int]=mapped_column(ForeignKey("game_rooms.id"))
    display_name: Mapped[str]=mapped_column(String(40))
    score: Mapped[int]=mapped_column(Integer, default=0)
    joined_at: Mapped[datetime]=mapped_column(DateTime, default=now)
    left_at: Mapped[datetime|None]=mapped_column(DateTime, nullable=True)
    room: Mapped[GameRoom]=relationship(back_populates="players")
class GameRound(Base):
    __tablename__="game_rounds"
    id: Mapped[int]=mapped_column(primary_key=True)
    room_id: Mapped[int]=mapped_column(ForeignKey("game_rooms.id"))
    round_number: Mapped[int]=mapped_column(Integer)
    drawer_player_id: Mapped[int]=mapped_column(ForeignKey("players.id"))
    word: Mapped[str]=mapped_column(String(80))
    started_at: Mapped[datetime]=mapped_column(DateTime, default=now)
    ended_at: Mapped[datetime|None]=mapped_column(DateTime, nullable=True)
    room: Mapped[GameRoom]=relationship(back_populates="rounds")
    guesses: Mapped[list["Guess"]]=relationship(back_populates="round", cascade="all, delete-orphan")
class Guess(Base):
    __tablename__="guesses"
    id: Mapped[int]=mapped_column(primary_key=True)
    round_id: Mapped[int]=mapped_column(ForeignKey("game_rounds.id"))
    player_id: Mapped[int]=mapped_column(ForeignKey("players.id"))
    guess_text: Mapped[str]=mapped_column(Text)
    is_correct: Mapped[bool]=mapped_column(Boolean, default=False)
    submitted_at: Mapped[datetime]=mapped_column(DateTime, default=now)
    round: Mapped[GameRound]=relationship(back_populates="guesses")
