
import asyncio
import logging
import random
import string
import time

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, engine, get_db, SessionLocal
from .models import GameRoom, Player, GameRound, Guess, now
from .schemas import CreateRoom, JoinRoom
from .game import LiveRoom, score_for_guess
from .auth import create_player_token, verify_player_token


logger = logging.getLogger("drawing_game")

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="REST API and WebSocket server for the real-time drawing game",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

live_rooms: dict[str, LiveRoom] = {}


def new_code() -> str:
    return "".join(
        random.choices(string.ascii_uppercase + string.digits, k=6)
    )


def room_payload(room, db):
    live = live_rooms.get(room.room_code)
    players = db.query(Player).filter_by(room_id=room.id).all()

    return {
        "room_code": room.room_code,
        "status": room.status,
        "current_round": room.current_round,
        "total_rounds": room.total_rounds,
        "players": [
            {
                "id": player.id,
                "display_name": player.display_name,
                "score": (
                    live.scores.get(str(player.id), player.score)
                    if live
                    else player.score
                ),
                "ready": bool(
                    live and str(player.id) in live.ready
                ),
                "connected": bool(
                    live and str(player.id) in live.sockets
                ),
            }
            for player in players
        ],
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/rooms", status_code=201)
def create_room(
    payload: CreateRoom,
    db: Session = Depends(get_db),
):
    name = payload.display_name.strip()
    if not name:
        raise HTTPException(422, "Display name is required")

    code = new_code()
    while db.query(GameRoom).filter_by(room_code=code).first():
        code = new_code()

    room = GameRoom(
        room_code=code,
        total_rounds=payload.total_rounds,
        status="lobby",
    )
    db.add(room)
    db.flush()

    player = Player(
        room_id=room.id,
        display_name=name,
    )
    db.add(player)
    db.commit()
    db.refresh(player)

    live = LiveRoom(code)
    live.total_rounds = payload.total_rounds
    live.names[str(player.id)] = player.display_name
    live.scores[str(player.id)] = player.score or 0
    live.host_id = str(player.id)
    live.db_room_id = room.id
    live_rooms[code] = live

    return {
        "room_code": code,
        "player_id": player.id,
        "display_name": player.display_name,
        "access_token": create_player_token(player.id, code),
        "token_type": "bearer",
        "room": room_payload(room, db),
    }


@app.post("/api/rooms/{room_code}/join")
def join_room(
    room_code: str,
    payload: JoinRoom,
    db: Session = Depends(get_db),
):
    code = room_code.upper()
    room = db.query(GameRoom).filter_by(room_code=code).first()

    if not room or room.status != "lobby":
        raise HTTPException(
            404,
            "Room not found or no longer accepting players",
        )

    name = payload.display_name.strip()
    if not name:
        raise HTTPException(422, "Display name is required")

    existing = (
        db.query(Player)
        .filter(
            Player.room_id == room.id,
            func.lower(Player.display_name) == name.lower(),
        )
        .first()
    )

    if existing:
        player = existing
        player.left_at = None
    else:
        player = Player(
            room_id=room.id,
            display_name=name,
        )
        db.add(player)
        db.flush()

    db.commit()
    db.refresh(player)

    live = live_rooms.setdefault(code, LiveRoom(code))
    live.total_rounds = room.total_rounds
    live.names[str(player.id)] = player.display_name
    live.scores.setdefault(str(player.id), player.score or 0)

    # Do not overwrite an existing host when another player joins.
    if live.host_id is None:
        live.host_id = str(player.id)

    return {
        "room_code": code,
        "player_id": player.id,
        "display_name": player.display_name,
        "access_token": create_player_token(player.id, code),
        "token_type": "bearer",
        "room": room_payload(room, db),
    }


@app.get("/api/rooms/{room_code}")
def get_room(
    room_code: str,
    db: Session = Depends(get_db),
):
    room = db.query(GameRoom).filter_by(
        room_code=room_code.upper()
    ).first()

    if not room:
        raise HTTPException(404, "Room not found")

    return room_payload(room, db)


@app.get("/api/history")
def history(
    limit: int = 20,
    db: Session = Depends(get_db),
):
    limit = max(1, min(limit, 100))

    rooms = (
        db.query(GameRoom)
        .filter(GameRoom.status == "completed")
        .order_by(GameRoom.ended_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "room_code": room.room_code,
            "started_at": room.started_at,
            "ended_at": room.ended_at,
            "total_rounds": room.total_rounds,
            "leaderboard": [
                {
                    "display_name": player.display_name,
                    "score": player.score,
                }
                for player in sorted(
                    room.players,
                    key=lambda item: item.score,
                    reverse=True,
                )
            ],
        }
        for room in rooms
    ]


@app.get("/api/leaderboard")
def leaderboard(
    limit: int = 20,
    db: Session = Depends(get_db),
):
    limit = max(1, min(limit, 100))

    rows = (
        db.query(
            Player.display_name,
            func.sum(Player.score).label("score"),
        )
        .group_by(Player.display_name)
        .order_by(func.sum(Player.score).desc())
        .limit(limit)
        .all()
    )

    return [
        {"display_name": name, "score": score or 0}
        for name, score in rows
    ]


@app.get("/api/players/{player_id}/stats")
def player_stats(
    player_id: int,
    db: Session = Depends(get_db),
):
    player = db.query(Player).filter_by(id=player_id).first()

    if not player:
        raise HTTPException(404, "Player not found")

    guesses = db.query(Guess).filter_by(
        player_id=player_id
    ).all()

    return {
        "player_id": player.id,
        "display_name": player.display_name,
        "score": player.score,
        "guesses": len(guesses),
        "correct_guesses": sum(
            guess.is_correct for guess in guesses
        ),
    }


@app.websocket("/ws/{room_code}/{player_id}")
async def websocket_endpoint(
    ws: WebSocket,
    room_code: str,
    player_id: int,
    token: str = "",
):
    code = room_code.upper()
    db = SessionLocal()

    try:
        player = db.query(Player).filter_by(
            id=player_id
        ).first()

        room = db.query(GameRoom).filter_by(
            room_code=code
        ).first()

        if (
            not token
            or not verify_player_token(token, player_id, code)
            or not player
            or not room
            or player.room_id != room.id
            or room.status in ("completed", "cancelled")
        ):
            await ws.accept()
            await ws.send_json({
                "type": "error",
                "message": "Invalid player or inactive room",
            })
            await ws.close(code=1008)
            return

        display_name = player.display_name
        initial_score = player.score or 0
        room_id = room.id
        total_rounds = room.total_rounds

    finally:
        db.close()

    await ws.accept()

    live = live_rooms.setdefault(code, LiveRoom(code))
    pid = str(player_id)

    # Save this socket locally so cleanup can check its identity.
    previous_socket = live.sockets.get(pid)

    live.names[pid] = display_name
    live.scores.setdefault(pid, initial_score)
    live.total_rounds = total_rounds

    # Register the new connection before closing the old connection.
    live.sockets[pid] = ws

    # Restore the host if this is a room whose live state was recreated.
    # Prefer the earliest player record as the host when necessary.
    if live.host_id is None:
        db = SessionLocal()
        try:
            first_player = (
                db.query(Player)
                .filter_by(room_id=room_id)
                .order_by(Player.id.asc())
                .first()
            )
            if first_player:
                live.host_id = str(first_player.id)
        finally:
            db.close()

    if previous_socket is not None and previous_socket is not ws:
        try:
            await previous_socket.close(
                code=4001,
                reason="Replaced by a newer connection",
            )
        except Exception:
            logger.debug(
                "Old socket already closed for player %s",
                player_id,
            )

    await live.send(
        pid,
        "connection_state",
        {
            "connected": True,
            "player_id": player_id,
        },
    )
    await live.send(pid, "lobby_state", live.lobby())

    snapshot = {
        "status": "playing" if live.active else "lobby",
        "current_round": live.round_index,
        "total_rounds": live.total_rounds,
        "drawer_id": (
            int(live.drawer_id) if live.drawer_id else None
        ),
        "seconds_left": (
            max(0, int(live.deadline - time.monotonic()))
            if live.active
            else 0
        ),
        "operations": live.operations[-5000:],
    }

    # The secret word must only be sent to the current drawer.
    if live.active and pid == live.drawer_id and live.word:
        snapshot["word"] = live.word

    await live.send(pid, "state_snapshot", snapshot)

    await live.broadcast(
        "player_joined",
        {
            "player_id": player_id,
            "display_name": display_name,
        },
        exclude=pid,
    )
    await live.lobby_update()

    try:
        while True:
            msg = await ws.receive_json()
            kind = msg.get("type")

            # Ignore messages from a socket that has been replaced.
            if live.sockets.get(pid) is not ws:
                break

            if kind == "ready":
                if not live.active:
                    if msg.get("ready", True):
                        live.ready.add(pid)
                    else:
                        live.ready.discard(pid)

                    await live.broadcast(
                        "player_ready",
                        {
                            "player_id": player_id,
                            "ready": pid in live.ready,
                        },
                    )
                    await live.lobby_update()

            elif kind == "start_game":
                if pid != live.host_id:
                    await live.send(
                        pid,
                        "error",
                        {
                            "message": (
                                "Only the room host can start the game."
                            )
                        },
                    )
                else:
                    await live.start()

            elif kind == "stroke":
                if not live.active or pid != live.drawer_id:
                    await live.send(
                        pid,
                        "error",
                        {
                            "message": (
                                "Only the current drawer can draw."
                            )
                        },
                    )
                    continue

                try:
                    operation = {
                        "x0": max(
                            0.0, min(1.0, float(msg["x0"]))
                        ),
                        "y0": max(
                            0.0, min(1.0, float(msg["y0"]))
                        ),
                        "x1": max(
                            0.0, min(1.0, float(msg["x1"]))
                        ),
                        "y1": max(
                            0.0, min(1.0, float(msg["y1"]))
                        ),
                        "color": str(
                            msg.get("color", "#222222")
                        )[:20],
                        "width": max(
                            1.0,
                            min(40.0, float(msg.get("width", 4))),
                        ),
                        "tool": (
                            "eraser"
                            if msg.get("tool") == "eraser"
                            else "brush"
                        ),
                    }

                    # Retain drawing operations for reconnect snapshots.
                    live.operations.append(operation)
                    if len(live.operations) > 5000:
                        live.operations = live.operations[-5000:]

                    await live.broadcast(
                        "stroke",
                        {
                            "player_id": player_id,
                            "operation": operation,
                        },
                        exclude=pid,
                    )

                except (KeyError, ValueError, TypeError):
                    await live.send(
                        pid,
                        "error",
                        {"message": "Invalid drawing operation."},
                    )

            elif kind == "clear_canvas":
                if live.active and pid == live.drawer_id:
                    live.operations.clear()
                    await live.broadcast(
                        "canvas_cleared",
                        {"player_id": player_id},
                    )
                else:
                    await live.send(
                        pid,
                        "error",
                        {
                            "message": (
                                "Only the drawer can clear the canvas."
                            )
                        },
                    )

            elif kind == "guess":
                if not live.active or pid == live.drawer_id:
                    await live.send(
                        pid,
                        "guess_result",
                        {
                            "correct": False,
                            "message": "You cannot guess right now.",
                        },
                    )
                    continue

                guess_text = str(msg.get("text", ""))[:120].strip()
                if not guess_text:
                    await live.send(
                        pid,
                        "guess_result",
                        {
                            "correct": False,
                            "message": "Enter a guess first.",
                        },
                    )
                    continue

                correct = bool(
                    live.word
                    and guess_text.casefold() == live.word.casefold()
                )

                db = SessionLocal()
                round_record = None

                try:
                    room = db.query(GameRoom).filter_by(
                        room_code=code
                    ).first()

                    if room:
                        round_record = (
                            db.query(GameRound)
                            .filter_by(
                                room_id=room.id,
                                round_number=live.round_index,
                            )
                            .first()
                        )

                    if round_record:
                        db.add(
                            Guess(
                                round_id=round_record.id,
                                player_id=player_id,
                                guess_text=guess_text,
                                is_correct=correct,
                            )
                        )
                        db.commit()

                    round_id = (
                        round_record.id if round_record else None
                    )

                finally:
                    db.close()

                if correct:
                    if pid in live.solved:
                        await live.send(
                            pid,
                            "guess_result",
                            {
                                "correct": True,
                                "message": (
                                    "You already scored this round."
                                ),
                            },
                        )
                        continue

                    live.solved.add(pid)

                    points = score_for_guess(
                        int(live.deadline - time.monotonic()),
                        live.round_index,
                    )
                    live.scores[pid] = (
                        live.scores.get(pid, 0) + points
                    )

                    await live.broadcast(
                        "correct_guess",
                        {
                            "player_id": player_id,
                            "display_name": live.names.get(
                                pid, "Player"
                            ),
                            "points": points,
                        },
                    )
                    await live.broadcast(
                        "scoreboard",
                        {"scores": live.scores},
                    )
                    await live.send(
                        pid,
                        "guess_result",
                        {
                            "correct": True,
                            "message": f"Correct! +{points} points.",
                        },
                    )

                    connected_guessers = (
                        set(live.sockets) - {live.drawer_id}
                    )
                    if (
                        connected_guessers
                        and connected_guessers.issubset(live.solved)
                    ):
                        if live.task:
                            live.task.cancel()

                        asyncio.create_task(
                            live.end_round(round_id, "all_guessed")
                        )

                else:
                    await live.send(
                        pid,
                        "guess_result",
                        {
                            "correct": False,
                            "message": "Not quite—try again!",
                        },
                    )

            elif kind == "leave":
                break

            else:
                await live.send(
                    pid,
                    "error",
                    {"message": "Unknown event type."},
                )

    except WebSocketDisconnect:
        logger.info(
            "WebSocket disconnected: room=%s player_id=%s",
            code,
            player_id,
        )

    except Exception:
        logger.exception(
            "WebSocket error: room=%s player_id=%s",
            code,
            player_id,
        )
        try:
            if live.sockets.get(pid) is ws:
                await live.send(
                    pid,
                    "error",
                    {"message": "An internal server error occurred."},
                )
        except Exception:
            pass

    finally:
        # An old connection must never remove a newer socket.
        if live.sockets.get(pid) is ws:
            live.sockets.pop(pid, None)
            live.ready.discard(pid)

            db = SessionLocal()
            try:
                player = db.query(Player).filter_by(
                    id=player_id
                ).first()
                if player:
                    player.left_at = now()
                    db.commit()
            finally:
                db.close()

            await live.broadcast(
                "player_left",
                {
                    "player_id": player_id,
                    "display_name": live.names.get(pid, "Player"),
                },
            )
            await live.lobby_update()

            if live.active and pid == live.drawer_id:
                if live.task:
                    live.task.cancel()

                live.active = False
                await live.broadcast(
                    "round_ended",
                    {
                        "reason": "drawer_disconnected",
                        "word": live.word,
                        "scores": live.scores,
                    },
                )
                live.active = True
                asyncio.create_task(live.next_round())

            elif live.active and len(live.sockets) < 2:
                if live.task:
                    live.task.cancel()

                live.active = False
                await live.finish()
