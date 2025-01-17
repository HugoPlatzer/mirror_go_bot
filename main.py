import sys
import argparse
import subprocess
import re
import string


class KataCommandFailedException(Exception):
    pass


def init_state():
    return {"katago_handle": None, "cmdline_args": None}


def katago_launch(state):
    katago_binary = state["cmdline_args"].katago_binary
    katago_model = state["cmdline_args"].katago_model
    katago_config = state["cmdline_args"].katago_config
    args = [katago_binary,
            "gtp",
            "-model", katago_model,
            "-config", katago_config]
    katago_handle = subprocess.Popen(args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL)
    state["katago_handle"] = katago_handle


def katago_read_line(state):
    return (state["katago_handle"].stdout.readline()
            .decode("ascii").strip())


def katago_write_line(state, line):
    line_bytes = (line + "\n").encode("ascii")
    state["katago_handle"].stdin.write(line_bytes)
    state["katago_handle"].stdin.flush()


def katago_send_gtp_command(state, args):
    line = " ".join(args)
    katago_write_line(state, line)
    response_lines = []
    response_line = katago_read_line(state)
    while response_line != "":
        response_lines.append(response_line)
        response_line = katago_read_line(state)
    response = "\n".join(response_lines)
    assert len(response) >= 1 and response[0] in ["=", "?"]
    main_response = response[1:].strip()
    if response[0] == "=":
        return main_response
    else:
        raise KataCommandFailedException(main_response)


def katago_check_ready(state):
    response = katago_send_gtp_command(state, ["name"])
    assert response == "KataGo"


def katago_analyze(state):
    katago_write_line(state, "kata-analyze 100")
    first_line = katago_read_line(state)
    assert first_line == "="
    analysis_line = katago_read_line(state)
    assert analysis_line.startswith("info move")
    # abort search by sending empty line
    katago_write_line(state, "")
    # confirm end of search by waiting for empty line
    line = katago_read_line(state)
    while line != "":
        line = katago_read_line(state)
    # extract best move coords and score from analysis
    pattern = r"info move ([a-zA-Z0-9]+) .*?scoreLead ([\-.0-9]+)"
    match = re.match(pattern, analysis_line)
    best_move = match.group(1).lower()
    score = float(match.group(2))
    return best_move, score


def sgf_to_gtp_coord(boardsize, sgf_coord):
    assert len(sgf_coord) == 2
    assert sgf_coord[0] in string.ascii_lowercase
    assert sgf_coord[1] in string.ascii_lowercase
    col = sgf_coord[0]
    row = string.ascii_lowercase.index(sgf_coord[1])
    row = boardsize - row
    assert row in range(1, boardsize+1)
    assert col in string.ascii_lowercase[:boardsize]
    gtp_coord = f"{col}{row}"
    return gtp_coord


def coord_to_row_col_index(gtp_coord):
    col_index = string.ascii_lowercase.index(gtp_coord[0])
    row_index = int(gtp_coord[1:]) - 1
    return row_index, col_index


def row_col_index_to_coord(row_index, col_index):
    row_str = str(row_index + 1)
    col_str = string.ascii_lowercase[col_index]
    return f"{col_str}{row_str}"


def get_mirror_move_lastmove(boardsize, gtp_coord):
    row_index, col_index = coord_to_row_col_index(gtp_coord)
    mirror_row = boardsize - 1 - row_index
    mirror_col = boardsize - 1 - col_index
    mirror_coord = row_col_index_to_coord(mirror_row, mirror_col)
    return mirror_coord


def get_tengen_move(boardsize):
    tengen_row = (boardsize - 1) // 2
    return row_col_index_to_coord(tengen_row, tengen_row)


def get_mirror_move(state):
    sgf = katago_send_gtp_command(state, ["printsgf"])
    pattern = r"\(;.*?SZ\[([0-9]+)\].*?(?:;.*?[BW]\[([a-z]+)\])?\)"
    match = re.match(pattern, sgf)
    assert match is not None
    assert len(match.groups()) == 2
    boardsize = int(match.group(1))
    sgf_coord = match.group(2)
    if sgf_coord is not None:
        gtp_coord = sgf_to_gtp_coord(boardsize, sgf_coord)
        move = get_mirror_move_lastmove(boardsize, gtp_coord)
    else:
        move = get_tengen_move(boardsize)
    return move


def is_move_legal(state, player, gtp_coord):
    try:
        katago_send_gtp_command(state, ["play", player, gtp_coord])
    except KataCommandFailedException as e:
        return False
    katago_send_gtp_command(state, ["undo"])
    return True


def evaluate_move(state, player, gtp_coord):
    katago_send_gtp_command(state, ["play", player, gtp_coord])
    best_move, score = katago_analyze(state)
    katago_send_gtp_command(state, ["undo"])
    return score


def generate_move(state, player):
    best_move, best_score = katago_analyze(state)
    mirror_move = get_mirror_move(state)
    if not is_move_legal(state, player, mirror_move):
        return best_move
    mirror_score_opponent = evaluate_move(state, player, mirror_move)
    mirror_score = -mirror_score_opponent
    # print(best_move, best_score, mirror_move, mirror_score)
    mirror_threshold = state["cmdline_args"].mirror_threshold
    if best_score - mirror_score > mirror_threshold:
        return best_move
    else:
        return mirror_move


def gtp_read_command():
    command_str = input()
    while command_str.strip() == "":
        command_str = input()
        
    command_parts = command_str.split()
    command_name, command_args = command_parts[0], command_parts[1:]
    return command_name, command_args


def gtp_write_response(response_str, success=True):
    if success:
        print(f"= {response_str}")
    else:
        print(f"? {response_str}")
    print()
    sys.stdout.flush()


def gtp_handle_name(state, args):
    return "MirrorGoBot", True


def gtp_handle_version(state, args):
    return "1.0", True


def gtp_handle_protocol_version(state, args):
    return "2", True


def gtp_handle_clear_board(state, args):
    katago_send_gtp_command(state, ["clear_board"])
    return "", True


def gtp_handle_boardsize(state, args):
    katago_send_gtp_command(state, ["boardsize", *args])
    return "", True


def gtp_handle_komi(state, args):
    katago_send_gtp_command(state, ["komi", *args])
    return "", True


def gtp_handle_play(state, args):
    katago_send_gtp_command(state, ["play", *args])
    return "", True


def gtp_handle_genmove(state, args):
    assert len(args) == 1
    player = args[0].lower()
    assert player in ["b", "w"]
    move = generate_move(state, player)
    katago_send_gtp_command(state, ["play", player, move])
    return move, True


def gtp_loop(state):
    command_handlers = {
        "quit": None,
        "list_commands": None,
        "name": gtp_handle_name,
        "version": gtp_handle_version,
        "protocol_version": gtp_handle_protocol_version,
        "clear_board": gtp_handle_clear_board,
        "boardsize": gtp_handle_boardsize,
        "komi": gtp_handle_komi,
        "play": gtp_handle_play,
        "genmove": gtp_handle_genmove
    }
    while True:
        command_name, command_args = gtp_read_command()
        if command_name == "quit":
            gtp_write_response("", True)
            exit()
        elif command_name == "list_commands":
            response_str = "\n".join(command_handlers.keys())
            gtp_write_response(response_str, True)
        elif command_name in command_handlers:
            handler_fn = command_handlers[command_name]
            response_str, success = handler_fn(state, command_args)
            gtp_write_response(response_str, success)
        else:
            gtp_write_response("unknown command", False)


def main():
    state = init_state()
    parser = argparse.ArgumentParser()
    parser.add_argument("--katago-binary", required=True)
    parser.add_argument("--katago-model", required=True)
    parser.add_argument("--katago-config", required=True)
    parser.add_argument("--mirror-threshold", required=True,
            type=float)
    state["cmdline_args"] = parser.parse_args()
    katago_launch(state)
    katago_check_ready(state)
    gtp_loop(state)


if __name__ == "__main__":
    main()

