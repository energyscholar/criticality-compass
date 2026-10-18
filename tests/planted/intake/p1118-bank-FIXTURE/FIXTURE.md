# FIXTURE: a stand-in for the planted S1 bank of plan 1118 (plan 1136, amendment A2 ruling Q7)

Every file under S1/ is EMPTY. The names are the bank's: 61 curve files S1_c000.npz to S1_c060.npz, MANIFEST.json and truth.json. No value
of the bank is here, and no file here was copied from it. `bin/cc intake seal dial1118-s1 --universe <this directory>` seals the worked
example against these names and sizes (all 0), so SEAL.json records `location_name = "p1118-bank-FIXTURE"`: a seal against the real bank
names its own directory. A data stage run against this fixture would read empty files; every data stage is a STUB in plan 1136.
