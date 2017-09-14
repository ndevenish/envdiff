#!/usr/bin/env python
# coding: utf-8

"""
Works out the environmental changes from sourcing a script.

Usage:
  source_diff.py <script> [<arg> [<arg> ...]]
  source_diff.py -h | --help
"""

import os
import sys
import subprocess
import re

# Look for :, but not ://
re_list_splitter = re.compile(r":(?!\/\/)")

def is_bash_listlike(entry):
  "Does this string look like a bash list?"
  return re_list_splitter.search(entry) is not None

def sublist_index(a, b):
  "Returns the index of b in a, or None"
  if len(a) < len(b):
    return None
  for i in range(len(a)-len(b)+1):
    if a[i:i+len(b)] == b:
      return i
  return None

def contains_sublist(a, b):
  "Tests if list a contains sequence b"
  return sublist_index(a,b) is not None

def main():
  # Handle arguments and help
  if "-h" in sys.argv or "--help" in sys.argv or len(sys.argv) == 1:
    print(__doc__.strip())
    # Exit with 0 if help requested, otherwise an error
    sys.exit(1 if len(sys.argv) == 1 else 0)

  script = " ".join([sys.argv[1]] + [" ".join(sys.argv[2:])])
  shell_command = ". {} 2>&1 > /dev/null; python -c 'import os; print(repr(os.environ))'".format(script)

  start_env = dict(os.environ)
  env_output = subprocess.check_output(shell_command, shell=True)
  sourced_env = eval(env_output)

  # Keys to ignore
  IGNORE = {"SHLVL", "_"}
  for key in IGNORE:
    if key in sourced_env:
      del sourced_env[key]
    if key in start_env:
      del start_env[key]

  # Now, go through and find the differences in these two environments
  start_keys = set(start_env.keys())
  sourced_keys = set(sourced_env.keys())

  added_keys = sourced_keys - start_keys
  changed_keys = {x for x in (start_keys & sourced_keys) if start_env[x] != sourced_env[x]}

  # Look for added keys that are listlike - pretend these are changes
  for changelike in [x for x in added_keys if is_bash_listlike(sourced_env[x])]:
    print("({} is changelike but added - treating as list)".format(changelike))
    changed_keys |= {changelike}
    added_keys = added_keys - {changelike}

  # Keys that changed, but are not listlike, are treated like adds - replacing
  for key in list(changed_keys):
    if not (is_bash_listlike(start_env.get(key, "")) or is_bash_listlike(sourced_env[key])):
      print("({} changed but not in a listlike way, overwriting)".format(key))
      changed_keys = changed_keys - {key}
      added_keys |= {key}

  # Removed keys are the easy case: Must have been unset
  for key in start_keys - sourced_keys:
    print("unset  {}")

  # Firstly, added keys
  for key in added_keys:
    print("export {}={}".format(key, sourced_env[key]))

  # Now, changed keys, but we know they are lists or look like one
  for key in changed_keys:
    start = re_list_splitter.split(start_env.get(key, ""))
    end = re_list_splitter.split(sourced_env[key])

    # assert is_bash_listlike(start) or is_bash_listlike(end), "Change but neither are listlike???"
    # Either we are listlike or not. 
    # if is_bash_listlike(start) or is_bash_listlike(end):
    # else:
      # Not listlike. Just replace.
      # print("export {}={}")

    # # Let's try to embed one in the other
    # if start in end:
    #   # Prefer to prefix to an existing, empty entry
    #   if start:
    #     sindex = end.index(start)
    #   else:
    #     sindex = len(end)

    #   interpose = end[:sindex] + "$" + key + end[sindex+len(start):]
    #   print("export {}={}".format(key, interpose))
    # elif end in start:
    #   # We might have had entries removed
    #   raise NotImplementedError("No code to handle removal of entries from path")
    # else:
    #   # Just set the whole variable for now, might be more complicated though
    #   print("export {}={} # Complex change. Potentially incorrect...".format(key, end))
    
if __name__ == "__main__":
  main()