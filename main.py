import sys
import argparse
import subprocess
import re


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
    if response[0] != "=":
        raise Exception("katago command failed", args, response)
    response = response[1:].strip()
    return response


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
    best_move = match.group(1)
    score = float(match.group(2))
    return score, best_move


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


def gtp_loop(state):
    command_handlers = {
        "quit": None,
        "list_commands": None,
        "name": gtp_handle_name,
        "version": gtp_handle_version,
        "protocol_version": gtp_handle_protocol_version
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
            response_str, success = handler_fn(
                    game_state, command_args)
            gtp_write_response(response_str, success)
        else:
            gtp_write_response("unknown command", False)


def main():
    state = init_state()
    parser = argparse.ArgumentParser()
    parser.add_argument("--katago-binary", required=True)
    parser.add_argument("--katago-model", required=True)
    parser.add_argument("--katago-config", required=True)
    state["cmdline_args"] = parser.parse_args()
    katago_launch(state)
    katago_send_gtp_command(state, ["boardsize", "9"])
    result = katago_analyze(state)
    print(result)
    katago_send_gtp_command(state, ["boardsize", "13"])
    result = katago_analyze(state)
    print(result)
    #gtp_loop(state)


if __name__ == "__main__":
    main()
