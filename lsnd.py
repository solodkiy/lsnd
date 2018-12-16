#!/usr/bin/env python

import os, sys
from string import *

import signal
import re
import ast
import random
import time
import mailbox
import base64
import smtplib
from cPickle import dump, load
from glob import glob
from time import sleep
from email.encoders import encode_base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.header import decode_header
from email.Utils import parseaddr

from Orderfile import Orderfile

HOME=os.environ['HOME']

serverAddress = 'mbays@paunix.org'
helpurl = 'http://mbays.freeshell.org/lsnd/USAGE'
SMTPHelpUrl = 'http://mbays.freeshell.org/lsnd/SMTPHelp'
codeurl = 'http://mbays.freeshell.org/lsnd/'
logfile = HOME+'/var/log/lsnd'
sentlogfile = HOME+'/var/log/lsnd-sent'
lsndir = HOME+'/lsn'
chalfile = '%s/challenges' % lsndir
automaton = HOME+'/bin/lsnautomaton.sh'

DEFAULT_MAXTURNS = 30
DEFAULT_FP = 20
DEFAULT_GAMETYPE = 'wipeout'

MAXAUTOMS=6
XDEBUG=False
MAX_LADDER_DIFF=30

automataPIDs = {}

def rmrf(victim):
    for r,ds,fs in os.walk(victim, False):
	for f in fs: os.remove(os.path.join(r,f))
	for d in ds: os.removedirs(os.path.join(r,d))

def fexists(f):
    return os.access(f, os.R_OK)

def greater(x,y):
    if x > y: return x
    else: return y
greatest = lambda l: reduce(greater, l, 0)

def PIDIsAlive(pid):
    try:
	# check if the automaton is alive - no actual signal is sent
	os.kill(pid, 0)
	return True
    except:
	return False

def killAutomaton(gnum):
    os.kill(automataPIDs[gnum], 15)
    del automataPIDs[gnum]
    sleep(5)

def getActualAddr(addr):
    # "Foo Bar <foobar@example.com>" -> "foobar@example.com"
    return parseaddr(addr)[1].lower()

class MailProcException(Exception):
    pass
class AutomatonException(Exception):
    pass

def spawnAutomaton(gnum):
    if len(automataPIDs.keys()) >= MAXAUTOMS:
	killnum = automataPIDs.keys()[0]
	logit("Killing old game %s" % killnum)
	killAutomaton(killnum)
    if XDEBUG:
	PID = os.spawnl(os.P_NOWAIT, automaton, automaton, '-x', gnum)
    else:
	PID = os.spawnl(os.P_NOWAIT, automaton, automaton, gnum)
    logit("Spawned %d" % PID)
    automataPIDs[gnum]=PID


def handleSIGCHLD(signum, frame):
    os.waitpid(-1, os.WNOHANG)

serverIdentText = "This is the Unofficial Hacky LSN Server at %s" % (
	serverAddress )

helptext = \
"""How to use this server:

* Starting a new game:
Send a mail to %s with subject line:

LSN New [opponentAddress] [type] [FP] [maxturns] [map] [mode]

type, FP, maxturns, map and mode are all optional - defaults are Friendly, 20,
30, Pool and wipeout respectively.

opponentAddress is also optional - if you leave it blank, it's interpreted as
accepting/creating an "open challenge". If there's a challenge open which
doesn't conflict with your parameters, you'll accept it; else, you'll create a
new challenge.

Examples:
LSN New
    - just get a game
LSN New evil@xyz.zy
    - start a game against evil@xyz.zy on a random map
LSN New evil@xyz.zy L 30 40 forest hq
    - start a ladder hq game on Forest with 30 fp limit and 40 turn limit
LSN New trains
    - play on Trains against whoever next sends 'LSN New' or 'LSN New trains'

To get a list of maps you can use, send a mail with subject line "LSN maps",
or see http://www.countzero.pwp.blueyonder.co.uk/lsn/maphq.htm.
Map names are not case sensitive. If you don't specify a map, or if you
specify "Pool", a random balanced map from the map pool will be chosen; if you
specify "Random", a possibly unbalanced random map will be used.

* Playing turns:
You will get .lsn files mailed to you. You should open these with your
LSNClient.exe and play the turn, and send your orders back to this server.

There are two ways to do this.

The first is simply to mail your orders to the server. At the end of your
turn, hit 'save file'. LSN will save a file which you should manually send to
the server by sending a mail with subject line "LSN Game" to %s,
with the orders file created by LSN attached (note you should send the orders
file, not the gamestate file). You will find the file somewhere like:
    Games/00001337/Orders/orders1_G00001337_T17.lsn

The second option is to set things up such that the LSN client will send the
mails for you. NOTE: it has been reported that this hacking of LSNClient.exe
might make windows refuse to run the exe. If you try this, please tell me how
it goes! If you want to try, here's how:
(i) Ensure that Configs/UserData.cfg has SMTPServer set to an
    *unauthenticated* SMTP server you have access to. If you're lucky, your
    ISP will provide such a server - but you may well find that you have
    access only to SMTP servers which require authentication. In this case,
    your best bet is probably to set SMTPServer to 'localhost', and set up an
    SMTP server on your own machine to relay mails via an authenticated
    server. For some simple instructions on how to do this on a Windows
    machine, see %s
    or mail %s with subject 'LSN SMTP Help'.
(ii) Make a backup of LSNClient.exe
(iii) load LSNClient.exe in your favourite hex editor, go to position 2175AC,
    and change '<lsnorders@codo-linux1.bytemark.co.uk>' to '<%s>'.
    Ensure that the bytes between the '>' and 'Could not send mail' are all
    00.
    If you have access to a unix shell, you could use the following command to
    do this rather than using a hex editor:
    sed "s/<lsnorders@codo-linux1.bytemark.co.uk>/<%s>%s/g" < LSNClient.exe > LSNClient.hacked.exe
(iv) always use this hacked version of LSNClient.exe when loading games from
    this server. At the end of your turn, hit 'send'.

* Ladder and Rating:
There are three types of game: Ladder, Friendly, and Very Friendly
(abbreviated to L, F, VF). In Ladder games, you play for ladder points. In
Ladder games and Friendlies, you play for ELO. In VFs, you just play.

You can check the current ladder with the 'ladder' command. You'll be added to
it if you play a ladder game.

ELO isn't implemented yet!

For the purposes of the ladder and ratings, you are your email address.
Specifically, the email address you send your first turn from is the one which
counts.

* Other commands:
You can get a list of open challenges with "LSN challenges", and can cancel
the challenges you've made with "LSN unchallenge".

"LSN games" will give info on the games you have in progress. You are
identified by your email address. If you lost a turn file, you can get the
server to resend the last turn's results with "LSN resend [game number]"
(or "LSN resend [game number] [turn]" if you want an old results file).


Warnings and disclaimers:
This server is running on my home computer, which is neither beefy nor
permanently on. Processing will sometimes take a few minutes, sometimes a few
hours, and occasionally a few days. Please be patient.

This server is intended only as a stop-gap solution. Hopefully, Codogames will
either start a proper server going again, or give the community the means to
do so.

If Codogames at any point ask me to stop running this server, I will do so.

One last warning: the password set in your LSN client is sent out with your
orders files, so if I wanted to (which I don't) I could read them. So if your
password is at all sensitive, I suggest you blank it out before using this
server.

Full technical information about this server, including all code, is available
at %s.


Summary of commands:
LSN new [opponentAddress] [type] [FP] [maxturns] [map] [mode]
LSN game [[with turnfile attached]]
LSN games
LSN ladder
LSN resend [game number] [turn]
LSN challenges
LSN unchallenge
LSN cancel [game number]
LSN help


That's it. Happy gaming!
""" % (serverAddress, serverAddress, SMTPHelpUrl, serverAddress,
	serverAddress,
	'\\x00'*(len('lsnorders@codo-linux1.bytemark.co.uk') -
	    len(serverAddress)),
	serverAddress, codeurl)

SMTPHelptext = \
"""Simple instructions for setting up a relaying SMTP server in windows
====================================================================

Download hMailServer from www.hmailserver.com. These instructions are based on
version 5.3.

Install it, accepting all defaults.

Enter a password when it asks, then have it start the 'administrator' when it
offers to.

In the administrator, hit 'connect'.

On the left, select Advanced->IP Ranges, then double-click on 'internet'.

Under "Allow deliveries", deselect everything.

Now select 'My computer' under Advanced->IP Ranges, ensure that "Allow
deliveries from: external to external" is ticked, but "require SMTP
authentication: external to external" is *not* ticked.

If you're lucky, your ISP is not blocking outgoing connections to SMTP
servers, and you should now be done. But probably you're not lucky, and you'll
have to set the server to forward mail via your ISP's server.

To do this, go to Settings->Protocols->SMTP->Delivery of e-mail, and put the
details of your ISP's SMTP server there. This is most likely something like
"smtp.yourisp.com", port 25, and maybe some authentication details.

Hopefully, all will now work.

Please test that you are not now running an open relay - see
http://www.abuse.net/relay.html
"""

def validMaps():
    return [ fn[:-4].lower()
	    for fn in os.listdir('Map')
	    if fn[-4:] == '.map' ]
# list of maps removed from the random pool taken from
# http://www.countzero.pwp.blueyonder.co.uk/lsn/maphq.htm
UNBALANCED_MAPS = [
"access control", "arena", "beach head", "beach strike", "big brother",
"bio dome", "chess", "colony", "tournament", "confusion", "data bank",
"dehydration", "depot", "ellbese cafe", "enemy hq", "football", "forest",
"high command", "holding cell", "jungle p o w", "labs", "last stand",
"mirror arena", "moon base", "pacman", "praerie", "restaurant", "rugby",
"scrum", "shuttle assault", "slum clearance", "sniper duel",
"the tomb of lord x", "tic tac toe", "training camp", "warehouse jungle" ]

def poolMaps():
    return [ map for map in validMaps() if map not in UNBALANCED_MAPS ]

def mailText(subject, text, addr):
    msg = MIMEText(serverIdentText + '\n\n' + text)
    msg['Subject'] = '[LSN] %s' % subject
    msg['From'] = serverAddress
    msg['To'] = addr

    sendMail(msg.as_string(), addr)

def sendMail(text, addr):
    s = smtplib.SMTP('localhost')
    s.sendmail(serverAddress, [addr], text)
    s.quit()

    open(sentlogfile, 'a').write(text)

def turnProcessed(gnum, turn):
    return fexists('Games/%s/processed_T%d' % (gnum, turn))

processAttempts=0
def waitForResults(gnum, turn):
    pid = automataPIDs[gnum]
    maxTime=(8+turn)*3*60
    global processAttempts
    processAttempts += 1
    if processAttempts == 5:
	# the issue might be that we have too many automs running
	# (not sure why, but this is sometimes a problem!)
	logit("Kill them all!")
	for gnum2 in automataPIDs.keys():
	    if gnum2 != gnum:
		killAutomaton(gnum2)
    if processAttempts >= 10:
	# let's not overload the server with failure...
	logit("Taking %ds to consider our mistakes." % processAttempts)
	time.sleep(processAttempts)

    for i in range(maxTime):
	if turnProcessed(gnum, turn):
	    return True

	if not PIDIsAlive(pid):
	    del automataPIDs[gnum]
	    raise AutomatonException("Automaton died")
	
	time.sleep(1)

    raise AutomatonException("Processing stuck")
    processAttempts = 0

def mailResults(gnum, turn, p1, p2, chernum=None, p1msg='', p2msg='',
	winner=None, concessions=[False,False]):

    addrs = (p1,p2)
    msgs = (p1msg,p2msg)

    for p in (0,1):
	addr = addrs[p]
	oppaddr = addrs[1-p]
	rf = 'Games/%s/results%d_G%s_T%d.lsn' % (gnum, p+1, gnum, turn)

	msg = MIMEMultipart()
	subject = '[LSN] '
	if turn == 0:
	    subject += "New game vs %s" % oppaddr
	else:
	    subject += "Game %s turn %d vs %s" % (gnum, turn, oppaddr)
	
	if winner:
	    if winner == str(p+1):
		subject += " - Victory!"
	    elif winner == str((1-p)+1):
		subject += " - Defeat"
	    else:
		subject += " - Game ends in a draw"

	text = serverIdentText + '\n\n'

	if turn == 0:
	    if p == chernum:
		text += ( "This is the deployment phase of your new game "
			"against %s." % oppaddr )
	    else:
		text += ( "%s has challenged you to a game of Laser Squad" 
			" Nemesis. This is the deployment phase.\n\n"
			"If you do not want to play the game, please send a"
			" mail to %s\nwith subject line 'LSN cancel %s'." %
			(oppaddr, serverAddress, gnum) )
	else:
	    text += ( "This is turn %d of your game against %s" %
		    (turn, oppaddr ) )
	text += '\n\n'

	if concessions[p]:
	    text += "You conceded the game.\n\n"
	if concessions[1-p]:
	    text += "Your opponent conceded the game.\n\n"
	    if concessions[p]:
		text += "As well. On the same turn. Funny, eh?\n\n"
	
	if msgs[1-p] != '':
	    text += ("Message from opponent: %s\n\n" % msgs[1-p])

	if turn <= 1:
	    text += ( "If you have not used this server before, please"
		" read\n\t%s ,\nor send a mail to %s with subject line"
		" 'LSN Help',\nto find out how to do so." % (
		    helpurl, serverAddress) )

	msg['From'] = serverAddress
	msg['To'] = addr
	msg['Subject'] = subject
	msg.preamble = "There's an LSN turn file in here - I suggest you use a MIME-aware mail user agent to get at it."
	msg.attach(MIMEText(text))

	resmsg = MIMEBase('application', 'octet-stream')
	resmsg.set_payload(open(rf).read())
	encode_base64(resmsg)
	resmsg.add_header('Content-Disposition', 'attachment',
		filename="LSN_%s_T%d.lsn" % (gnum, turn))

	msg.attach(resmsg)

	sendMail(msg.as_string(), addr)

def ladderAdjust(ps, amounts):
    try: ladder = load(open(ladderFile))
    except: ladder = {}
    ds = [0,0]
    for i in (0,1):
	old = ladder.get(ps[i], 0)
	new = max(0, old + amount[i])
	ladder[p] = new
	ds[i] = new - old
    dump(ladder, open(ladderFile, 'w'))
    for i in (0,1):
	if ds[i] != 0:
	    mailText("You %s %d ladder points!" % (("lost","won")[d>0], d), 
		    "You now have %d points.\n\n"
		    "Current ladder:\n\n%s" % showLadder(ps[i]), ps[i])

def showLadder(shown):
    try: ladder = load(open(ladderFile))
    except: ladder = {}
    pairs = ladder.items()
    pairs.sort(lambda a,b: -cmp(a[1],b[1]))
    return join([
	"%-50s  |  %d" % ( ('',"--> ")[p==shown] + p, points)
	for (p,points) in pairs ], '\n')

def checkLadderability(p1, p2):
    try: ladder = load(open(ladderFile))
    except: ladder = {}
    return abs(ladder.get(p1,0) - ladder.get(p2,0)) <= MAX_LADDER_DIFF

def resendTurnfile(gnum, turn, player):
    gamedir = lsndir+'/Games/%s'%gnum
    if not os.path.exists(gamedir):
	raise MailProcException("Game %s does not exist." % gnum)

    plmatch = [ p for p in [1,2] if
	    getActualAddr(open("%s/conf/p%d" % (gamedir,p)).read().strip()) == player ]
    if plmatch == []:
	raise MailProcException("You're not playing in game %s!" % gnum)
    pnum = plmatch[0]

    if turn == None:
	turn = greatest(map(int,
	    map(lambda f: re.sub('.*T(\d*)\.lsn','\\1',f),
		glob(gamedir+'/results%d_G%s_T*.lsn' % (pnum,gnum)))))

    rf = gamedir+'/results%d_G%s_T%d.lsn' % (pnum, gnum, turn)
    if not os.path.exists(rf):
	raise MailProcException("Turn %d not processed in game %s" % (turn, gnum))

    msg = MIMEMultipart()
    msg['From'] = serverAddress
    msg['To'] = player
    msg['Subject'] = "resending results for turn %d in game %s" % (turn, gnum)
    msg.preamble = "There's an LSN turn file in here - I suggest you use a MIME-aware mail user agent to get at it."

    text = serverIdentText+'\n\n'
    text += 'As requested, please find attached the results file for turn %d in game %s' % (turn, gnum)
    msg.attach(MIMEText(text))

    resmsg = MIMEBase('application', 'octet-stream')
    resmsg.set_payload(open(rf).read())
    encode_base64(resmsg)
    resmsg.add_header('Content-Disposition', 'attachment',
	    filename="LSN_%s_T%d.lsn" % (gnum, turn))

    msg.attach(resmsg)

    sendMail(msg.as_string(), player)


def handleOrderfile(OF, frm):
    gnum = OF.gnum
    gdir = 'Games/%s' % gnum
    confdir = 'Games/%s/conf' % gnum
    OFname = "%s/Orders/orders%d_G%s_T%d.lsn" % (gdir, OF.pnum, gnum, OF.turn)

    if re.search('^....Nemesis-3-10',OF.s) == None:
	raise MailProcException("Bad LSN client version - we need 3.10")

    if fexists(confdir+'/gameover'):
	raise MailProcException("Game %s is already finished" % gnum)

    if (OF.conceded == "true" and fexists(OFname)):
	# Bizarreness: orders to concede seem to come with the *previous* turn
	# as the turn number... we just hack here to fix that!
	OF.turn+=1
	OFname = "%s/Orders/orders%d_G%s_T%d.lsn" % (
		gdir, OF.pnum, gnum, OF.turn)

    if not fexists(OFname):
	try:
	    open(OFname, 'w').write(OF.s)
	except:
	    raise MailProcException("bad game number: %s" % gnum)

	open("%s/p%dmsg" % (confdir, OF.pnum), 'w').write(OF.message)

	if (OF.conceded == "true"):
	    open("%s/p%dconceded" % (confdir, OF.pnum), 'w').write('')

    if tryProcessTurn(gnum, OF.turn) == "waiting":
	p = open("%s/p%d" % (confdir, OF.pnum), 'r').read().strip()
	mailText("Orders accepted for %s; waiting for opponent" % gnum,
	    "The game will proceed as soon as your opponent submits their"
	    " orders for this turn", p)

    if OF.turn == 1:
	# Let the player decide what email address they want to use
	open('%s/p%s' % (confdir, OF.pnum),'w').write("%s\n" % frm)
	

def tryProcessTurn(gnum, turn):
    # check we have the orders files
    for p in (1,2):
	if not fexists("Games/%s/Orders/orders%d_G%s_T%d.lsn" % (gnum, p,
	    gnum, turn)):
	    return "waiting"
    if turnProcessed(gnum, turn):
	raise MailProcException("Turn %d already processed in game %s" % (turn, gnum))
    
    confdir = 'Games/%s/conf' % gnum

    p1 = open("%s/p1" % confdir).read().strip()
    p2 = open("%s/p2" % confdir).read().strip()
    p1msg = open("%s/p1msg" % confdir).read().strip()
    p2msg = open("%s/p2msg" % confdir).read().strip()
    logit("Processing turn %d of game %s (%s vs %s)" % (turn, gnum, p1, p2))

    if not (automataPIDs.has_key(gnum) and
	    PIDIsAlive(automataPIDs[gnum])):
	spawnAutomaton(gnum)

    waitForResults(gnum, turn)

    concessions = [ fexists("%s/p%dconceded" % (confdir, p)) for p in (1,2) ]
    if True in concessions:
	if concessions == [True,True]:
	    winner = 'd'
	elif concessions[0]:
	    winner = '2'
	else:
	    winner = '1'
	open("%s/gameover" % confdir, 'w').write(winner)
    else:
	try:
	    winner = open("%s/gameover" % confdir).read().strip()
	    del automataPIDs[gnum]
	except IOError:
	    winner = None

    if winner:
	logit("Game %s (%s vs %s) over. Winner:%s" % (gnum, p1, p2, winner))
	try: friendliness = open('%s/friendliness' % confdir).read().strip()
	except: friendliness = 'F'
	if friendliness == 'L' and winner in ["1","2"]:
	    w = int(winner)-1
	    ladderAdjust((p1,p2), (5*(-1)**winner=="2", 5*(-1)**winner=="1"))
	    

    mailResults(gnum, turn, p1, p2, None, p1msg, p2msg, winner, concessions)
    logit("Processed turn %s:%d" % (gnum, turn))
	
def startGame(challenger, challenged, friendliness=None, maxfp='20',
	maxturns='30', mapname=None, gametype='wipeout'):

    chernum = random.randrange(2)
    if chernum == 0:
	p1=challenger
	p2=challenged
    else:
	p1=challenged
	p2=challenger

    if friendliness is None:
	friendliness = "F"
    friendliness = { "ladder" : "L", "friendly" : "F", "very friendly": "VF",
	    "very f": "VF", "v friendly": "VF" }.get(friendliness.lower(),
		    friendliness)
    if friendliness == 'L' and not checkLadderability(challenger, challenged):
	raise MailProcException(
	"Can't start a ladder match - players too mismatched"
	" (more than %d ladder points difference)" % MAX_LADDER_DIFF)

    if gametype and gametype.lower() == 'hq':
	gametype = 'hq'
    else:
	gametype = 'wipeout'

    if mapname:
	mapname=mapname.lower()

    if not mapname or mapname == 'pool':
	mapname = random.choice(poolMaps())
    elif mapname == 'random':
	mapname = random.choice(validMaps())
    elif mapname not in validMaps():
	raise MailProcException("Unknown map: %s. Use 'LSN maps' to get a"
		" list of valid maps." % mapname)
    
    try:
	gnum='%08d' % ( int(open("lastGnum").read()) + 1 )
    except:
	gnum='00001337'

    while turnProcessed(gnum, 0):
	gnum='%08d' % (int(gnum)+1)

    gdir = 'Games/'+gnum
    if not fexists(gdir):
	os.mkdir(gdir)

    confdir=gdir+'/conf'
    if not fexists(confdir):
	os.mkdir(confdir)

    # XXX: what the docs call 'type' is in the code called 'friendliness', and
    # what they call 'mode' is called 'gametype'. Ah, the pains of tweaking
    # a system which is already running...
    open(confdir+'/friendliness','w').write("%s\n" % friendliness)
    open(confdir+'/maxfp','w').write("%s\n" % maxfp)
    open(confdir+'/maxturns','w').write("%s\n" % maxturns)
    open(confdir+'/mapname','w').write("%s\n" % mapname)
    open(confdir+'/gametype','w').write("%s\n" % gametype)
    open(confdir+'/p1','w').write("%s\n" % p1)
    open(confdir+'/p2','w').write("%s\n" % p2)
    open(confdir+'/p1msg','w').write("\n")
    open(confdir+'/p2msg','w').write("\n")

    logit("Starting game %s: %s v %s on %s" % (gnum, p1, p2, mapname))

    spawnAutomaton(gnum)

    waitForResults(gnum, 0)

    open("lastGnum", 'w').write(gnum+'\n')
    
    mailResults(gnum, 0, p1, p2, chernum)
    logit("Processed turn %s:%d" % (gnum, 0))

def showGames(pl):
    # List comprehensions are fun! (to write, whether or not to read!)
    return join([
	"%s: %s vs. %s on %s; turn %d/%s: %s" % (
		gnum, conf['p1'], conf['p2'], conf['mapname'], lastProcessed,
		{'None':str(DEFAULT_MAXTURNS)}.get(conf['maxturns']),
		{(True,True): "orders in, processing", (False,False): "waiting for orders",
		    (True, False): "waiting for player 2's orders",
		    (False,True): "waiting for player 1's orders"}[moved])

	    for gnum in map(os.path.basename, glob(lsndir+'/Games/*'))
	    for gamedir in [ '%s/Games/%s' % (lsndir, gnum) ]
	    for confdir in [ gamedir+'/conf' ]
	    for conf in [
		dict([ (f, open(confdir+'/%s'%f).read().strip())
		for f in ['p1','p2','mapname','maxturns'] ]) ]
	    for lastProcessed in [ greatest(map(int,
		map(lambda f: re.sub('.*T','',f),
		    glob(gamedir+'/processed_T*')))) ]
	    for moved in [ tuple([
		os.path.exists(gamedir+'/Orders/orders%s_G%s_T%d.lsn' %
		    (p,gnum,lastProcessed+1)) for p in ['1','2'] ]) ]
	    if True in [os.path.exists(confdir+'/p%s' % p)
		and pl == getActualAddr(open(confdir+'/p%s' % p).read().strip())
		for p in ['1','2'] ] and not os.path.exists(confdir+'/gameover')
	    ],'\n')

def cancelGame(gnum, canceler):
    if not fexists("Games/%s/results1_G%s_T0.lsn" % (gnum, gnum)):
	raise MailProcException("Game %s does not exist" % gnum)
    if not canceler in [ open("Games/%s/conf/p%s" % (gnum,p)).read().strip()
	    for p in ['1','2'] ]:
	raise MailProcException("Not your game to cancel!")
    if fexists("Games/%s/results1_G%s_T1.lsn" % (gnum, gnum)):
	raise MailProcException("Game %s already in progress" % gnum)

    logit("Game %s canceled by %s" % (gnum, canceler))
    if automataPIDs.has_key(gnum):
	killAutomaton(gnum)
    confdir = 'Games/%s/conf' % gnum
    open("%s/gameover" % confdir, 'w').write('c')
    p1 = open("%s/p1" % confdir).read().strip()
    p2 = open("%s/p2" % confdir).read().strip()
    mailText("Game %s canceled by %s" % (gnum, canceler), "", p1)
    mailText("Game %s canceled by %s" % (gnum, canceler), "", p2)

def logit(text):
    stampedText = time.strftime('%b %e %T') + " " + text + '\n'
    sys.stderr.write(stampedText)
    try:
	log=open(logfile, 'a')
	log.write(stampedText)
	close(log)
    except:
	pass

commPat = '\s*\[?(?:LSN|Laser Squad Nemesis)\]?\s*'
emailPat = '[A-Z0-9._%+-]+@[A-Z0-9.-]+'
startGamePat = ( '^%s(?:start|new|challenge)\s*(?:game)?' '(?:\s+' '<?(%s)?>?'
	'\s*(?:(L(?:adder)?|F(?:reindly)?|V(?:ery )?F(?:riendly)?)\s+)?'
	'\s*([0-9]+)?' '\s*([0-9]+)?' '\s*[\'"]?(\w[a-z0-9 ,.]*?)?[\'"]?'
	'\s*(wipeout|hq)?)?\s*$') % (commPat, emailPat)
turnfilePat = '^%s(game|file|orders)' % commPat
cancelPat = '^%scancel\s*([0-9]+)' % commPat

def mainloop():
    signal.signal(signal.SIGCHLD, handleSIGCHLD)

    if not os.access(HOME+'/Mail', os.W_OK):
	os.mkdir(HOME+'/Mail')
    failbox=mailbox.mbox(HOME+'/Mail/lsnfails')
    processedbox=mailbox.mbox(HOME+'/Mail/lsnprocessed')

    os.chdir(lsndir)

    inbox = mailbox.Maildir(HOME+'/.maildir', None)

    while True:
	for k, mail in inbox.iteritems():
	    if k == '.keep':
		continue
	    frm = getActualAddr(mail['From'])
	    subject = decode_header(mail['Subject'])[0][0]

	    logit("Handling mail; From: %s; Subject %s" % (frm, subject))

	    startGameMatch = re.match(startGamePat, subject, re.I)
	    turnfileMatch = re.match(turnfilePat, subject, re.I)
	    cancelMatch = re.match(cancelPat, subject, re.I)
	    challengesMatch = re.match('%schallenges' % commPat, subject, re.I)
	    unchallengeMatch = re.match('%sunchallenge' % commPat, subject, re.I)
	    gamesMatch = re.match('%s(show\s*)?games' % commPat, subject, re.I)
	    ladderMatch = re.match('%s(show\s*)?ladder' % commPat, subject, re.I)
	    helpMatch = re.match('%shelp' % commPat, subject, re.I)
	    SMTPHelpMatch = re.match('%ssmtp\s*help' % commPat, subject, re.I)
	    processMatch = re.match(
		    '%sprocess\s*([0-9]+)\s*[-:]*\s*([0-9]+)\s*$' % commPat,
		    subject, re.I)
	    resendMatch = re.match(
		    '%sresend\s*([0-9]+)\s*([0-9]+)?\s*$' % commPat, subject, re.I)

	    try:
		if startGameMatch:
		    g = startGameMatch.groups()
		    try: challenges = load(open(chalfile))
		    except: challenges = []
		    if g[0] is None:
			goodChallenges = [ ch for ch in challenges if
				ch[0] != frm and False not in
				[ g[i] in [None, ch[i]] for i in range(1,5)] ]
			if goodChallenges == []:
			    ch = list(g[:])
			    ch[0] = frm
			    challenges.append(ch)
			    dump(challenges, open(chalfile,'w'))
			    mailText("Challenge registered",
				"There are no suitable open challenges, so "
				"I'm interpreting your request for a game\n"
				"as an open challenge. Your game will start "
				"when someone accepts the challenge.\n\n"
				"If you want to withdraw all your challenges, "
				"\nplease send a mail with subject 'lsn "
				"unchallenge'.", frm)
			else:
			    goodCh = goodChallenges[0]
			    params = [goodCh[0]] + [frm] + goodCh[1:]
			    startGame(*params)
			    challenges = [ ch for ch in challenges if ch != goodCh ]
			    dump(challenges, open(chalfile,'w'))
		    else:
			params = [frm, getActualAddr(g[0])] + list(g[1:])
			startGame(*params)
		elif unchallengeMatch:
		    try: challenges = load(open(chalfile))
		    except: challenges = []
		    challenges = [ ch for ch in challenges if ch[0] != frm ]
		    dump(challenges, open(chalfile,'w'))
		    mailText("Challenges removed",
			    "All open challenges have been removed.", frm)
		elif challengesMatch:
		    try: challenges = load(open(chalfile))
		    except: challenges = []
		    mailText("Current challenges",
			    join([ '%-40s %-5s %-3s %-6s %-10s %-7s' %
				tuple([{None:'-'}.get(f,f) for f in ch])
				for ch in [["Player","Type","FP","Turns","Map","Mode"]]+challenges],
				'\n'), frm)
		elif gamesMatch:
		    mailText("Games in progress", showGames(frm), frm)
		elif ladderMatch:
		    mailText("Current ladder", showLadder(frm), frm)
		elif resendMatch:
		    g=resendMatch.groups()
		    try: gnum='%08d' % int(g[0])
		    except: raise MailProcException("Bad game number")
		    try: turn = int(g[1])
		    except: turn = None
		    resendTurnfile(gnum, turn, frm)
		elif helpMatch:
		    logit("Sending help text to %s" % frm)
		    mailText("Help", helptext, frm)
		elif SMTPHelpMatch:
		    logit("Sending SMTP help text to %s" % frm)
		    mailText("SMTP Help", SMTPHelptext, frm)
		elif processMatch:
		    grps = processMatch.groups()
		    gnum='%08d' % int(grps[0])
		    turn=int(grps[1])
		    tryProcessTurn(gnum, turn)
		elif cancelMatch:
		    gnum='%08d' % int(cancelMatch.groups()[0])
		    cancelGame(gnum, frm)
		elif subject == "LSN xyzzy":
		    mailText("Nothing happens", "", frm)
		elif subject.lower() == "lsn maps":
		    mailText("List of known maps",
			    join(validMaps(), '\n'), frm)
		elif turnfileMatch:
		    foundOrders = False
		    for part in mail.walk():
			cd = part['Content-Disposition']
			if cd and cd[:10] == 'attachment':
			    orderfileString = base64.decodestring(
				    part.get_payload())
			    orderfile = None
			    try:
				orderfile = Orderfile(orderfileString)
			    except:
				pass
			    if orderfile:
				foundOrders = True
				handleOrderfile(orderfile, frm)
		    if not foundOrders:
			raise MailProcException("Expected to find a valid "
				"orderfile attached, but didn't.")

		else:
		    raise MailProcException("Couldn't understand subject "
			    "line: %s" % subject)
	    except MailProcException as exc:
		e = exc.args[0]
		logit("Mail processing failed - %s" % e)
		mailText("Mail processing failure",
			"There was an error in processing your mail." +
			"\n\nError message: %s" % e +
			"\n\nPlease see %s for usage," % helpurl +
			" or send a mail with subject line 'LSN Help'"
			, frm)
		try:
		    failbox.lock()
		    failbox.add(mail)
		    failbox.flush()
		    failbox.unlock()
		except:
		    logit("failbox writing failed... dear me. %s" %
			    str(sys.exc_info()))
		    pass
		pass
	    except AutomatonException as exc:
		e = exc.args[0]
		logit("Automaton badness: %s" % e)
		# We leave the mail on the queue, so we'll try again later.
		continue
	    except:
		logit("Unhandled exception during mail processing")
		raise

	    processedbox.lock()
	    processedbox.add(mail)
	    processedbox.flush()
	    processedbox.unlock()

	    inbox.lock()
	    inbox.remove(k)
	    inbox.flush()
	    inbox.unlock()

	time.sleep(1)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
	print helptext
	sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "--smtphelp":
	print SMTPHelptext
	sys.exit(0)
    options = sys.argv[1:]
    while len(options) > 0 and options[0] == "--xdebug":
	XDEBUG=True
	options = options[0:]
    while len(options) > 1 and options[0] == "--maxautoms":
	MAXAUTOMS=int(options[1])
	options = options[1:]
    try:
	mainloop()
    except:
	# clean up...
	for ps in automataPIDs.values():
	    os.kill(ps, 15)
	raise
