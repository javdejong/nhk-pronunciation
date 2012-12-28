# -*- coding: utf-8 -*-

from collections import namedtuple
import re
import codecs
import os
import cPickle

from aqt import mw
from aqt.qt import *
from aqt.utils import showInfo

import japanese

accent_database = os.path.join(mw.pm.addonFolder(), "ACCDB_unicode.csv")
accent_pickle = os.path.join(mw.pm.addonFolder(), "ACCDB_unicode.pickle")

AccentEntry = namedtuple('AccentEntry', ['NID','ID','WAVname','K_FLD','ACT','MIDASHIGO','nhk','kanjiexpr','NHKexpr','numberchars','nopronouncepos','nasalsoundpos','majiri','kaisi','KWAV','midashigo1','akusentosuu','bunshou','ac'])

entries = []

def build_database(f):
    for line in f:
        line = re.sub("\{(.*),(.*)\}", "\{\1;\2\}", line.strip())
        line = re.sub("\((.*),(.*)\)", "\(\1;\2\)   ", line.strip())
        entries.append(AccentEntry._make(line.split(",")))

if False and (os.path.exists(accent_pickle) and
    os.stat(accent_pickle).st_mtime > os.stat(accent_database).st_mtime):
    f = open(accent_pickle, 'rb')
    entries = cPickle.load(f)
    f.close()
else:
    f = codecs.open(accent_database, 'r', 'utf8')
    build_database(f)
    f.close()

    # Write to pickle
    f = open(accent_pickle, 'wb')
    cPickle.dump(entries, f, cPickle.HIGHEST_PROTOCOL)
    f.close()

def lookupPronuncation(expr):
    showInfo("Tried a pronunciation lookup on %s!" % expr)

def onLookupPronunciation():
    japanese.lookup.initLookup()
    mw.lookup.selection(lookupPronuncation)

def createMenu():
    if not getattr(mw.form, "menuLookup", None):
        ml = QMenu()
        ml.setTitle("Lookup")
        mw.form.menuTools.addAction(ml.menuAction())

    ml = mw.form.menuLookup
    # add action
    a = QAction(mw)
    a.setText("...pronunciation on alc")
    a.setShortcut("Ctrl+6")
    ml.addAction(a)
    mw.connect(a, SIGNAL("triggered()"), onLookupPronunciation)

createMenu()
