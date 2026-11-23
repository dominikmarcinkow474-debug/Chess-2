from contextlib import asynccontextmanager
from datetime import datetime, timezone
from io import StringIO
import chess
import chess.pgn
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.chess_service import ChessEngineError, board_status, make_analysis, parse_board
from app.config import settings
from app.database import Base, engine, get_db
from app.models import Game, User
from app.schemas import AnalysisOut, GameCreate, GameOut, MoveIn, TokenOut, UserCreate, UserOut
from app.security import create_access_token, hash_password, verify_password

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="JWT-secured gaming companion API with Stockfish-powered chess move analysis.",
    lifespan=lifespan,
)
origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware, allow_origins=origins, allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"], allow_headers=["Authorization", "Content-Type"],
)

@app.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name}

@app.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    db.refresh(user)
    return user

@app.post("/auth/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    email = form.username.lower()
    user = db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    token, expires_in = create_access_token(str(user.id))
    return {"access_token": token, "token_type": "bearer", "expires_in": expires_in}

@app.get("/users/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user

@app.post("/games", response_model=GameOut, status_code=status.HTTP_201_CREATED)
def create_game(payload: GameCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        board = parse_board(payload.fen)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    game = Game(owner_id=user.id, fen=board.fen(), pgn="", status="active")
    db.add(game)
    db.commit()
    db.refresh(game)
    return game

@app.get("/games", response_model=list[GameOut])
def list_games(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return list(db.scalars(select(Game).where(Game.owner_id == user.id).order_by(Game.updated_at.desc())))

@app.get("/games/{game_id}", response_model=GameOut)
def get_game(game_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _owned_game(game_id, user, db)

@app.delete("/games/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_game(game_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    game = _owned_game(game_id, user, db)
    db.delete(game)
    db.commit()

@app.post("/games/{game_id}/moves", response_model=AnalysisOut)
def play_move(game_id: int, payload: MoveIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    game = _owned_game(game_id, user, db)
    try:
        board = parse_board(game.fen)
    except ValueError:
        raise HTTPException(status_code=409, detail="Stored game position is invalid")
    if board.is_game_over(claim_draw=True):
        raise HTTPException(status_code=409, detail="This game is already over")
    try:
        move = chess.Move.from_uci(payload.uci)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UCI move format; use e.g. e2e4")
    if move not in board.legal_moves:
        raise HTTPException(status_code=422, detail="Illegal move for the current position")
    san = board.san(move)
    board.push(move)
    status_value, result = board_status(board)

    # Persist the move before analysis so the submitted move is not lost if Stockfish is down.
    game.fen = board.fen()
    game.status = status_value
    game.updated_at = datetime.now(timezone.utc)
    game.pgn = _append_pgn(game.pgn, san)
    db.commit()
    try:
        return make_analysis(board, game.id, san, payload.depth or settings.stockfish_depth)
    except ChessEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

def _owned_game(game_id: int, user: User, db: Session) -> Game:
    game = db.scalar(select(Game).where(Game.id == game_id, Game.owner_id == user.id))
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return game

def _append_pgn(pgn_text: str, san: str) -> str:
    # Store a human-readable SAN sequence. The authoritative position is always FEN.
    moves = pgn_text.split() if pgn_text else []
    move_number = len(moves) // 2 + 1
    if len(moves) % 2 == 0:
        moves.append(f"{move_number}.")
    moves.append(san)
    return " ".join(moves)

@app.get("/")
def root():
    return {"message": "CART3R Chess Companion API", "docs": "/docs", "health": "/health"}
