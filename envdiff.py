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
  changed_keys = {x for x in (start_keys & sourced_keys) if start_env[x] != sourced_env[x]}

  # Firstly, added keys
  for key in sourced_keys - start_keys:
    print("export {}={}".format(key, sourced_env[key]))

  # Potentially, removed keys (though probably rare)
  for key in start_keys - sourced_keys:
    print("unset  {}")

  # Now, changed keys
  for key in changed_keys:
    start = start_env[key]
    end = sourced_env[key]

    # Let's try to embed one in the other
    if start in end:
      # Simple case of e.g. adding 
      sindex = end.index(start)
      interpose = end[:sindex] + "$" + key + end[sindex+len(start):]
      print("export {}={}".format(key, interpose))
    elif end in start:
      # We might have had entries removed
      raise NotImplementedError("No code to handle removal of entries from path")
    else:
      # Just set the whole variable for now, might be more complicated though
      print("export {}={} # Complex change. Potentially incorrect...".format(key, end))
    
if __name__ == "__main__":
  main()
