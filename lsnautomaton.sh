#!/bin/bash

XOPTS=
#XOPTS="-config xorg.conf.basic"

# rest for $RESTCPU seconds after every 30 during intensive processing
RESTCPU=20

function die ()
{
    echo "$0 $GNUM: $1" >&2
    exit 1
}

function usage ()
{
    echo -e "usage: $0 [-x] GAMENUMBER\n\t-x\tUse an actual non-virtual X"
    exit 2
}

usex=
while getopts "xh" opt; do
    case $opt in
        x) usex=1;;
        [?h]) usage;;
    esac
done

shift $(($OPTIND - 1))

[ -n "$1" ] || usage

lsndir=~/.lsn/lsndir
wine=~/.lsn/wine
xlog=~/.lsn/xlog
lsnlog=~/.lsn/lsnlog

[ -e "$lsndir" ] || die "make ~/.lsn/lsndir a link to your lsn directory"
if [ -L "$lsndir" ]; then lsndir="`readlink "$lsndir"`"; fi

if ! [ -e "$wine" ]; then
    wine=wine
elif [ -L "$wine" ]; then
    wine="`readlink "$wine"`"
fi

gnum="$1"
display=":$gnum"
# Yep, we use the game number as the X display number! Why not, eh?

gnum=`seq -f%08g "$gnum" "$gnum"` || die "GAMENUMBER should be a number"

if [ -n "$usex" ]; then
    X $XOPTS "$display" &> "$xlog" &
else
    Xvfb $XOPTS "$display" -screen 0 1024x768x16 &> "$xlog" &
fi
xpid=$!
export DISPLAY="$display"

cd "$lsndir"

# Hack us up a copy of the client, which stores hotseat game files in
# Games/$gnum:
lsnc=LSNClient.$gnum.exe
cp LSNClient.exe "$lsnc"
echo -e "%s/00000001/$gnum/g\nw" | ed "$lsnc" &>/dev/null

function lsnlives ()
{
    ps $lsnpid &>/dev/null
    return
}

function cleanup ()
{
    trap {} INT
    [ -e Configs/Command.cfg.bk ] && mv Configs/Command.cfg.bk Configs/Command.cfg
    kill $lsnpid &>/dev/null
    sleep 1
    kill -9 $lsnpid &>/dev/null
    kill $xpid &>/dev/null
    sleep 1
    kill -9 $xpid &>/dev/null
    rm "$lsnc" &>/dev/null
    exit
}

trap cleanup INT TERM EXIT

# Run the client.
nice -n 20 "$wine" "$lsnc" &> "$lsnlog" &
lsnpid=$!
sleep 5
if ! ps "$!" &>/dev/null; then
    sleep 30 
    if ! ps "$!" &>/dev/null; then
	cleanup 
	die "Client failed to start properly"
    fi
fi

# XXX: this seems not to work so well - cpulimit wakes the process back up
# after we suspend it...
#if [ -n "$CPULIMIT" ]; then
    #cpulimit -z -l $CPULIMIT -p $lsnpid &
#fi

gamedir=Games/$gnum
[ -e $gamedir ] || mkdir $gamedir
ordersdir=$gamedir/Orders

# Preserve any pre-existing orders:
[ -e $ordersdir ] && chmod -w $ordersdir/*

# Remove any pre-existing results files, so we can tell when they're
# recreated:
rm $gamedir/results* &>/dev/null

confdir=$gamedir/conf
[ -e $confdir ] || mkdir $confdir

if [ -r $confdir/mapname ]; then
    mapname="`cat $confdir/mapname`"
else
    mapname=Crossroads
    echo "$mapname" > $confdir/mapname
fi

if [ -r $confdir/gametype ]; then
    gametype="`cat $confdir/gametype`"
else
    gametype=wipeout
    echo "$gametype" > $confdir/gametype
fi

if [ -r $confdir/maxfp ]; then
    maxfp="`cat $confdir/maxfp`"
fi
if [ -z "${maxfp//[^0-9]/}" ]; then
    maxfp=20
    echo "$maxfp" > $confdir/maxfp
fi

if [ -r $confdir/maxturns ]; then
    maxturns="`cat $confdir/maxturns`"
fi
if [ -z "${maxturns//[^0-9]/}" ]; then
    maxturns=20
    echo "$maxturns" > $confdir/maxturns
fi


# edit Command.cfg to make the buttons do what we want
[ -e Configs/Command.cfg.bk ] || cp Configs/Command.cfg Configs/Command.cfg.bk
echo -e '/SetFP30\n+1\ns/| .*/| '$maxfp'\nwq' | ed Configs/Command.cfg >&/dev/null
echo -e '/SetTurns50\n+1\ns/| .*/| '$maxturns'\nwq' | ed Configs/Command.cfg >&/dev/null

## Automation functions

function sleephr ()
{
    # CONFME:
    # Replace with a version of sleep which accepts floating point argument if
    # 'sleep' itself doesn't
    sleep $1 
}

function click ()
{
    xte "mousemove $1 $2" "mouseclick 1"
    sleephr ${3:-0.3}
}

function type ()
{
    xte "str $1"
}

function key ()
{
    xte "key $1"
}

function OK ()
{
    # Click the OK button
    click 522 448 2
}

function startGame ()
{
    # Give LSN a few seconds to start up
    sleep 5

    ## First, click OK on an annoying dialogue about failure to "defrag sound
    ## buffers" which some versions of wine cause:
    #click 289 197 5
    #
    ## ...and/or on another about failing to create sound manager
    #click 520 400 3

    # Start a hotseat game:
    click 731 499 2

    # set gametype
    [ "$gametype" == hq ] && click 584 311

    # set gamename
    click 503 369
    for i in `seq 6`; do key BackSpace; done
    sleephr 0.5
    type "$mapname"
    sleephr 1

    #[ "$maxfp" == 15 ] && click 450 440
    #[ "$maxfp" == 25 ] && click 630 440
    #[ "$maxfp" == 30 ] && click 710 440
    #[ "$maxturns" == 20 ] && click 450 480
    #[ "$maxturns" == 40 ] && click 630 480
    #[ "$maxturns" == 50 ] && click 710 480
    click 710 440
    click 710 480

    # start game!
    click 735 605 3
}

function deploy ()
{
    # Select greys:
    click 735 605 1
    # Select warper:
    click 98 419
    # Zoom out:
    click 484 701

    deployfile="Map/$mapname.deploy"
    if [ -r "$deployfile" ]
	#&& [ $(wc -l "$deployfile" | cut -d' ' -f 1) < $((100 + (RANDOM % 1000))) ]
    then
	while read line; do $line; done < "$deployfile"
    else
	dirs=(Right Up Left Down)
	dists=(5 7 13 17)
	# Spam clicks and keyboard presses!
	for i in `seq 20`; do
	    dir=${dirs[$((RANDOM % 4))]}
	    dist=${dists[$((RANDOM % 4))]}
	    for i in `seq 5`; do
		for pos in "500 350" "500 200" "500 600" "200 350" "800 350"; do 
		    click $pos 0.02
		done
		for i in `seq $dist`; do
		    key $dir
		done
	    done
	done
    fi

    # accept deployment
    click 897 738 1

    OK
}

function doturn ()
{
    # end turn
    click 997 715 2

    OK
}


turn=0
startGame
while true; do
    # Wait for processing to complete.
    while true; do
	processed=
	for i in `seq 30`; do
	    if [ -e $gamedir/results2_G${gnum}_T$((turn)).lsn ]; then
		processed=yes
		OK
		break
	    fi
	    sleep 1
	done
	if [ -n "$processed" ]; then
	    statusfile=$gamedir/status_G${gnum}_T${turn}.lsn
	    if ! grep "gameover = t" $statusfile &>/dev/null; then
		touch $gamedir/processed_T$turn
		turn=$((turn+1))
		break
	    else
		# game over man
		grep "winner = " $statusfile |\
		    sed 's/winner = //' > $confdir/gameover
		touch $gamedir/processed_T$turn
		exit 0
	    fi
	else
	    # Processing has taken too long. This could be for a number of
	    # reasons...
	    
	    # 1: has the LSN process died for some reason?
	    lsnlives || die "LSN ($lsnpid) died unexpectedly!"
	    

	    # 2: our dummy orders weren't submitted properly (most likely due
	    # to bad luck in the deployment phase). Try again.
	    if [ $turn == 0 ]; then
		startGame
	    elif [ $turn == 1 ]; then
		deploy
	    else
		doturn
	    fi

	    # 3: it's just still processing.
	    # Note: you might worry that the actions in 2 above might cause
	    # problems were the processing to finish just after we stopped
	    # waiting for it - but in fact, if you think about it, it won't
	    # cause problems.
	    if [ -n "$RESTCPU" ]; then
		kill -STOP $lsnpid
		sleep $RESTCPU
		kill -CONT $lsnpid
	    fi
	fi
    done

    kill -STOP $lsnpid
    while true; do
	# Wait for orders files to appear:
	if [ -e $ordersdir/orders1_G${gnum}_T$((turn)).lsn ] &&\
	    [ -e $ordersdir/orders2_G${gnum}_T$((turn)).lsn ]; then
	    break
	fi
	sleep 10
	lsnlives || die "LSN ($lsnpid) died unexpectedly!"
    done
    kill -CONT $lsnpid

    # Ensure our orders are not overwritten:
    chmod -w $ordersdir/orders*_G${gnum}_T$((turn)).lsn

    # Now submit some dummy orders:
    if [ $turn == 1 ]; then
	deploy
	deploy
    else
	doturn
	doturn
    fi
done
