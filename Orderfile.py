#!/usr/bin/env python

import zlib
import re

class Orderfile:
    def __init__(self, s):
	# Quick and dirty extraction of useful info from the orderfile:
	self.s = s
	self.innards = zlib.decompress(s[35:])
	self.message, rest = re.search("message = (.*?)\n(.*)$",
		self.innards, re.S).groups()
	self.pnum = int(re.search("playerNum = ([0-9])", rest).groups()[0])
	self.turn = int(re.search("turn = ([0-9]*)", rest).groups()[0])
	self.gnum = re.search("game_id = ([0-9]*)", rest).groups()[0]
	self.conceded = re.search("conceded = (true|false)", rest).groups()[0]
	self.race = re.search("\x00\x00\x00(spwn|marn|mech|grey)", rest).groups()[0]

	# Verifying these are really numbers:
	int(self.pnum) + int(self.turn) + int(self.gnum)

if __name__=="__main__":
    import sys
    for f in sys.argv[1:]:
	s = open(f).read()
	try:
	    tf = Orderfile(s)
	    print tf.__dict__
	except:
	    print zlib.decompress(s[35:])
	    raise
