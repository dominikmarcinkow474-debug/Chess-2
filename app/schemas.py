from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

class UserOut(BaseModel):
    id: int
    email: EmailStr
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class GameCreate(BaseModel):
    fen: str | None = None

class GameOut(BaseModel):
    id: int
    fen: str
    pgn: str
    status: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class MoveIn(BaseModel):
    uci: str = Field(min_length=4, max_length=5, examples=["e2e4"])
    depth: int | None = Field(default=None, ge=1, le=25)

class AnalysisOut(BaseModel):
    game_id: int
    played_move: str
    fen_after_user_move: str
    opponent_best_move_uci: str | None
    opponent_best_move_san: str | None
    predicted_fen_after_opponent: str | None
    your_recommended_move_uci: str | None
    your_recommended_move_san: str | None
    evaluation: str
    depth: int
    game_over: bool
    result: str | None
