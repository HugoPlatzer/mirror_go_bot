import sys

def gtp_read_command():
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


def init_game_state():
    return {"board_size": 9}


def gtp_handle_name(game_state, args):
    return "MirrorGoBot", True


def gtp_handle_version(game_state, args):
    return "1.0", True


def gtp_handle_protocol_version(game_state, args):
    return "2", True


def main():
    command_handlers = {
        "quit": None,
        "list_commands": None,
        "name": gtp_handle_name,
        "version": gtp_handle_version,
        "protocol_version": gtp_handle_protocol_version
    }
    game_state = init_game_state()
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



if __name__ == "__main__":
    main()
