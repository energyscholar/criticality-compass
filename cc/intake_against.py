"""intake_against - the cross-check (plan 1165 section 5; role intake_against, its own cap tests/test_budget.py AGAINST_CAP, split from
cc/intake_profile.py by plan 1165 D5): a declaration against the PROFILE of the files it names, by `bin/cc intake profile <id> --check`
and by S3. Invariants: it reads no data byte (PROFILE.json, the declaration, CONVERSION.toml are plain values); a contradiction is a row
of Contradiction; every live S4 / S4 reader / S5 reason is in PREDICTS or NOT_PREDICTABLE (tests/test_intake_profile.py)."""
import enum

Contradiction = enum.Enum("Contradiction", "FILE_NOT_PROFILED ENCODING_CONTRADICTS_PROFILE DELIMITER_CONTRADICTS_PROFILE HEADER_CONTRADICTS_PROFILE "
                          "COLUMN_CONTRADICTS_PROFILE CELLS_CONTRADICT_PROFILE WIDTH_CONTRADICTS_PROFILE ORDER_CONTRADICTS_PROFILE "
                          "REPEATS_CONTRADICT_PROFILE SHEET_CONTRADICTS_PROFILE FILES_CONTRADICT_PROFILE")
R = Contradiction
PREDICTS = {   # plan 1165 section 5: a live S4 / S4 reader / S5 reason a byte-level fact can raise -> the Contradiction that precedes it (test)
    "NOT_UTF8": R.ENCODING_CONTRADICTS_PROFILE, "ROW_WIDTH_DIFFERS": R.WIDTH_CONTRADICTS_PROFILE, "COLUMN_NAME_ABSENT": R.COLUMN_CONTRADICTS_PROFILE,
    "COLUMN_NAME_AMBIGUOUS": R.COLUMN_CONTRADICTS_PROFILE, "COLUMN_POSITION_OUT_OF_RANGE": R.COLUMN_CONTRADICTS_PROFILE,
    "CELL_NOT_A_NUMBER": R.CELLS_CONTRADICT_PROFILE, "HEADER_LINE_ABSENT": R.HEADER_CONTRADICTS_PROFILE, "NO_DATA_ROW": R.HEADER_CONTRADICTS_PROFILE,
    "SHEET_ABSENT": R.SHEET_CONTRADICTS_PROFILE, "COLUMNS_DIFFER": R.FILES_CONTRADICT_PROFILE, "ROW_ORDER_DIFFERS": R.ORDER_CONTRADICTS_PROFILE,
    "FILE_DIFFERS_FROM_FIRST": R.FILES_CONTRADICT_PROFILE, "FAST_VALUE_REPEATED": R.REPEATS_CONTRADICT_PROFILE, "ACQUISITION_ORDER_DIFFERS": R.ORDER_CONTRADICTS_PROFILE,
}
NOT_PREDICTABLE = {   # plan 1165 section 5: the live reasons no profile can precede, each with why (test: PREDICTS + this = every live S4, S5 reason)
    "CURVE_REPEATED": "a slow value's recurrence is a value fact, and the profile holds no value",
    "SLOW_KEY_UNRESOLVED": "a FILE_KEY slow value is a header cell's value, which the profile masks",
    "REPLICATE_KEY_UNRESOLVED": "a replicate key is a value of a file name field or a column, which the profile does not hold",
    "UNIT_DIFFERS": "a unit is compared as declared text; the profile masks every numeral in it",
    "NOT_AN_XLSX": "openpyxl's parse of the cells, not a structure the profile states",
    "XLSX_READER_ABSENT": "a fact of the machine that runs the reader, not of the files",
    "READER_NOT_LIVE": "a fact of the declaration's reader name, not of the files",
    "READER_REFUSED": "the wrapper of a reader reason; each reader reason has its own row",
}
