from . import action_log, lair


def log_entry_tgt_pieces_to_text(entry: action_log.LogEntry) -> str:
    return lair.stringify_pieces((tgt, cnt) for _, tgt, cnt in entry.pieces())


def log_entry_src_pieces_to_text(entry: action_log.LogEntry) -> str:
    return lair.stringify_pieces((src, cnt) for src, _, cnt in entry.pieces())


def log_entry_to_text(entry: action_log.LogEntry) -> str:
    match entry.action:
        case action_log.Action.COMMENT:
            assert entry.text
            return entry.text
        case action_log.Action.GATHER:
            intermediate = "".join(
                f" to {land}" for land in (entry.intermediate_lands or [])
            )
            return f"gather {log_entry_src_pieces_to_text(entry)} from {entry.src_land}{intermediate} to {entry.tgt_land} (total {entry.total_count()})"
        case action_log.Action.ADD:
            return f"add {log_entry_tgt_pieces_to_text(entry)} in {entry.tgt_land} (total {entry.total_count()})"
        case action_log.Action.DESTROY:
            if entry.tgt_piece:
                response_log = f", MR adds {log_entry_tgt_pieces_to_text(entry)} in {entry.tgt_land}"
            else:
                response_log = ""
            return f"destroy {log_entry_src_pieces_to_text(entry)} in {entry.src_land}{response_log}"
        case action_log.Action.DOWNGRADE:
            return f"downgrade {log_entry_src_pieces_to_text(entry)} in {entry.src_land} (total {entry.total_count()})"
        case action_log.Action.MANUAL:
            if entry.tgt_land and any(entry.tgt_piece):
                tgt = f" +({log_entry_tgt_pieces_to_text(entry)}) in {entry.tgt_land}"
            else:
                tgt = ""
            if entry.src_land and any(entry.src_piece):
                src = f" -({log_entry_src_pieces_to_text(entry)}) in {entry.src_land}"
            else:
                src = ""
            if entry.text:
                text = " " + entry.text.split(" - ")[-1]
            else:
                text = ""
            return f"manual action:{text}{src}{tgt}"
    raise LookupError(entry.action)


def digest_log(log: action_log.Actionlog, filter: str = "") -> str:
    return "\n".join(
        " " * (nest * 2) + "- " + line
        for nest, entry in log.entries
        for line in (log_entry_to_text(entry),)
        if line
        if (nest == 0) or (filter in line)
    )
