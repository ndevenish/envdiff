#!/usr/bin/env python
# coding: utf-8

"""
Works out the environmental changes from sourcing a script.

Usage:
  source_diff.py <script> [<arg> [<arg> ...]]
  source_diff.py -h | --help
"""

from __future__ import print_function

import os
import sys
import subprocess
import re

# Look for :, but not ://
re_list_splitter = re.compile(r":(?!\/\/)")
# The comment prefix to use for output
COMMENT_PREFIX = "#"

def is_bash_listlike(entry):
  "Does this string look like a bash list?"
  return re_list_splitter.search(entry) is not None

def index_of_sublist(a, b):
  "Returns the index of b in a, or None"
  if len(a) < len(b):
    return None
  for i in range(len(a)-len(b)+1):
    if a[i:i+len(b)] == b:
      return i
  return None

def contains_sublist(a, b):
  "Tests if list a contains sequence b"
  return index_of_sublist(a,b) is not None

class OutputCategories(object):
  def __init__(self):
    self.added = []
    self.replaced = []
    self.removed = []
    self.listchange = []
    self.assumed_listchange = []
    self.unhandled = []

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

  output = OutputCategories()

  # Look for added keys that are listlike - pretend these are changes
  for changelike in [x for x in added_keys if is_bash_listlike(sourced_env[x])]:
    # print("({} is changelike but added - treating as list)".format(changelike))
    changed_keys |= {changelike}
    added_keys = added_keys - {changelike}

  # Keys that changed, but are not listlike, are treated separately
  replaced_keys = set()
  for key in list(changed_keys):
    if not (is_bash_listlike(start_env.get(key, "")) or is_bash_listlike(sourced_env[key])):
      # print("({} changed but not in a listlike way, overwriting)".format(key))
      changed_keys = changed_keys - {key}
      replaced_keys |= {key}

  # Removed keys are the easy case: Must have been unset
  for key in start_keys - sourced_keys:
    output.removed.append("unset  {}")

  # Firstly, added/replaced keys
  for key in added_keys | replaced_keys:
    # Choose where it goes
    dest = output.added if key in added_keys else output.replaced
    dest.append("export {}={}".format(key, sourced_env[key]))

  # Now, changed keys, but we know they are lists or look like one
  for key in changed_keys:
    # Treat an empty start as an explicitly empty list
    if start_env.get(key):
      start = re_list_splitter.split(start_env.get(key, ""))
    else:
      start = []
    end = re_list_splitter.split(sourced_env[key])

    # If we don't have a start, assume that we added as a prefix
    if not start:
      output.assumed_listchange.append("export {}={}".format(key, ":".join(end + ["$"+key])))
    else:
      # Look for the start embedded in the end
      if not contains_sublist(end, start):
        output.unhandled.append("export {}={} # complex list handling?".format(key, sourced_env[key]))
        # We don't have the original list embedded in the end list...
        # raise NotImplementedError("Not yet handling lists with removed items")

      ind = index_of_sublist(end, start)

      prefix = end[:ind]
      suffix = end[ind+len(start):]
      new_list = prefix + ["$"+key] + suffix
      output.listchange.append("export {}={}".format(key, ":".join(new_list)))

  # Do the actual output, grouped, with information
  if output.added:
    print(COMMENT_PREFIX + " Variables added")
    print("\n".join(output.added))
    print()
  if output.replaced:
    print(COMMENT_PREFIX + " Variables replaced - these had a value before that changed")
    print("\n".join(output.replaced))
    print()
  if output.removed:
    print(COMMENT_PREFIX + " Variables deleted/unset")
    print("\n".join(output.removed))
    print()
  if output.listchange:
    print(COMMENT_PREFIX + " Lists prefixed/appended to")
    print("\n".join(output.listchange))
    print()
  if output.assumed_listchange:
    print(COMMENT_PREFIX + " Variables created - but looked like a list; assuming prefix operation")
    print("\n".join(output.assumed_listchange))
    print()
  if output.unhandled:
    print(COMMENT_PREFIX + " WARNING: The following were unhandled/unknown/too complex")
    print("\n".join(x + "#" for x in output.unhandled))
    print()

if __name__ == "__main__":
  main()
