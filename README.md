# Spirit Island 144p helper

This project aims to assist players of the Spirit Island 144p game in their grand in-game projects that require some number crunching to pull off optimally.

## LRLR optimization

The Lair-Lair (LRLR) is able to gather and damage hundreds of invaders and affect doznes of lands every turn. `lrlr/main.py` calculates turns for LRLR in a (somewhat) optimal manner, to ease the burden on players from manually finding optimal lines.

LRLR optimization takes its input in the form of four files:
- `config/turnX/initial_lair.json5` - initial number of invaders in the Lair.
- `config/turnX/start.csv` - initial state of lands surrounding the Lair including its many Weaved-into locations.
- `config/turnX/actions.csv` - non-Lair actions that happen during the turn.
  - Most actions here are executed before Lair begins its own action sequence, and mostly affect initial state.
  - Actions here _may_ have dependencies on Lair-related actions, and be executed after the Lair has reached some point in its execution. This can be achieved by setting a value in the `After Toplevel` column.
- `config/turnX/input.json5` - additional configuration options to control what we want the Lair to do this turn. Options include:
  - `actions`: Array of actions that are available to Lair on top of the Lair innates themselves (which don't need to be specified). An action that is available multiple times should be specified multiple times.
  - `terrain_priority`: terrain priority to clear first when considering how to distribute Lair actions. It's recommended to set ravaging terrains first, then building terrains.
  - `ignore_lands`: Array of lands to be ignored by Lair actions. These lands will not be gathered from, and gathering into an ignored land will cause an additional gather to bypass it.
  - `leave_behind`: Object representing lands in which some pieces should be left behind by lair actions. Each key in this object should be a land key, and the value should be an object with optional keys `explorer`/`town`/`city`/`dahan` and integer values representing how many invaders should be left behind. Note that setting a range-1 land here currently may lead to illegal ravage results when there's excess damage.
  - `blue_lair`/`orange_lair`: Configuration for each Lair's innate. An Object with the following keys:
    - `reserve_gathers`: Amount of gathers to be manually reserved from the innate's third threshold. This many gathers will not be performed, allowing players to instead gather through Finder adjacency for other purposes.
    - `max_range`: Maximum range to perform gathers. Matches the Lair's Air element.
- `config/turnX/weaves.json5` - list of weaved lands, each in the form `"land,land"`, e.g. `"🍪S4,😎R4"`.

The LRLR optimization tool can be run like
```
python3 -m lrlr.main --output log
```

The possible output types are:
- `log`: Output the Lair's full action sequence in detail to be used as the Lair's turn submission.
- `diff`: Output the initial and final state of surrounding lands that were changed by the Lair's actions.
- `cat-cafe`: Output a CSV format that is compatible with the [Cat Cafe Chain of Custody](https://docs.google.com/spreadsheets/d/1x9654XIyF7MKBAcl5Itv4OQ9JLdwQlXY1-Y3E6svHwY) document, to update it with the turn's events.
- `actions.csv`: Output the Lair's full action sequence in CSV format compatible with `config/turnX/actions.csv` files.

Additional useful arguments include:
- `--split $DIRECTORY`: Split log/diff output into files of the correct size to be sent as discord messages. Those files will use server emojis from the _Spirit Island - Second Wave_ discord server.
- `--split-header $HEADER` - append a string to the first line of each discord message. This is useful to indicate the finality state of the turn by appending one of ❌, ☑️, or ✅.
- `--filter $EMOJI`: Filter log/diff output to only show information relevant to a specific islet, chosen by its emoji (e.g. `--filter 🍪`).
- `--diff-sort-range`: Sort diff output by range rather than by islet.
- `--diff-all`: Show for all lands in diff output even when they're unchanged.

For a full list of commandline arguments, run
```
python3 -m lrlr.main --help
```

### Missing Start Data

Run
```
python3 -m lrlr.missing_start_data --turn T --range R
```
to get a list of all lands in range `R` that are missing data in `config/turn{T}/start.csv`. This is useful during data collection for a for a specific turn.
