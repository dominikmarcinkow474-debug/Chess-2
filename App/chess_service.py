import shutil
import chess
import chess.engine
import chess.pgn
from io import StringIO
from app.config import settings

class ChessEngineError(RuntimeError):
    pass

def get_engine():
    path = shutil.which(settings.stockfish_path) or settings.stockfish_path
    try:
        return chess.engine.SimpleEngine.popen_uci(path)
    except (FileNotFoundError, OSError) as exc:
        raise ChessEngineError(
            "Stockfish was not found. Install Stockfish and set STOCKFISH_PATH in .env."
        ) from exc

def parse_board(fen: str | None) -> chess.Board:
    if not fen:
        return chess.Board()
    try:
        return chess.Board(fen)
    except ValueError as exc:
        raise ValueError("Invalid FEN position") from exc

def board_status(board: chess.Board) -> tuple[str, str | None]:
    if not board.is_game_over(claim_draw=True):
        return "active", None
    result = board.result(claim_draw=True)
    return "finished", result

def make_analysis(board_after_user: chess.Board, game_id: int, played_move: str, depth: int):
    """Suggest the opponent's best reply, then the user's best response to that reply."""
    if board_after_user.is_game_over(claim_draw=True):
        status, result = board_status(board_after_user)
        return {
            "game_id": game_id, "played_move": played_move,
            "fen_after_user_move": board_after_user.fen(),
            "opponent_best_move_uci": None, "opponent_best_move_san": None,
            "predicted_fen_after_opponent": None,
            "your_recommended_move_uci": None, "your_recommended_move_san": None,
            "evaluation": "Game over", "depth": depth, "game_over": True, "result": result,
        }

    engine = get_engine()
    try:
        # Analyse from the opponent's side to move. The best move is the strongest reply
        # found at the selected depth, not a guarantee of a forced win or perfect play.
        opponent_info = engine.analyse(board_after_user, chess.engine.Limit(depth=depth))
        opponent_move = opponent_info["pv"][0]
        opponent_san = board_after_user.san(opponent_move)
        after_opponent = board_after_user.copy()
        after_opponent.push(opponent_move)

        if after_opponent.is_game_over(claim_draw=True):
            evaluation = _format_score(opponent_info["score"].pov(board_after_user.turn))
            _, result = board_status(after_opponent)
            return {
                "game_id": game_id, "played_move": played_move,
                "fen_after_user_move": board_after_user.fen(),
                "opponent_best_move_uci": opponent_move.uci(),
                "opponent_best_move_san": opponent_san,
                "predicted_fen_after_opponent": after_opponent.fen(),
                "your_recommended_move_uci": None, "your_recommended_move_san": None,
                "evaluation": evaluation, "depth": depth, "game_over": True, "result": result,
            }

        # At this point it's the user's turn. Analyse a recommended follow-up.
        user_info = engine.analyse(after_opponent, chess.engine.Limit(depth=depth))
        user_move = user_info["pv"][0]
        user_san = after_opponent.san(user_move)
        evaluation = _format_score(user_info["score"].pov(after_opponent.turn))
        return {
            "game_id": game_id, "played_move": played_move,
            "fen_after_user_move": board_after_user.fen(),
            "opponent_best_move_uci": opponent_move.uci(),
            "opponent_best_move_san": opponent_san,
            "predicted_fen_after_opponent": after_opponent.fen(),
            "your_recommended_move_uci": user_move.uci(),
            "your_recommended_move_san": user_san,
            "evaluation": evaluation, "depth": depth,
            "game_over": False, "result": None,
        }
    finally:
        engine.quit()

def _format_score(score) -> str:
    if score.is_mate():
        return f"Mate in {score.mate()} (from analysed side's perspective)"
    return f"{score.score() / 100:+.2f} pawns (from analysed side's perspective)"

def append_move_to_pgn(pgn_text: str, move: chess.Move, board_before: chess.Board) -> str:
    """Maintain a compact PGN move list from the initial position."""
    if pgn_text:
        try:
            game = chess.pgn.read_game(StringIO(pgn_text))
            if game is not None:
                board = game.board()
                for existing in game.mainline_moves():
                    board.push(existing)
                san = board.san(move)
                board.push(move)
                node = game.end()
                node.parent.add_variation(move)
                out = StringIO()
                print(game, file=out, end="\n\n")
                out.write(" ".join(board.move_stack and [] or []))
                return out.getvalue().strip()
        except Exception:
            pass
    # For a non-standard FEN, the FEN is stored on the game; pgn text is still useful
    # for the moves made in this session. A canonical PGN is assembled in the API route.
    return pgn_text
