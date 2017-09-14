#!/usr/bin/env python

from envdiff import contains_sublist, sublist_index

def test_sublist():
  assert contains_sublist([1,2,3,4,5], [5])
  assert sublist_index([1,2,3,4,5], [5]) == 4
  
  assert contains_sublist([1,2,3,4,5], [2,3])
  assert sublist_index([1,2,3,4,5], [2,3]) == 1

  assert not contains_sublist([1,2,3,4,5], [6])
  assert not contains_sublist([], [6])

  assert contains_sublist([1,2,3,4,5], [])
  