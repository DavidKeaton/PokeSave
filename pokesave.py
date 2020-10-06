#!/usr/bin/python3

"""
          _.:[PokeSave]:._
author: David "SuperSalsa" Keaton

usage: pokesave.py <filename>.sav

PokeSave is a save-game editor for Pokemon Silver/Gold.
    This script will open a save game file for Gen II,
    and display the contents to the user. One can then edit
    the changes and have it written back to the save file
    with the correct checksums computed so it can be used.

The editor inside allows one to not only modify raw values
    in the save file, but to easily modify the contents of
    one's bag, their party Pokemon (and their attributes),
    and the Pokemon in BILL's PC!

This program stemmed from my FRUSTRATION at having progress
    lost on an emulated run of Pokemon Gold, so don't expect
    completion past workable state. Hopefully someone else
    can find use out of this, but if not it has helped me. ;)

                    Gotta HACK 'em all!     B-)

TODO:
    x create save data memory region to be filled by parser
    x parse save file
    ! create simple UI to edit values for save file
        + finish CURSES term UI
        + ASCII art display on Windoze term w/o Cygwin
    x compute primary and secondary checksums
    - assure sync of edited byte stream back to file
    x create proprietary string encoding algorithms
    - control stream & file position
    ! associate strings in save data with str_* functions
    - allow user to change filename (no static `POKEGOLD.SAV')
    - add bitfields for save['options']
    - add parser/editor for POKEMON_* struct        (allow edit PokeManz)
    - add parser/editor for POKEMON_BOX_* struct    (allow edit PokeManz)
    - add parser/editor for items, TMs, pokeballs, key items, etc

    < some other stuff I'm sure I need to add to this list > :D
"""

import io, sys, curses, curses.ascii

# [DATA] {{{1

# [CONSTANTS] {{{2
# error codes
ERR_PIKA    = 25
ERR_FILE    = 2
ERR_FAIL    = 1
ERR_NONE    = 0

# [SIZES]
# size of options bitfield
OPTIONS_SIZE        = 8
# size of an ID field
ID_SIZE             = 2
# size of names
NAME_SIZE           = 11    # total bytes for name
REAL_NAME_SIZE      = 7     # available bytes for name
# size of the seen/owned pokedex entries
POKEDEX_SIZE        = 32
# size of pokemon structure
POKEMON_SIZE        = 0x48      # XXX: MAKE SURE THIS # IS CORRECT!
# size of the player's pokemon party
POKEPARTY_SIZE      = 428       # possibly [432], since     (432 / 0x48) == 6
# size of player's money
MONEY_SIZE          = 3
# size of bag pockets
TM_POCKET_SIZE      = 57
ITEM_POCKET_SIZE    = 42
KEY_POCKET_SIZE     = 54
BALL_POCKET_SIZE    = 26
# size of PC things
PC_ITEM_SIZE        = 102
PC_NAME_SIZE        = 126
# size of each box in BILL's PC
POKEBOX_SIZE        = 1102      # TODO: xlat into formula
# size of the checksum field
CHECKSUM_SIZE       = 2

# End Of Name (string terminator)
EON = 0x50
# End Of List (pokemon lists)
EOL = 0xFF00
# End Of Pokemon (found in pokemon_party)
EOP = (0, 0, 0,)

# bytes that follow player name field (starting @ byte 8)
PLAYER_NAME_SUFFIX  = bytes((EON, 0, 0, 0,))
# bytes that follow rival name field  (starting @ byte 8)
RIVAL_NAME_SUFFIX   = bytes((EON, 0x86, 0x91, 0x84,))

# player palette colors
PLYR_PAL_RED        = 0
PLYR_PAL_BLUE       = 1
PLYR_PAL_GREEN      = 2
PLYR_PAL_BROWN      = 3
PLYR_PAL_ORANGE     = 4
PLYR_PAL_GRAY       = 5
PLYR_PAL_DARK_GREEN = 6
PLYR_PAL_DARK_RED   = 7

# data types
TYPE_NAME       = 0     # nickname or player name as encoded string
TYPE_POKEMON    = 1     # pokemon data
TYPE_POKEBOX    = 2     # pokemon-in-PC-box data
TYPE_POKELIST   = 3     # pokemon list (i.e. party pokemon)
TYPE_STRING     = 4     # encoded string (non-name related)

# TODO: tm/hm list

# TODO: item list

# TODO: move list

# johto badges bit fields
# <---- MSB                                         LSB ---->
# Zephyr, Insect, Plain, Fog, Storm, Mineral, Glacier, Rising
BADGE_ZEPHYR    = 1 << 7
BADGE_INSECT    = 1 << 6
BADGE_PLAIN     = 1 << 5
BADGE_FOG       = 1 << 4
BADGE_STORM     = 1 << 3
BADGE_MINERAL   = 1 << 2
BADGE_GLACIER   = 1 << 1
BADGE_RISING    = 1 << 0

# frame = 1/60th of a second
TIME_FRAME      = 1.0 / 60.0

# }}}2

# [POKEMON] {{{2
# TODO: finish this struct
pokemon = {
        'species': 0x00,
} #}}}2

# [SAVE] {{{2
save = {}
# text speed, battle anims, etc
save['options'] = {
        'addr': 0x2000,
        'size': OPTIONS_SIZE,
        'val' : list()
}
# Trainer ID
save['trainer_id'] = {
        'addr': 0x2009,
        'size': ID_SIZE,
        'val' : list()
}
# player's name
save['player_name'] = {
        'addr': 0x200b,
        'size': NAME_SIZE,
        'val' : list()     # uses str_encode/str_decode
}
# rival's name
save['rival_name'] = {
        'addr': 0x2021,
        'size': NAME_SIZE,
        'val' : list()     # uses str_encode/str_decode
}
# daylight savings
save['dst'] = {
        'addr': 0x2037,
        'size': 1,
        'val' : list()
}
# time played
save['time_played'] = {
        'addr': 0x2053,
        'size': 4,
        'val' : list()
}
# player's sprite palette (?)
save['player_palette'] = {
        'addr': 0x206b,
        'size': 1,
        'val' : list()
}
# $$$ DOLLA DOLLA BILLS Y'ALL $$$
save['money'] = {
        'addr': 0x23db,
        'size': MONEY_SIZE,
        'val' : list()
}
# amount of badges earned in Johto
save['johto_badges'] = {
        'addr': 0x23e4,
        'size': 1,
        'val' : list()
}
# TMs in bag pocket
save['tm_pocket'] = {
        'addr': 0x23e6,
        'size': TM_POCKET_SIZE,
        'val' : list()
}
# items in bag pocket
save['item_pocket'] = {
        'addr': 0x241f,
        'size': ITEM_POCKET_SIZE,
        'val' : list()
}
# key items in bag pocket
save['key_item_pocket'] = {
        'addr': 0x2449,
        'size': KEY_POCKET_SIZE,
        'val' : list()
}
# PokeBalls (TM) in bag pocket
save['ball_pocket'] = {
        'addr': 0x2464,
        'size': BALL_POCKET_SIZE,
        'val' : list()
}
# PC stored items
save['pc_items'] = {
        'addr': 0x247e,
        'size': PC_ITEM_SIZE,
        'val' : list()
}
# current PC box number
save['pc_box_current'] = {
        'addr': 0x2724,
        'size': 1,
        'val' : list()
}
# names of PC boxen
save['pc_box_names'] = {
        'addr': 0x2727,
        'size': PC_NAME_SIZE,
        'val' : list()
}
# party pokemon     (see POKEMON_* struct)
save['pokemon_party'] = {
        'addr': 0x288a,
        'size': POKEPARTY_SIZE,
        'val' : list()
}
# PokeDex (TM) entries owned
save['pokedex_owned'] = {
        'addr': 0x2a4c,
        'size': POKEDEX_SIZE,
        'val' : list()
}
# PokeDex (TM) entries seen
save['pokedex_seen'] = {
        'addr': 0x2a6c,
        'size': POKEDEX_SIZE,
        'val' : list()
}
# pokemon in BILL's PC (current box)        (see POKEMON_BOX_* struct)
save['pokemon_cur_box'] = {
        'addr': 0x2d6c,
        'size': POKEBOX_SIZE,
        'val' : list()
}
# ------------------
# sure, it's "redundant," but initialization 
# of a `dict' preserves the proper order of
# its pieces, and checksum needs to be last
# ------------------
# Box 1
save['pokemon_box_1'] = {
        'addr': 0x4000,
        'size': POKEBOX_SIZE,
        'val' : list()
}
# Box 2
save['pokemon_box_2'] = {
        'addr': 0x4450,
        'size': POKEBOX_SIZE,
        'val' : list()
}
# Box 3
save['pokemon_box_3'] = {
        'addr': 0x48a0,
        'size': POKEBOX_SIZE,
        'val' : list()
}
# Box 4
save['pokemon_box_4'] = {
        'addr': 0x4cf0,
        'size': POKEBOX_SIZE,
        'val' : list()
}
# Box 5
save['pokemon_box_5'] = {
        'addr': 0x5140,
        'size': POKEBOX_SIZE,
        'val' : list()
}
# Box 6
save['pokemon_box_6'] = {
        'addr': 0x5590,
        'size': POKEBOX_SIZE,
        'val' : list()
}
# Box 7
save['pokemon_box_7'] = {
        'addr': 0x59e0,
        'size': POKEBOX_SIZE,
        'val' : list()
}
# Box 8
save['pokemon_box_8'] = {
        'addr': 0x6000,
        'size': POKEBOX_SIZE,
        'val' : list()
}
# Box 9
save['pokemon_box_9'] = {
        'addr': 0x6450,
        'size': POKEBOX_SIZE,
        'val' : list()
}
# Box 10
save['pokemon_box_10'] = {
        'addr': 0x68a0,
        'size': POKEBOX_SIZE,
        'val' : list()
}
# Box 11
save['pokemon_box_11'] = {
        'addr': 0x6cf0,
        'size': POKEBOX_SIZE,
        'val' : list()
}
# Box 12
save['pokemon_box_12'] = {
        'addr': 0x7140,
        'size': POKEBOX_SIZE,
        'val' : list()
}
# Box 13
save['pokemon_box_13'] = {
        'addr': 0x7590,
        'size': POKEBOX_SIZE,
        'val' : list()
}
# Box 14
save['pokemon_box_14'] = {
        'addr': 0x79e0,
        'size': POKEBOX_SIZE,
        'val' : list()
}
save['checksum'] = ({
# Checksum 1    (primary save)
        'addr':     0x2d69,     # addr to store in
        'chunk':    (           # (pseudo-) tuple of areas to compute
            {'start': 0x2009, 'end': 0x2d68},
        ),
        'size':     CHECKSUM_SIZE,
        'val':      list(),
    },{
# Checksum 2    (secondary save)
#   (this has 3 areas that need summed into one addr)
        'addr':     0x7e6d,     # addr to store in
        'chunk':    (           # tuple of areas to compute
            {'start': 0x0c6b, 'end': 0x17ec},
            {'start': 0x3d96, 'end': 0x3f3f},
            {'start': 0x7e39, 'end': 0x7e6c},
        ),
        'size':     CHECKSUM_SIZE,
        'val':      list(),
},) # }}}2

# [FILE/STREAM] {{{2
# positions and addresses for current stream cursor, base/offset, etc
pos = {
        'base':     0x2000, # base addr (for abs->rel & rel->abs compute)
        'offset':   0x0000, # (current_addr) - (base)
        'stream':   0x0000, # current stream pos
        'file':     0x0000, # current file pos
# current = base + (offset - 0x2000)    (???)
} # }}}2

# [ASCII] {{{2
# ASCII => hex lookup table
ascii_hex = { # {{{3
        '?': 0x3F,
        '[': 0x5B,
        ']': 0x5D,
        '(': 0x28,
        ')': 0x29,
        '_': 0x5F,
        #'Ä': 0x00,
        #'Ö': 0x00,
        #'Ü': 0x00,
        #'ä': 0x00,
        #'ö': 0x00,
        #'ü': 0x00,
# TODO: still need to fill in values and add more!
} # }}}3

# special PKMN character lookup table
special_char = { # {{{3
        # unown char    D:
        0x00: '?',

        # spaces
        0xBA: ' ',
        0xBB: ' ',
        0xBC: ' ',
        0xBD: ' ',
        0xBE: ' ',
        0xBF: ' ',

        0x60: '       ', # tab?
        0x61: '▲',
        0x6E: 'ぃ',
        0x6F: 'ぅ',

        0x70: 'PO',
        0x71: 'Ké',
        0x72: '“',
        0x73: '”',
        0x74: '・',
        0x75: '…',
        0x76: 'ぁ',
        0x77: 'ぇ',
        0x78: 'ぉ',

        0x9A: '(',
        0x9B: ')',
        0x9C: ':',
        0x9D: ';',
        0x9E: '[',
        0x9F: ']',

        0xC0: 'Ä',
        0xC1: 'Ö',
        0xC2: 'Ü',
        0xC3: 'ä',
        0xC4: 'ö',
        0xC5: 'ü',

        0xD0: '\'d',
        0xD1: '\'l',
        0xD2: '\'m',
        0xD3: '\'r',
        0xD4: '\'s',
        0xD5: '\'t',
        0xD6: '\'v',
        #0xDF: '←', # only in crystal

        0xE1: 'PK',
        0xE2: 'MN',
        0xE3: '-',
        0xE6: '?',
        0xE7: '!',
        0xE8: '.',
        0xE9: '&',
        0xEA: 'é',
        #0xEB: '→', # only in crystal
        0xEC: '▷',
        0xED: '▶',
        0xEE: '▼',
        0xEF: '♂',

        0xF1: '×',
        0xF3: '/',
        0xF5: '♀',
} # }}}3
# }}}2

# [UI] {{{2

# global curses window handle
window = None

# XXX: <DEPRECATED>
# dimensions we would LIKE to have
#LINES   = 50
#COLS    = 80

# UI mode constants
MODE_DISPLAY    = 0
MODE_EDIT       = 1
# current viewport details
view = {
        'mode':     MODE_DISPLAY, # current UI MODE_
        'index':    0,  # index of chosen field
        'y':        0,  # current y position
        'x':        0,  # current x position
        'top':      0,  # top line displayed
        'bottom':   0,  # bottom line displayed
        'left':     0,  # left-most column displayed
        'right':    0,  # right-most column displayed
        'height':   0,  # height of the curses window
        'width':    0,  # width of the curses window
}
# sub-window details (more-or-less a clone of `view')
subview = {
        'y':        0,  # current y position
        'x':        0,  # current x position
        'top':      0,  # top line displayed
        'bottom':   0,  # bottom line displayed
        'left':     0,  # left-most column displayed
        'right':    0,  # right-most column displayed
        'height':   0,  # height of the curses window
        'width':    0,  # width of the curses window
}
# escape sequences
ESC_SEQ = {
        # arrows
        'UP':       (91, 65,),
        'LEFT':     (91, 68,),
        'DOWN':     (91, 66,),
        'RIGHT':    (91, 67,),
        # Fn
        'F10':      (91, 50,),
}
# key types
KEY_TYPE_TEXT   = 0 # ([A-Za-z0-9]|[?!.,-'"@$])
KEY_TYPE_MOVE   = 1 # ^ v < >
KEY_TYPE_CTRL   = 2 # ENTER, 'q'uit
# key movement codes
KEY_UP          = 0
KEY_LEFT        = 1
KEY_DOWN        = 2
KEY_RIGHT       = 3
# key control codes
KEY_NONE        = 0 # special: "continue processing"
KEY_HALT        = 1 # special: "stop processing"
KEY_ENTER       = 2 # change MODE_ values || write new data value
KEY_ESCAPE      = 3 # go back a screen
KEY_QUIT        = 4 # quit the program
# key action template (NOTE: has no purpose but to document structure)
key_action = {
        'type':     0,  # a KEY_TYPE_
        'key':      0,  # string repr || key code
}
# color constants
COLOR_GRAY  = 9
# 'UI element': color_pair
colors = {  # TODO: give actual values
        'label': {
            'n':  1,    # COLOR_PAIR '#'
            'fg': curses.COLOR_WHITE,
            'bg': curses.COLOR_BLACK,
        },
        'edit': {
            'n':  2,    # COLOR_PAIR '#'
            'fg': curses.COLOR_YELLOW,
            'bg': curses.COLOR_BLUE,
        },
}
# }}}2
# }}}1

# [FUNCTIONS] {{{1
"""
checksum(stream)
    stream      := "bytes-like" data stream

returns:    computed checksum as integer

Compute checksum for given chunk of memory in `stream'
"""
def checksum(stream): # {{{2
    n = 0
    for b in stream:
        n += b
    return n
# }}}2

"""
parse(stream)
    stream      := "bytes-like" data stream (opened via `io.FileIO')

returns:    ???

Parses the given stream for data to fill associative map `save' with.
"""
def parse(stream): # {{{2
    # start iteration thru segments (keys)
    for k in save.keys():
        # we don't need to worry about the old checksums, so skip
        if k is 'checksum':
            continue
        # get addresses for mem splicing
        start   = save[k]['addr']
        end     = start + save[k]['size']
        # store its value in its place
        save[k]['val'] = list(stream[start:end])
    return
# }}}2

"""
get_input()

returns:    `key_action' struct (see DATA-UI)

Translates input from CURSES into apropos action{} for internal parsing.
"""
def get_input(): # {{{2
    # pop 3 characters from stack, as the
    # arrows and Fn keys are escape sequences
    # NOTE: this may just be a linux thing...
    ch = (window.getch(), window.getch(), window.getch())

    # translate curses key into internal action
    action = None

# CONTROL KEYS
    # since we are in no-delay mode, -1 means no input is ready
    if ch[0] == curses.ERR:     # curses.ERR == -1
        action = {'type': KEY_TYPE_CTRL, 'key': KEY_NONE}
    # ENTER key
    elif ch[0] == curses.ascii.CR:  # '\r'
        action = {'type': KEY_TYPE_CTRL, 'key': KEY_ENTER}
    # ESC or escape sequence?
    elif ch[0] == curses.ascii.ESC:
        # ESC key
        if ch[1] == curses.ERR:
            action = {'type': KEY_TYPE_CTRL, 'key': KEY_ESCAPE}
        # escape sequences
        else:
            # time to quit?
            if ch[1:] == ESC_SEQ['F10']:
                action = {'type': KEY_TYPE_CTRL, 'key': KEY_HALT}
# MOVEMENT KEYS
            # UP arrow
            elif ch[1:] == ESC_SEQ['UP']:
                action = {'type': KEY_TYPE_MOVE, 'key': KEY_UP}
            # LEFT arrow
            elif ch[1:] == ESC_SEQ['LEFT']:
                action = {'type': KEY_TYPE_MOVE, 'key': KEY_LEFT}
            # DOWN arrow
            elif ch[1:] == ESC_SEQ['DOWN']:
                action = {'type': KEY_TYPE_MOVE, 'key': KEY_DOWN}
            # RIGHT arrow
            elif ch[1:] == ESC_SEQ['RIGHT']:
                action = {'type': KEY_TYPE_MOVE, 'key': KEY_RIGHT}
# TEXT KEYS
    # chances are whatever is left over is text
    else:
        action = {'type': KEY_TYPE_TEXT, 'key': ch[0]}

    # return translated key
    return action
# }}}2

"""
ui_loop()

Updates view intelligently based on current mode.

This function will get user input and handle
`key_action' returned per MODE_* (see DATA-UI).

Handles drawing/refresh of CURSES window as well.
"""
def ui_loop(): # {{{2
    # global window instance
    global window
    # run until the wheels fall off
    while True:
        # begin by writing info to the window
        #prep_display()
        # get input as an action
        action = get_input()

        # store the old field index
        index = view['index']

        # check some important control keys first
        if action['type'] == KEY_TYPE_CTRL:
            # nothing to process
            if action['key'] == KEY_NONE:
                continue
            # wheels fell off!
            elif action['key'] == KEY_HALT:
                break
# DISPLAY MODE
        if view['mode'] == MODE_DISPLAY:
            # CONTROL
            if action['type'] == KEY_TYPE_CTRL:
                # go to edit screen
                if action['key'] == KEY_ENTER:
                    view['mode'] = MODE_EDIT
            # MOVEMENT
            elif action['type'] == KEY_TYPE_MOVE:
                # we only care about up and down arrows
                if action['key'] == KEY_UP:
                    # make sure we don't go too far up
                    if view['index'] > 0:
                        view['index'] -= 1
                    else:
                        view['index'] = 0
                elif action['key'] == KEY_DOWN:
                    # make sure we don't go too far down
                    if view['index'] < (len(save.keys()) - 1):
                        view['index'] += 1
                    else:
                        view['index'] = (len(save.keys()) - 2)
# EDIT MODE
        elif view['mode'] == MODE_EDIT:
            # CONTROL
            if action['type'] == KEY_TYPE_CTRL:
                # go back to display, disregard changes
                if action['key'] == KEY_ESCAPE:
                    view['mode'] = MODE_DISPLAY
                    # TODO: DISREGARD CHANGES
                # go back to display, save any changes
                elif action['key'] == KEY_ENTER:
                    view['mode'] = MODE_DISPLAY
                    # TODO: SAVE CHANGES
            # MOVEMENT
            elif action['type'] == KEY_TYPE_MOVE:
                # UP/DOWN change position of multi-line cursor
                if action['key'] == KEY_UP:
                    # don't go too far up (if we can even move)
                    if subview['y'] > 0:
                        subview['y'] -= 1
                    else:
                        subview['y'] = 0
                elif action['key'] == KEY_DOWN:
                    # don't go too far down (if we can even move)
                    if subview['y'] < (subview['height'] - 1):
                        subview['y'] += 1
                    else:
                        subview['y'] = (subview['height'] - 1)
                # LEFT/RIGHT change position of cursor
                elif  action['key'] == KEY_LEFT:
                    # don't go too far left (if we can even move)
                    if subview['x'] > 0:
                        subview['x'] -= 1
                    else:
                        subview['x'] = 0
                elif  action['key'] == KEY_RIGHT:
                    # don't go too far right (if we can even move)
                    if subview['x'] < (subview['width'] - 1):
                        subview['x'] += 1
                    else:
                        subview['x'] = (subview['width'] - 1)
            # TEXT
            elif action['type'] == KEY_TYPE_TEXT:
                # TODO: determine INSERT vs OVERWRITE
                # TODO: change value(s) to text inserted
                pass
        # TODO: update viewports from index or coordinate changes
        # TODO: update display with new values or new viewport position

# FIXME: this does not work, need more complex checks to determine
#           whether or not the screen space will be scrolled
        # amount to scroll screen
        lines = 0
        # did it scroll up?
        if index < view['index']:
            lines = 1
        # did it scroll down?
        elif index > view['index']:
            lines = -1

# FIXME: unable to use if setscrreg() isn't working!
        # scroll the screen (if needed)
        #window.scroll(lines)

        # prep entire window for redraw
        window.touchwin()
        # redraw that window, holmes
        window.refresh()
    return
# }}}2

"""
prep_display()

Prepare the window with the data to be displayed.
"""
def prep_display(): # {{{2
# TODO: BASE WHAT TO START WRITING AND WHEN TO STOP ON VIEWPORT TOP/BOTTOM

    # save my wrists pls
    global window
    w = window
    LINES = view['height']
    COLS = view['width']

    # determine the tabstop string in save.keys() before-hand
    tabstop = 0
    #       TODO: optimize this to be in iteration loop
    # this can be done by writing labels, going to 0, then writing values!
    for k in save.keys():
        if tabstop < len(k):
            tabstop = len(k)

    # make sure the cursor is in the upper-left position
    w.move(0, 0)
    # zero out positional vars
    y, x = w.getyx()

    # iterate through the save's data
    for k in save.keys():
        # last entry is checksum, so...
        if k is 'checksum':
            # ...AUTOBOTS - ROLL OUT!
            break

        # print the label field
        try:
            # set label attributes
            a = curses.color_pair(colors['label']['n']) | curses.A_NORMAL
            w.attron(a)
# FIXME:    if(x - len(str) >= COLS) --> BAIL
            # label is simply the key
            w.addstr(k)
            w.attroff(a)
        # yoinks! error occurred!
        except curses.error as e:
            # TODO: output to debug log or something
            sys.stderr.write("[LABEL]: " + str(e) + '\n')
            return None

        # determine how much to move the cursor
        y, x = w.getyx()

        ## let's use tabstop of 8
        #ts = (x % 8)
        #if ts == 0:
            #ts = 8

        # indent to where we want the edit field
        w.move(y, x + (tabstop - len(k)) + 1)

        # determine what `value' is
        value = None
        # size of the field determines a lot...
        size = save[k]['size']
        # is it the options bytes?
        if size == OPTIONS_SIZE:
            # TODO: make these ellipses, or just display the options?
            value = "<OPTIONS>"
        # TODO: is it an ID?
        elif size == ID_SIZE:
            pass
        # is it an encoded string?
        elif size == NAME_SIZE:
            value = str_decode(save[k]['val'])
        # TODO: is it the player's money?
        elif size == MONEY_SIZE:
            pass
        # TODO: is it the bag's TM pocket?
        elif size == TM_POCKET_SIZE:
            pass
        # TODO: is it the bag's ITEM pocket?
        elif size == ITEM_POCKET_SIZE:
            pass
        # TODO: is it the bag's KEY ITEM pocket?
        elif size == KEY_POCKET_SIZE:
            pass
        # TODO: is it the bag's BALL pocket?
        elif size == BALL_POCKET_SIZE:
            pass
        # TODO: is it the POKEDEX fields?
        elif size == POKEDEX_SIZE:
            pass
        # is it a Pokemon?
        elif size == POKEMON_SIZE:
            value = "<POKeMON>"
        # TODO: is it the player's party?
        elif size == POKEPARTY_SIZE:
            pass
        # TODO: is it the items in PC storage?
        elif size == PC_ITEM_SIZE:
            pass
        # TODO: is it PC box names?
        elif size == PC_NAME_SIZE:
            pass
        # is it a Bill's PC Box?
        elif size == POKEBOX_SIZE:
            value = "<POKeBOX>"
        elif size == 0:
            pass
        # raw bytes = raw attitude
        else:
            value = str(save[k]['val'])
            # ellipses are fancy and mean more data
            #value = "<...>"

        # amount of lines the data wraps
        wrap = 0

        # now that we have the value to print, MAKE IT SO!
        try:
# FIXME:    if(length test) --> blah blah
            # enable attributes for edit field
            a = curses.color_pair(colors['edit']['n']) | curses.A_BOLD
            w.attron(a)
            # get current coordinates for wrap math
            y, x = w.getyx()
            # how many times does the data wrap?
            wrap = int((len(value) + x) / COLS)
            if (y + wrap) >= LINES:
                value = "<...>"
            # write the value out, and disable attributes
            w.addstr(value)
            w.attroff(a)
        # an error occurred! D:
        except curses.error as e:
            # TODO: output to debug log or something
            sys.stderr.write("[EDIT]: " + str(e) + '\n')
            return None
        # figure out how much exactly to move
        y, x = w.getyx()
        #if value is "<...>":
            #y += 1
        #else:
            ## determine if move is valid
            #y = y + wrap + 1
        if (y + 1) >= LINES:
            # uh-oh, moving past end of window...
            y = LINES - 1
        # cooool, now we advance a line (or n lines)
        w.move(y + 1, 0)
        # get updated positions
        y, x = w.getyx()

    # mark window for redraw
    w.noutrefresh()
    # place the cursor back at the start
    w.move(0, 0)
    # zero-out the cursor's position
    view['y'], view['x'] = w.getyx()
    # mark window for redraw
    curses.doupdate()
    # all done!
    return
# }}}2

"""
display(stream)
    stream      := "bytes-like" data stream

returns:    ???

Displays the save-data parsed earlier for the user to peruse.
Encapsulated inside is the UI subsystem startup and UI main loop.

TODO:
    - PC items
    - item bag
    - party pokemon
    - PC pokemon
"""
def display(stream): # {{{2
    # make sure the curses subsystem has been started
    curses_init()

    # (re-)initialize viewport information
    view['mode']    = MODE_DISPLAY
    view['index']   = 0
    #view['height']  = LINES
    #view['width']   = COLS
    # begin by writing info to the window
    prep_display()
    # enter UI loop, and it will guide us...ohm...
    ui_loop()

    return None
# }}}2

"""
edit(stream)
    stream      := "bytes-like" data stream

returns:    a new data stream with user-made changes

Prepares and presents the given data stream for user-made changes.

TODO:
    - decide on UI (curses, printf, etc) ?
    - display save-data
    - implement editor for RAW stuff
    - add editors for items, pc, pokemon, etc
"""
# TODO: IS THIS EVEN NEEDED? PROBS NOT - AS IS HANDLED IN `display()'
def edit(stream): # {{{2
    # create the new bytes-like that will store the changes
    new = stream

    # TODO: display save-data and allow editing

    # return the new (or old) data stream
    return new
# }}}2

"""
validate(stream)
    stream      := "bytes-like" data stream

returns:    a new data stream with changes

Computes primary and secondary checksums from data provided in `stream'.
"""
def validate(stream): # {{{2
    # store fixes in list...
    new = list(stream)
    # dynamically determine and compute checksums
    for cs in save['checksum']:
        # where result is stored
        dest = cs['addr']
        # list of results
        r = list()
        # iterate thru chunks
        for chunk in cs['chunk']:
            # each memory chunk has a start and an end
            r.append(checksum(stream[chunk['start']:chunk['end']]))
        # now add up all the checksums computed for this `chunk'
        x = 0
        for i in r:
            x += i
        # cut off anything longer than 2 bytes
        x = x & 0xffff
        # splice for insertion
        temp = new[:dest]
        # now store the resulting calculation "little-endian" style
        temp.append(x & 0x00ff)
        temp.append((x & 0xff00) >> 8)
        # slap in the rest of the stream...
        temp += new[dest+2:]
        # store changes
        new = temp
        del temp
    return bytes(new)
# }}}2

"""
sync(stream, fd)
    stream      := "bytes-like" data stream
    fd          := file descriptor opened via `io.FileIO'

returns:    True if no problems arised, all hunky-dory
            False if file errors or other silly nonsense occurred

Synchronizes any changes made by the user back to the save file.

TODO:
    - write changes back to file
"""
def sync(stream, fd): # {{{2
    # TODO: write changes in `stream' back to `fd'
    #fd.write(stream)

    # flush changes
    fd.flush()
    # close file handle
    fd.close()
    # XXX: return whether there were any file errors?
    return True
# }}}2

"""
str_encode(mem)
str_decode(mem)
    mem     := "bytes-like" data stream

returns:    str_encode() => encoded string
            str_decode() => decoded string

These two functions convert a PKMN proprietary string
    back and forth into its ASCII equivalent.

UPPER:    [0x41, 0x5a]    ==> PKMN: [$80, $99]
lower:    [0x61, 0x7a]    ==> PKMN: [$A0, $B9]
numbers:  [0x30, 0x39]    ==> PKMN: [$F6, $FF]
specials: <see lookup table `special_char' below>
"""

def str_encode(mem): # {{{2
    # turn bytes into a list
    new = list()
    # ZOOOOOM
    for c in mem:
        # xlat char
        x = 0x00
        # UPPER
        if c in range(0x41, 0x5A):
            x = (c - 0x41) + 0x80
        # lower
        elif c in range(0x61, 0x7A):
            x = (c - 0x61) + 0xA0
        # numbers
        elif c in range(0x30, 0x39):
            x = (c - 0x30) + 0xF6
        # special char?
        else:
            # is it in the list of values?
            v = special_char.values()
            k = special_char.keys()
            for i in range(0, len(v)):
                # get the key from its value
                if v[i] is c:
                    x = k[i]
                    break
        # append to end of list
        new.append(x)
    # turn list back into byte array
    return bytes(new)
# }}}2

def str_decode(mem): # {{{2
    # turn bytes into a list
    new = list()
    # VWOOSH
    for c in mem:
        x = 0x00
        # UPPER
        if c in range(0x80, 0x99):
            x = (c - 0x80) + 0x41
        # lower
        elif c in range(0xA0, 0xB9):
            x = (c - 0xA0) + 0x61
        # numbers
        elif c in range(0xF6, 0xFF):
            x = (c - 0xF6) + 0x30
        # terminator or null?
        elif c is 0x50 or c is 0x00:
            break
        # special char? use lookup table!
        else:
            x = special_char.get(c, 0x7E) # '~'
            continue
        # plop it onto the end
        new.append(x)
    # iterate through the list and turn any ASCII into raw hex
    for c in new:
        # is the current character ASCII?
        continue

    # WHIZZ BANG! KABLOOWIE!
    # Have some bytes!  B-)
    return bytes(new)
# }}}2

# TODO: -----------------------------------------
# TODO: turn these into biderectional, or classes
# TODO: -----------------------------------------

"""
Translate 3 byte money field into readable number
"""
def money_encode(data): # {{{2
    return
# }}}2
def money_decode(data): # {{{2
    return
# }}}2

"""
Translate 4 byte time data into readable number
"""
def time_encode(data): # {{{2
    return
# }}}2
def time_decode(data): # {{{2
    return
# }}}2

"""
Translate game settings
"""
def options_encode(data): # {{{2
    return
# }}}2
def options_decode(data): # {{{2
    return
# }}}2

"""
Translate pokeparty into individual pokemon
"""
def pokeparty_encode(data): # {{{2
    return
# }}} 2
def pokeparty_decode(data): # {{{2
    return
# }}}2

"""
key2index(struct, key)
    struct  := `dict' to search
    key     := key to find in `struct'

returns:    index of struct[key]

Computes and returns an "index" from `struct[key]`

Since `dict' (python >= 3.x) guarantees sequential and contiguous
    data placement, this should be considered as pointing to the
    same region of said `dict'.
"""
def key2index(struct, key): # {{{2
    # position of key -> struct
    index = 0
    # iterate through structure looking for key
    for i in struct.keys():
        if i == key:
            break
        index += 1
    # did we find what we were looking for?
    if index == len(struct):
        # nope, tell caller that
        return None
    # found it!
    return index
# }}}2

"""
index2key(struct, index)
    struct  := `dict' to search
    index   := index into array of `struct'

returns:    key for which index points to, or None if NOT found!

Computes and returns the key from which `struct(index)' was derived.
"""
def index2key(struct, index): # {{{2
    # iteration var
    i = 0
    # walk thru keys
    for k in struct.keys():
        # is this the spot?
        if i == index:
            # nice! found it!
            return k
        # moving on...
        i += 1
    # no bueno :(
    return None
# }}}2

"""
lsplit(l, delim)
    l       := list to split
    delim   := delimiter to split on

returns:    list of chunked lists

Split a list based on a delimiter, and return the new list in chunks.
i.e.
    lsplit( (a, b, 0, 0, c,), (0, 0,) )     =>  list( (a, b, ), (c, ) )
"""
# TODO: make sure this BLACK MAGIC works correctly
def lsplit(l, delim): # {{{2
    # delimited list
    new = list()
    # start of range for a list entry
    index = 0
    # iterate entry by entry
    for i in range(0, len(l)):
        # did we find the delimiter?
        if l[i:(i+len(delim))] == delim:
            # add l[index:i-1] to the list
            new.append(l[index:i-1])
            # make note of the new index
            index = i + len(delim)
            # jump to new start position of next list element
            i = index
    return new
# }}}2

"""
shutdown(code=ERR_NONE, msg=None)
    code    := error code to return to calling env
    msg     := error message to print (iff code != 0)

Shutdown all open subsystems, file handles, and caches/mem.
Exit with `code' (defaults to 0 - no error) and display `msg'
    if given a non-zero error code.

NOTE:       THIS WILL EXIT THE PROGRAM!!

TODO:
    - clean-up file handles (espec. if ERR)
    - clean-up alloc'd mem or caches (espec. if ERR)
"""
def shutdown(code=ERR_NONE, msg=None): # {{{2
    # make sure curses has shutdown
    curses_close()
    # if error present, print message
    if code is not ERR_NONE:
        print("err [{}]: {}", code, msg)

    # ...time for us to blow this popsicle stand...
    sys.exit(code)
    # this should never be reached
    return
# }}}2

"""
usage()

Displays program usage information.
"""
def usage(): # {{{2
    # TODO: something something print stuff or w/e
    return
# }}}2

"""
curses_init()

returns:    True if successful, False otherwise

Initialize and set-up post-init options.

TODO:
    - error check init/options set
    - fix terminal restoration bug
"""
def curses_init(): # {{{2
    # make sure we store to the global window instance
    global window
    # initialize curses system
    try:
        window = curses.initscr()
    except curses.error as e:
        # no bueno! D:
        sys.stderr.write("[curses.initscr(): " + str(e) + '\n')
        return False
    # double check our `window' object
    if window is None or window is 0:
        # initialization has failed!
        return False
# FIXME: fix terminal restoration bug on exit
    # save user's TTY setup
    curses.savetty()
    curses.def_shell_mode()
    # pause for PIKACHU effect (continues on key press)
    window.timeout(-1)
    # NL/LF interpreted by program
    curses.nonl()
    # don't echo input
    curses.noecho()
    # `rare' mode
    curses.cbreak()
    # start color mode
    curses.start_color()
    # set up custom color pairs
    if curses.can_change_color():
        # create gray color
        curses.init_color(COLOR_GRAY, 127, 127, 127)
    # initialize label and edit field COLOR_PAIRs
    for c in colors.keys():
        curses.init_pair(colors[c]['n'],
                         colors[c]['fg'],
                         colors[c]['bg'])
    
    # resize the window
    #window.resize(LINES, COLS)

    # get the window size
    view['height'], view['width'] = window.getmaxyx()

# FIXME: this still bugs out for some reason...
    # set up the scrolling region
    #try:
        #window.setscrreg(0, LINES)
    #except curses.error as e:
        #sys.stderr.write(str(e))
    
    # if curses doesn't resize our window, do it ourselves
    ##if curses.is_term_resized(LINES, COLS) is False:
        # resize the window to match term size
        ##window.resize(LINES, COLS)
    # attempt to resize the terminal
    ##curses.resizeterm(LINES, COLS)

# FIXME: use getyx() or something to assure these dims are correct
    # set the window cursor to the upper-left cell of the screen
    curses.setsyx(0, 0)
    window.move(0, 0)
    
    # create display pad
    ##pad['h'] = curses.newpad(pad['L'], pad['C'])
    # set the scrolling region (for scroll fn's)
    ##pad['h'].setscrreg(0, pad['L'])
    # not okay to keep scrolling on some input
    ##pad['h'].scrollok(False)
    # set pad cursor to upper-left
    ##pad['h'].move(0, 0)
    
    # set cursor type   -   `[]`
    curses.curs_set(2)
    # cause non-blocking input buffer
    window.nodelay(True)
    # set the background character
    window.bkgdset(' ')
    # clear the screen
    window.clear()
    # update screen
    window.refresh()
    # DO IT TO IT!
    return window
# }}}2

"""
curses_print_field()
    struct  := data structure (`dict') to gather from
    key     := struct[key]   \_
    index   := struct(index) / '(EQUIVALENCE)

    ,--(maybe string instead?)
returns:    True if successful
            False if encountered error (like a missing key/index)

Gathers information about the given field inside
    of `struct' and prints it to a CURSES window. 
"""
# FIXME: IS THIS THING EVEN GONNA BE USED?
def curses_print_field(struct, key=None, index=None): # {{{2
# XXX: have this return a string? `*_prep_field()' ?
#      or have this `*_print_field()' ? needs `y, x, win' args, too
    # determine argument sanity
    if (struct is None) or (key is None and index is None):
        return False
    # gather information about field to be printed
    label   = key
    edit    = None
# TODO: raise `KeyError' or `IndexError' if not present in `struct'
#           instead of returning False
    # key of field
    k = None
    # field via key...
    if key is not None and key in struct:
        # key is present in struct
        k = key
    #...or index
    elif index is not None:
        # xlat key from index
        k = index2key(struct, index)
    # IS THE KEY EVEN REAL?!
    if k is None:
        if key is None:
            raise IndexError
        elif index is None:
            raise KeyError
    # ...well I _guess_ it passes the test...
    label   = k
    edit    = save[k]['val']
# }}}2

"""
curses_close()

returns:    True if success,
            False otherwise

Restore prior state of terminal before CURSES was started,
    and shut down CURSES subsystem.

TODO:
    ! fix TTY restoration bug
    - err check shutdown
"""
def curses_close(): # {{{2
    # have we already shut down?
    if curses.isendwin() is True:
        # yep! alert the user that we have
        # NOTE: may not want to return False?
        return False
# FIXME: this is currently NOT working, need to manually `reset'
    # restore user's TTY setup
    curses.reset_shell_mode()
    curses.resetty()
    # undo our options
    curses.nl()
    curses.echo()
    curses.nocbreak()
    # close curses system
    curses.endwin()
    # signal no UI
    window = None
    # A-OKAY HERE BOSS!
    return True
# }}}2

"""
stringify_edit_field(text, n)
    text    := text to place in field
    n       := maximum bytes allowed

returns:    a new string post fix-up

Prepares a string to be placed into an edit field.
    i.e. "SALSA CON QUESO" => "[__SALSA CON QUESO__]"
"""
# FIXME: IS THIS EVEN GONNA BE USED?
def stringify_edit_field(text, n): # {{{2
    # new string created for edit field
    new = None
# TODO: compute size of stringified stuff
    # `n' will be the amount of characters available to us
    #size = n
    # "[" and "]"
    #size -= 2
# XXX: for now, just basic-it-up
    l = len(text)
    # would it go over the amount?
    if (l + 6) > n:
        # truncate rest of string
        new = text[:l - 6]
    # stringify
    new = "[__{}__]".format(new)
    return new
# }}}2

"""
get_data_type(struct, key)
    struct  := x
    key     := x

returns:    the type of data as TYPE_* constant

Using characteristics of the field (struct[key]) in question,
    determine the type of field referenced.
"""
# FIXME: IS THIS EVEN GONNA BE USED?
def get_data_type(struct, key): # {{{2
# TODO: validate params and key-existence
    # the type of data referenced
    data_type = None
    # get the size of the object
    size = struct[key]['size']
    # size can tell us a few things...
    if size == NAME_SIZE:
        # player, rival, nick-name
        data_type = TYPE_NAME
# XXX: the next two checks _could_ be ambiguous
    elif size == POKEMON_SIZE:
        # Pokemon data structure
        data_type = TYPE_POKEMON
    elif size == POKEBOX_SIZE:
        # Pokemon-in-PC data structure
        data_type = TYPE_POKEBOX
    else:
# TODO: elaborate tricks to determine if POKELIST
        pass
    # report type (or None if not found)
    return data_type
# }}}2

"""
Pause until ENTER key is pressed. Pretty rudimentary.
"""
def pause(): # {{{2
    sys.stdin.read(1)
    return
# }}}2

"""
Draw some dope ASCII art!   B-)
"""
def ascii_art(): # {{{2
# pikachu.ascii, gameboy.ascii
    # NOTE: p sure this won't work on Windoze, unless Cygwin
    fname = "pikachu.ascii"
    try:
        # print fancy ascii art!    :D
        art = open(fname)
        print(art.read())
        art.close()
        # pause for PIKAffect!
        # XXX: either have it display "Press Enter" or any key works
        #           (right now, only enter is acceptable)
        pause()
    except FileNotFoundError:
        # no fancy art...           :'(
        #print("unable to send out Pikachu :(")
# FIXME: for now, if unable to print Pikachu, FAIL HARDCORE
        shutdown(ERR_PIKA, "unable to send out Pikachu! :(")
    return
# }}}2
# }}}1

"""
main()

Program entry point.
"""
# [MAIN] {{{1
# print program info
fancy_e     = special_char[0xEA]
prog_name   = "POK" + fancy_e + "SAVE"
version     = "0.7a"
author      = "David `SuperSalsa' Keaton"
info        = "Save file editor for POK" + fancy_e + "MON Gen II"
usage       = "{0} <filename>.sav"
# save data file name
fname       = "POKEGOLD.SAV"

# show off some super cool program info and stuff!
print("{} [v{}]".format(prog_name, version, author))

# do we have no arguments?
if len(sys.argv) is 1:
    # TODO: print usage information for (lack of) args
    #usage()
    pass

# TODO: TURN THIS BACK ON!!!
# print some cool ascii art!
ascii_art()

# try to open the save file
try:
    fd = io.FileIO(fname)
# yikes! the file access errors
except FileNotFoundError:
    shutdown(ERR_FILE, "file not found")
# depending on python version, `OSError' is `IOError'
except (OSError, IOError) as e:
    #shutdown(ERR_FILE, "file can't be opened")
    shutdown(ERR_FILE, e)

# was file I/O successful?
if fd is not None and fd is not 0:
    # load ALL of the binary data into a `bytes-like' structure
    data = fd.readall()
else:
    # zoinks! file couldn't be read!
    shutdown(ERR_FILE, "file is empty or couldn't be read")

# XXX: ------------------------------------------------------------
# XXX: STREAMIFY() FUNCTION TO CREATE DATA STREAM BASED ON `save{}'
# XXX:                          AND VICE VERSA!!
# XXX: ------------------------------------------------------------


# now that the file has been loaded, let's parse
parse(data)

# display the data to the user          XXX: <IN PROGRESS>
delta = display(data)

# prime stream for display and editing  XXX: <DEPRECATED>
#delta = edit(data)

# validate data & checksums so the game won't crap all over us
validate(data)

# write the changes back to the file    XXX: <INCOMPLETE>
sync(data, fd)

# exit with no error
shutdown()

# }}}1

# vim: set et:ts=4:sts=4:sw=4:fdm=marker:
