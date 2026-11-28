"""A small reference library of worked patterns for combining programs and libraries into one script. Not
lore, not a description of a capability of her own -- concrete code she can lean on when asked to WRITE a
program that uses more than one external tool together, which a local 8B model otherwise tends to fumble
(forgetting error checks, shelling out through a string instead of a list, not checking a program exists
first, piping wrong). Kept short on purpose: a handful of patterns that actually get reused, not a textbook,
since every line here eats into a small model's context."""

HOW = ("\nWHEN YOU WRITE A PROGRAM THAT USES OTHER PROGRAMS TOGETHER, lean on these patterns instead of "
       "guessing syntax. They're plain Python; adjust names and arguments, keep the shape.\n\n"
       "Run one external program and use its output:\n"
       "    import subprocess\n"
       "    r = subprocess.run([\"some_program\", \"--flag\", \"value\"], capture_output=True, text=True)\n"
       "    if r.returncode != 0:\n"
       "        raise RuntimeError(f\"some_program failed: {r.stderr.strip()}\")\n"
       "    output = r.stdout\n\n"
       "Chain two programs like a shell pipe (`a | b`), without building a shell string:\n"
       "    p1 = subprocess.Popen([\"first_program\"], stdout=subprocess.PIPE)\n"
       "    p2 = subprocess.Popen([\"second_program\"], stdin=p1.stdout, stdout=subprocess.PIPE, text=True)\n"
       "    p1.stdout.close()                        # let p1 see a closed pipe if p2 exits early\n"
       "    out, _ = p2.communicate()\n\n"
       "Run several programs in order and stop cleanly the moment one fails:\n"
       "    steps = [[\"first\", \"arg\"], [\"second\", \"arg\"]]\n"
       "    for cmd in steps:\n"
       "        r = subprocess.run(cmd, capture_output=True, text=True)\n"
       "        if r.returncode != 0:\n"
       "            print(f\"{cmd[0]} failed: {r.stderr.strip()}\")\n"
       "            break\n\n"
       "Check a program is even installed before calling it:\n"
       "    import shutil\n"
       "    if shutil.which(\"ffmpeg\") is None:\n"
       "        print(\"ffmpeg isn't installed\")\n\n"
       "Hand a program data you computed in Python, instead of shelling out to echo and a pipe:\n"
       "    r = subprocess.run([\"some_program\"], input=my_text, text=True, capture_output=True)\n\n"
       "Rules that matter more than the exact syntax: pass commands as a LIST of arguments (never one string "
       "with spaces in it -- that invites quoting bugs and, with shell=True, injection); always check "
       "returncode or catch the error before trusting a step worked; only combine `shell=True` with a single "
       "literal command you wrote yourself, never with anything built from a variable; close a Popen's stdout "
       "you piped from, same as above, so a blocked process doesn't hang the script.")
