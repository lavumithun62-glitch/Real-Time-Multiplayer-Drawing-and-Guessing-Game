from pydantic import BaseModel, Field, field_validator

class CreateRoom(BaseModel):
    display_name: str = Field(min_length=1, max_length=40)
    total_rounds: int = Field(default=3, ge=1, le=10)

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Display name cannot be blank")
        return value

class JoinRoom(BaseModel):
    display_name: str = Field(min_length=1, max_length=40)

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Display name cannot be blank")
        return value

class PlayerOut(BaseModel):
    id: int
    display_name: str
    score: int
    ready: bool = False
    connected: bool = False

class RoomOut(BaseModel):
    room_code: str
    status: str
    current_round: int
    total_rounds: int
    players: list[PlayerOut]
