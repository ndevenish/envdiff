#!/usr/bin/env python
# coding: utf-8

"""
Works out the environmental changes from sourcing a script.

Usage:
  source_diff.py [--bash | --modules] <script> [<arg> [<arg> ...]]
  source_diff.py -h | --help

Options:
  --bash        Generate bash scripting output. Default
  --modules     Generate GNU Modules Modulefile syntax output
  --warn-empty  Warn when replacing an empty variable (normally counts as added)
"""

# (WIP possible future feature)
# [-D <definition>]...
# -D <definition>  Add variables to the output. e.g. -DSOME_VAR=/some/path
#                  will add SOME_VAR to the output, and instances of /some/path
#                  in other variables will be replaced with SOME_VAR.


from __future__ import print_function

import os
import sys
import subprocess
import re
from abc import ABCMeta, abstractmethod

# Look for :, but not ://
re_list_splitter = re.compile(r":(?!\/\/)")

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
  """Holds raw output, grouped into category"""
  def __init__(self):
    self.added = []
    self.replaced = []
    self.removed = []
    self.listchange = []
    self.assumed_listchange = []
    self.unhandled = []

class OutputFormatter(object):
  __metaclass__ = ABCMeta

  def __init__(self, prior_definitions=None):
    self.definitions = prior_definitions
    self._output = OutputCategories()

  @abstractmethod
  def add(self, key, value):
    raise NotImplementedError()

  @abstractmethod
  def replace(self, key, value):
    "When a variable is replaced/written over completely"
    raise NotImplementedError()

  @abstractmethod
  def unhandled(self, key, value, comment=""):
    "When we don't know how to handle, just replace with a warning"
    raise NotImplementedError()

  @abstractmethod
  def remove(self, key):
    raise NotImplementedError()

  @abstractmethod
  def expand_list(self, key, prefix=[], postfix=[], assumed=True):
    """A list has been expanded by adding things in front or behind.

    :param assumed: This is an assumption. Used to annotate output.
    """
    raise NotImplementedError()

  @abstractmethod
  def dump(self):
    raise NotImplementedError()

class BashFormatter(OutputFormatter):
  def __init__(self, *args, **kwargs):
    super(BashFormatter, self).__init__(*args, **kwargs)

  def add(self, key, value):
    self._output.added.append("export {}={}".format(key, value))

  def replace(self, key, value):
    "When a variable is replaced/written over completely"
    self._output.replaced.append("export {}={}".format(key, value))

  def unhandled(self, key, value, comment=""):
    "When we don't know how to handle, just replace with a warning"
    out = "export {}={}".format(key, value)
    if comment:
      out += " # {}".format(comment)
    self._output.unhandled.append(out)

  def remove(self, key):
    self._output.removed.append("unset {}".format(key))

  def expand_list(self, key, prefix=[], postfix=[], assumed=False):
    dest_list = self._output.assumed_listchange if assumed else self._output.listchange
    dest_list.append("export {}={}".format(key, ":".join(prefix + ["$"+key] + postfix)))

  def dump(self):
    lines = []
      # Do the actual output, grouped, with information
    if self._output.added:
      lines.append("# Variables added")
      lines.append("\n".join(sorted(self._output.added)))
      lines.append("")
    if self._output.replaced:
      lines.append("# Variables replaced - these had a value before that changed")
      lines.append("\n".join(sorted(self._output.replaced)))
      lines.append("")
    if self._output.removed:
      lines.append("# Variables deleted/unset")
      lines.append("\n".join(sorted(self._output.removed)))
      lines.append("")
    if self._output.listchange:
      lines.append("# Lists prefixed/appended to")
      lines.append("\n".join(sorted(self._output.listchange)))
      lines.append("")
    if self._output.assumed_listchange:
      lines.append("# Variables created - but looked like a list; assuming prefix operation")
      lines.append("\n".join(sorted(self._output.assumed_listchange)))
      lines.append("")
    if self._output.unhandled:
      lines.append("# WARNING: The following were unhandled/unknown/too complex")
      lines.append("\n".join(x + "#" for x in sorted(self._output.unhandled)))
      lines.append("")
    return "\n".join(lines)

class GNUModulesFormatter(OutputFormatter):
  def __init__(self, *args, **kwargs):
    super(GNUModulesFormatter, self).__init__(*args, **kwargs)

  def add(self, key, value):
    # self._output.added.append("export {}={}".format(key, value))
    self._output.added.append("setenv {} {}".format(key, value))

  def replace(self, key, value):
    "When a variable is replaced/written over completely"
    # self._output.replaced.append("export {}={}".format(key, value))
    self._output.replaced.append("setenv {} {}".format(key, value))

  def unhandled(self, key, value, comment=""):
    "When we don't know how to handle, just replace with a warning"
    # out = "export {}={}".format(key, value)
    out = "setenv {} {}".format(key, value)
    if comment:
      out += " # {}".format(comment)
    self._output.unhandled.append(out)

  def remove(self, key):
    self._output.removed.append("unsetenv {}".format(key))

  def expand_list(self, key, prefix=[], postfix=[], assumed=False):
    dest_list = self._output.assumed_listchange if assumed else self._output.listchange

    # Don't support single-item empty prefix/postfix
    if len(prefix) == 1 and prefix[0].strip() == "":
      prefix = []
    if len(postfix) == 1 and postfix[0].strip() == "":
      postfix = []
    
    if prefix:
      dest_list.append("prepend-path {} {}".format(key, ":".join(prefix)))
    if postfix:
      dest_list.append("append-path  {} {}".format(key, ":".join(postfix)))
      
  def dump(self):
    lines = []
      # Do the actual output, grouped, with information
    if self._output.added:
      lines.append("# Variables added")
      lines.append("\n".join(sorted(self._output.added)))
      lines.append("")
    if self._output.replaced:
      lines.append("# Variables replaced - these had a value before that changed")
      lines.append("\n".join(sorted(self._output.replaced)))
      lines.append("")
    if self._output.removed:
      lines.append("# Variables deleted/unset")
      lines.append("\n".join(sorted(self._output.removed)))
      lines.append("")
    if self._output.listchange:
      lines.append("# Lists prefixed/appended to")
      lines.append("\n".join(sorted(self._output.listchange)))
      lines.append("")
    if self._output.assumed_listchange:
      lines.append("# Variables created - but looked like a list; assuming prefix operation")
      lines.append("\n".join(sorted(self._output.assumed_listchange)))
      lines.append("")
    if self._output.unhandled:
      lines.append("# WARNING: The following were unhandled/unknown/too complex")
      lines.append("\n".join(x + "#" for x in sorted(self._output.unhandled)))
      lines.append("")
    return "\n".join(lines)

def process_argv(docstr, argv=None):
  "Process argv in a docopt-like way"
  options = {
    "--bash": True,
    "--modules": False,
    "--warn-empty": False,
  }
  # Make a copy of argv to start removing non-argument items from it
  filtered_argv = sys.argv[1:] if argv is None else argv[1:]
  
  # While bash is the only output, this is a noop
  if "--bash" in filtered_argv and "--modules" in filtered_argv:
    print("Error: Can not specify both --bash and --modules")
    sys.exit(1)
  if "--bash" in filtered_argv:
    filtered_argv.remove("--bash")
    options["--bash"] = True
  if "--modules" in filtered_argv:
    filtered_argv.remove("--modules")
    options["--bash"] = False
    options["--modules"] = True
  if "--warn-empty" in filtered_argv:
    filtered_argv.remove("--warn-empty")
    options["--warn-empty"] = True
  if "-h" in sys.argv or "--help" in filtered_argv or not filtered_argv:
    print(docstr.strip())
    # Exit with 0 if help requested, otherwise an error
    sys.exit(1 if len(filtered_argv) == 1 else 0)

  options["<script>"] = filtered_argv[0]
  options["<arg>"] = filtered_argv[1:]

  return options
  

def main():
  # Handle arguments and help
  options = process_argv(__doc__)
  
  # The start environment is simple...
  start_env = dict(os.environ)

  # Generate the after-environment by sourcing the script
  script = " ".join([options["<script>"]] + [" ".join(options["<arg>"])])
  shell_command = ". {} 1>&2 && python -c 'import os; print(repr(os.environ))'".format(script)
  try:
    env_output = subprocess.check_output(shell_command, shell=True, executable="/bin/bash", stderr=subprocess.STDOUT)
  except subprocess.CalledProcessError as ex:
    print("Error loading script: Returned non-zero status code.")
    if ex.output:
      print("Output from failed process:")
      print("\n".join("  " + x for x in ex.output.splitlines()))

    sys.exit(1)

  sourced_env = eval(env_output)

  # Keys to ignore - e.g. things that normally change in any sourced script
  IGNORE = {"SHLVL", "_", "OLDPWD"}
  for key in IGNORE:
    if key in sourced_env:
      del sourced_env[key]
    if key in start_env:
      del start_env[key]

  # Make useful sets out of the dictionary keys
  start_keys = set(start_env.keys())
  sourced_keys = set(sourced_env.keys())
  added_keys = sourced_keys - start_keys
  changed_keys = {x for x in (start_keys & sourced_keys) if start_env[x] != sourced_env[x]}

  # Choose the formatting class for output
  if options["--bash"]:
    formatter = BashFormatter()
  elif options["--modules"]:
    formatter = GNUModulesFormatter()

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
      # If we changed from nothing, then still count as added
      if start_env.get(key) == "":
        if options["--warn-empty"]:
          print("Warning: variable {} was replaced, but was originally empty. Emitting as add operation".format(key))
        added_keys |= {key}
      else:
        replaced_keys |= {key}

  # Removed keys are the easy case: Must have been unset
  for key in start_keys - sourced_keys:
    formatter.remove(key)

  # Firstly, added keys
  for key in added_keys:
    formatter.add(key, sourced_env[key])

  # Handle keys explicitly overwritten separately
  for key in replaced_keys:
    formatter.replace(key, sourced_env[key])

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
      formatter.expand_list(key, prefix=end, assumed=True)
      # output.assumed_listchange.append("export {}={}".format(key, ":".join(end + ["$"+key])))
    else:
      # Look for the start embedded in the end
      if not contains_sublist(end, start):
        formatter.unhandled(key, sourced_env[key])
        # output.unhandled.append("export {}={} # complex list handling?".format(key, sourced_env[key]))
        # We don't have the original list embedded in the end list...
        # raise NotImplementedError("Not yet handling lists with removed items")
      else:

        ind = index_of_sublist(end, start)

        prefix = end[:ind]
        suffix = end[ind+len(start):]
        formatter.expand_list(key, prefix, suffix)

      # new_list = prefix + ["$"+key] + suffix
      # output.listchange.append("export {}={}".format(key, ":".join(new_list)))

  print(formatter.dump())

if __name__ == "__main__":
  main()
