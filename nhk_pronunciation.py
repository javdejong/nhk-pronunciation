# -*- coding: utf-8 -*-

from collections import namedtuple
import re
import codecs
import os
import cPickle
import time
from string import punctuation
from bs4 import BeautifulSoup

from aqt import mw
from aqt.qt import *
from aqt.utils import showText

import japanese.reading
from japanese.reading import MecabController, mungeForPlatform, escapeText
import sys  


# ************************************************
#                User Options                    *
# ************************************************

# Style mappings (edit this if you want different colors etc.):
styles = {'class="overline"': 'style="text-decoration:overline;"',
          'class="nopron"':   'style="color: royalblue;"',
          'class="nasal"':    'style="color: red;"',
          '&#42780;': '&#42780;'}

# Expression, Reading and Pronunciation fields (edit if the names of your fields are different)
srcFields = ['Expression']    
dstFields = ['Pronunciation']
unaccented_color = 'green'
head_color = 'red'
tail_color = 'orange'
mid_color = 'blue'

# Regenerate readings even if they already exist?
regenerate_readings = True

# Add color to the expression to indicate accent? (Default: False)
#(note: requires modify_expressions to be True)
global colorize 
colorize = True

# Replace expressions with citation forms of relevant terms (Default: False)
modify_expressions = True
#delimiter to use between each word in a corrected expression (Default: '・')
modification_delimiter = '・' # only used if modify_expressions is True

# Use hiragana instead of katakana for readings?
pronunciation_hiragana = False

# ************************************************
#                Global Variables                *
# ************************************************

# Paths to the database files and this particular file
thisfile = os.path.join(mw.pm.addonFolder(), "nhk_pronunciation.py")
derivative_database = os.path.join(mw.pm.addonFolder(), "nhk_pronunciation.csv")
derivative_pickle = os.path.join(mw.pm.addonFolder(), "nhk_pronunciation.pickle")
accent_database = os.path.join(mw.pm.addonFolder(), "ACCDB_unicode.csv")

# "Class" declaration
AccentEntry = namedtuple('AccentEntry', ['NID','ID','WAVname','K_FLD','ACT','midashigo','nhk','kanjiexpr','NHKexpr','numberchars','nopronouncepos','nasalsoundpos','majiri','kaisi','KWAV','midashigo1','akusentosuu','bunshou','ac'])

# The main dict used to store all entries
thedict = {}

hiragana = u'がぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽ' \
               u'あいうえおかきくけこさしすせそたちつてと' \
               u'なにぬねのはひふへほまみむめもやゆよらりるれろ' \
               u'わをんぁぃぅぇぉゃゅょっ'
katakana = u'ガギグゲゴザジズゼゾダヂヅデドバビブベボパピプペポ' \
               u'アイウエオカキクケコサシスセソタチツテト' \
               u'ナニヌネノハヒフヘホマミムメモヤユヨラリルレロ' \
               u'ワヲンァィゥェォャュョッ'

numerals = u"一二三四五六七八九十０１２３４５６７８９"
               
#conjugation elements and other elements to not worry about
conj = ['お','ご','御','て','いる','ない','た','ば','ます','ん',
'です','だ','たり','える','うる','ある','そう','がる','たい','する','じゃ','う',
'させる','られる','せる','れる','ぬ']

particles_etc = ['は','が','も','し','を','に','と','さ','へ','まで','もう','まだ',
'ながら','より','よう','みたい','らしい','こと','の','もの','みる','わけ','よ','ね','か','わ','ぞ','ぜ']

j_symb = '・、※【】「」〒◎×〃゜『』《》〜〽。〄〇〈〉〓〔〕〖〗〘 〙〚〛〝 〞〟〠〡〢〣〥〦〧〨〫  〬  〭  〮〯〶〷〸〹〺〻〼〾〿'

#Ref: https://stackoverflow.com/questions/15033196/using-javascript-to-check-whether-a-string-contains-japanese-characters-includi/15034560#15034560               
regex = ur'[^\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\uff66-\uff9f\u4e00-\u9fff\u3400-\u4dbf]+'#+ (?=[A-Za-z ]+–)'
jp_regex = re.compile(regex, re.U)

# ************************************************
#                  Helper functions              *
# ************************************************
def test_cases():
    """
    List of things tested with via anki
    
    something with 々 and kana after it 着々と
    easy sentence 庭には二羽鶏がいる
    sentence with words that can't be looked up
    all kana sentence　あのかわいいものがいいですね
    single word (all kana) からい
    single word (all kanji)　勉強
    single word (kana at beginning)　お茶
    single word (kana or particle at end)　明らかな
    single word (kana in middle)　世の中
    single word (conjugated)　気に入った
    single word (citation form) 面白い
    word made up of useless things したがりませんか？
    2 words separated by ・　お支払い・前払い
    3 words, all conjugated, with HTML formatting, at least 
        one of which (the first) isn't in the accent dict in any form
    4 words, all lookup-able (but conjugated), no formatting, each with a 0-3 accent
    a compound word that mecab splits but that is actually in the dictionary 研究者
    """
    pass
    
def reading_new(expr):
    #set format for mecab before creating a MecabController (f[6] gets the citation form)
    old_args = japanese.reading.mecabArgs
    japanese.reading.mecabArgs = ['--node-format=%f[6] ', '--eos-format=\n',
                '--unk-format=%m[] ']
    reader = MecabController()
    reader.ensureOpen() #need to use this function before resetting args, since it uses them
    japanese.reading.mecabArgs = old_args #need to reset it so you don't break the other addon
    
    expr = escapeText(expr)
    reader.mecab.stdin.write(expr.encode("euc-jp", "ignore") + b'\n')
    reader.mecab.stdin.flush()
    expr = reader.mecab.stdout.readline().rstrip(b'\r\n').decode('euc-jp')
    return expr

"""
def new_mecab(mecabArgs_new):
    #command line testing function
    def munge(popen):
        popen = [os.path.normpath(x) for x in popen]
        popen[0] += ".exe"
        return popen
    mecabCmd_new = munge(
        [base + "mecab"] + mecabArgs_new + [
        '-d', base, '-r', base + "mecabrc"])
    mecab_new = subprocess.Popen(
                    mecabCmd_new, bufsize=-1, stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    startupinfo=si)
    def reading_new(expr):
        mecab_new.stdin.write(expr.encode("euc-jp", "ignore") + b'\n')
        mecab_new.stdin.flush()
        expr = mecab_new.stdout.readline().rstrip(b'\r\n').decode('euc-jp')
        print(expr)
        return expr
    return reading_new

"""
    
def katakana_to_hiragana(to_translate):
    katakana = [ord(char) for char in katakana]
    translate_table = dict(zip(katakana, hiragana))
    return to_translate.translate(translate_table)

def nix_punctuation(text):
    return ''.join(char for char in text if char not in punctuation)

def multi_lookup_helper(srcTxt_all, lookup_func):
    """
    Gets the pronunciation (or another type of dictionary lookup)
    for both the raw text and it without okurigana
    
    param list of strings srcTxt_all terms to look up with lookup_func
    param function lookup_func dictionary lookup function to send elements of srcTxt_all to
    """
    prons = []
    #return True if all succeeded; good for skipping mecab (avoiding possibly oversplitting)
    all_hit = False
    count = 0
    colorized_words = [] #only appended to if the words are colored
    def replace_dup(text):
        char_dex = 1
        for char in text:
            if char_dex == len(text): break
            if char == text[char_dex]: text = text[:char_dex] + '々' + text[char_dex+1:]
            char_dex += 1
        return text
    def prons_n_colors(src):
        """real lookup function"""
        new_prons = lookup_func(src)
        if not new_prons: new_prons = lookup_func(replace_dup(src))
        if new_prons:
            #choose only the first prons when assigning color to the word
            if colorize: colorized_words.append(add_color(src, new_prons[0]))
            prons.extend(new_prons)
            return True
        #else just add the blank word, so you don't lose words
        if colorize: colorized_words.append(src)
        return False
    
    if srcTxt_all:
        for srcTxt in srcTxt_all:
            if prons_n_colors(srcTxt): 
                count += 1
                continue
    
    if srcTxt_all and count == len(srcTxt_all): all_hit = True
    
    return colorized_words, prons, all_hit

def japanese_splitter(src):
    """Helper function for multi_lookup(src, lookup_func)
    but is its own function for modularity
    
    If multiple words are separated by a ・ (Japanese slash)
    or other punctuation, splits into separate words."""
    srcTxt_all = []
    src = soup_maker(src)
    #Separate the src field into individual words
    separated = re.sub(jp_regex, ' ', src)
    separated2 = nix_punctuation(separated)
    srcTxt_all = separated2.replace('・', ' ').split(' ')
    
    return srcTxt_all

def soup_maker(text):
    """para string text some text possibly formatted with HTML
    returns string src , the plaintext parsed from Beautiful soup"""
    soup = BeautifulSoup(text, "html.parser")
    src = soup.get_text()
    return src
    
def add_color(word, pron):
    """return HTML-encoded string c_word consisting of the given string word, + color"""
    non_mora_zi = r'[ぁぃぅぉゃゅょァィゥェォャュョ]'
    raw_pron = soup_maker(pron)
    if "ꜜ" in raw_pron:
        #then it has an accent (i.e. a downstep symbol)
        if len(re.sub(non_mora_zi, r'',raw_pron.split("ꜜ")[0])) == 1:
            #then it's 頭高型 or single-mora
            c_word = '<font color="' + head_color + '">' + word + '</font>'
        elif len(raw_pron) != len(raw_pron.rstrip("ꜜ")):
            #then it's 尾高　[tail]
            c_word = '<font color="' + tail_color + '">' + word + '</font>'
        else:
            #then it's 中高　[middle]
            c_word = '<font color="' + mid_color + '">' + word + '</font>'
    else:
        #it's unaccented (平板)
        c_word = '<font color="' + unaccented_color + '">' + word + '</font>'
    
    return c_word

def reading_parser(raw_reading):
    """takes a string (possibly with multiple words)
    consisting of a mecab parse (separated by spaces) and returns just the base word
    Uses heuristics to eliminate conjugations and other excessive stuff mecab returns"""
    base = [x for x in raw_reading.split(" ") if x and 
    x not in conj and x not in particles_etc and 
    x not in j_symb and x not in punctuation and x not in numerals]
    only_japanese = [re.sub(jp_regex, '', a) for a in base]
    
    return only_japanese
        
def multi_lookup(src, lookup_func, separator = "  ***  "):
    """Has 3 functions: 1) If multiple words are separated by a ・ (Japanese slash)
    or other punctuation, gets the pronunciation for each word. 
    2) Parses words with Mecab if a simple split doesn't work
    3) adds color to the original expression and/or replaces it with citation forms"""
    do_colorize = False
    is_sentence = False # set to True if probably a sentence, to avoid modifying it
    if colorize:
        if not modify_expressions:
            raise Exception("Please set modify_expressions to True for auto-colorize to work")
        else: do_colorize = True

    prons, colorized_words, srcTxt_all = [], [], []
    srcTxt_all = japanese_splitter(src)

    colorized_words, prons, all_hit = multi_lookup_helper(srcTxt_all, lookup_func)
    
    #if you couldn't split the words perfectly with a simple split, use mecab
    #or just use it anyway
    #if not all_hit:
    if len(srcTxt_all) == 1 and not prons: is_sentence = True
    
    #iterate through and replace 々 with the kanji preceding it
    new_src = src
    char_dex = 1
    for char in src:
        if char_dex == len(src): break
        if src[char_dex] == '々': new_src = src[:char_dex] + char + src[char_dex+1:]
        char_dex += 1

    #parse with mecab and add new terms to the entries to look up
    srcTxt_2 = reading_parser(reading_new(soup_maker(new_src)))
    srcTxt_all.extend([term for term in srcTxt_2 if term not in srcTxt_all])
    
    colorized_words, prons, _ = multi_lookup_helper(srcTxt_all, lookup_func)
    
    #join words together with the designated separator; but give the original src
    #back if lookup failed or if color is turned off
    fields_dest = separator.join(prons)
    
    #determine what/how to return/replace expressions based on the set config 
    delim = modification_delimiter if modify_expressions else '・'
    if do_colorize:
        if is_sentence:
            for word in colorized_words:
                src = re.sub(soup_maker(word), word, src)
            final_src = src
        else:
            final_src = delim.join(colorized_words) if prons and colorized_words else src
    else:
        final_src = delim.join(srcTxt_all) if modify_expressions else src
    
    
    #NOTE: colorized_words will only have the words that have prons, and
    #will have them in the form that was able to get a hit, i.e. citation/dictionary form
    
    return final_src, fields_dest


# ************************************************
#           Database generation functions        *
# ************************************************
def format_entry(e):
    """ Format an entry from the data in the original database to something that uses html """
    txt = e.midashigo1
    strlen = len(txt)
    acclen = len(e.ac)
    accent = "0"*(strlen-acclen) + e.ac

    # Get the nasal positions
    nasal = []
    if e.nasalsoundpos:
        positions = e.nasalsoundpos.split('0')
        for p in positions:
            if p:
                nasal.append(int(p))
            if not p:
                # e.g. "20" would result in ['2', '']
                nasal[-1] = nasal[-1] * 10

    # Get the no pronounce positions
    nopron = []
    if e.nopronouncepos:
        positions = e.nopronouncepos.split('0')
        for p in positions:
            if p:
                nopron.append(int(p))
            if not p:
                # e.g. "20" would result in ['2', '']
                nopron[-1] = nopron[-1] * 10

    outstr = ""
    overline = False

    for i in range(strlen):
        a = int(accent[i])
        # Start or end overline when necessary
        if not overline and a > 0:
            outstr = outstr + '<span class="overline">'
            overline = True
        if overline and a == 0:
            outstr = outstr + '</span>'
            overline = False

        if (i+1) in nopron:
            outstr = outstr + '<span class="nopron">'

        # Add the character stuff
        outstr = outstr + txt[i]

        # Add the pronunciation stuff
        if (i+1) in nopron:
            outstr = outstr + "</span>"
        if (i+1) in nasal:
            outstr = outstr + '<span class="nasal">&#176;</span>'

        # If we go down in pitch, add the downfall
        if a == 2:
            outstr = outstr + '</span>&#42780;'
            overline = False

    # Close the overline if it's still open
    if overline:
        outstr = outstr + "</span>"

    return outstr


def build_database():
    """ Build the derived database from the original database """
    tempdict = {}
    entries = []

    f = codecs.open(accent_database, 'r', 'utf8')
    for line in f:
        line = re.sub("\{(.*),(.*)\}", "\{\1;\2\}", line.strip())
        line = re.sub("\((.*),(.*)\)", "\(\1;\2\)   ", line.strip())
        entries.append(AccentEntry._make(line.split(",")))
    f.close()

    for e in entries:
        textentry = format_entry(e)

        # A tuple holding both the spelling in katakana, and the katakana with pitch/accent markup
        kanapron = (e.midashigo, textentry)

        # Add expressions for both
        for key in [e.nhk, e.kanjiexpr]:
            if key in tempdict:
                if kanapron not in tempdict[key]:
                    tempdict[key].append(kanapron)
            else:
                tempdict[key] = [kanapron]

    o = codecs.open(derivative_database, 'w', 'utf8')

    for key in tempdict.iterkeys():
        for kana, pron in tempdict[key]:
            o.write("%s\t%s\t%s\n" % (key, kana, pron))

    o.close()


def read_derivative():
    """ Read the derivative file to memory """
    f = codecs.open(derivative_database, 'r', 'utf8')

    for line in f:
        key, kana, pron = line.strip().split("\t")
        kanapron = (kana, pron)
        if key in thedict:
            if kanapron not in thedict[key]:
                thedict[key].append(kanapron)
        else:
            thedict[key] = [kanapron]

    f.close()


# ************************************************
#              Lookup Functions                  *
# ************************************************
def inline_style(txt):
    """ Map style classes to their inline version """

    for key in styles.iterkeys():
        txt = txt.replace(key, styles[key])

    return txt


def getPronunciations(expr):
    """ Search pronuncations for a particular expression """
    ret = []
    if expr in thedict:
        for kana, pron in thedict[expr]:
            inlinepron = inline_style(pron)

            if pronunciation_hiragana:
                inlinepron = katakana_to_hiragana(inlinepron)

            if inlinepron not in ret:
                ret.append(inlinepron)
    return ret


def lookupPronunciation(expr):
    """ Show the pronunciation when the user does a manual lookup """
    ret = getPronunciations(expr)

    thehtml = """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2//EN">
<HTML>
<HEAD>
<style>
body {
font-size: 30px;
}
</style>
<TITLE>Pronunciations</TITLE>
<meta charset="UTF-8" />
</HEAD>
<BODY>
%s
</BODY>
</HTML>
""" % ("<br/><br/>\n".join(ret))

    showText(thehtml, type="html")


def onLookupPronunciation():
    """ Do a lookup on the selection """
    japanese.lookup.initLookup()
    mw.lookup.selection(lookupPronunciation)


# ************************************************
#              Interface                         *
# ************************************************

def createMenu():
    """ Add a hotkey and menu entry """
    if not getattr(mw.form, "menuLookup", None):
        ml = QMenu()
        ml.setTitle("Lookup")
        mw.form.menuTools.addAction(ml.menuAction())

    ml = mw.form.menuLookup
    # add action
    a = QAction(mw)
    a.setText("...pronunciation")
    a.setShortcut("Ctrl+6")
    ml.addAction(a)
    mw.connect(a, SIGNAL("triggered()"), onLookupPronunciation)


def setupBrowserMenu(browser):
    """ Add menu entry to browser window """
    a = QAction("Bulk-add Pronunciations", browser)
    browser.connect(a, SIGNAL("triggered()"), lambda e=browser: onRegenerate(e))
    browser.form.menuEdit.addSeparator()
    browser.form.menuEdit.addAction(a)


def onRegenerate(browser):
    regeneratePronunciations(browser.selectedNotes())


def get_src_dst_fields(fields):
    """ Set source and destination fieldnames """
    src = None
    srcIdx = None
    dst = None
    dstIdx = None

    for i, f in enumerate(srcFields):
        if f in fields:
            src = f
            srcIdx = i
            break

    for i, f in enumerate(dstFields):
        if f in fields:
            dst = f
            dstIdx = i
            break

    return src, srcIdx, dst, dstIdx

def add_pronunciation_once(fields, model, data, n):
    """ When possible, temporarily set the pronunciation to a field """

    #if "japanese" not in model['name'].lower():
    #    return fields

    src, srcIdx, dst, dstIdx = get_src_dst_fields(fields)

    if not src or dst is None:
        return fields

    # Only add the pronunciation if there's not already one in the pronunciation field
    if not fields[dst]:
        fields[src], fields[dst] = multi_lookup(fields[src], getPronunciations)

    return fields

def add_pronunciation_focusLost(flag, n, fidx):
    # japanese model?
    #if "japanese" not in n.model()['name'].lower():
    #    return flag

    from aqt import mw
    fields = mw.col.models.fieldNames(n.model())

    src, srcIdx, dst, dstIdx = get_src_dst_fields(fields)

    if not src or not dst:
        return flag

    # dst field already filled?
    if n[dst]:
        return flag

    # event coming from src field?
    if fidx != srcIdx:
        return flag

    # grab source text
    srcTxt = mw.col.media.strip(n[src])
    if not srcTxt:
        return flag

    # update field
    try:
        n[src], n[dst] = multi_lookup(srcTxt, getPronunciations)
    except Exception, e:
        raise
    return True


def regeneratePronunciations(nids):
    mw.checkpoint("Bulk-add Pronunciations")
    mw.progress.start()
    for nid in nids:
        note = mw.col.getNote(nid)
        #if "japanese" not in note.model()['name'].lower():
        #    continue

        src, srcIdx, dst, dstIdx = get_src_dst_fields(note)

        if not src or dst is None:
            continue

        if note[dst] and not regenerate_readings:
            # already contains data, skip
            continue

        srcTxt = mw.col.media.strip(note[src])
        if not srcTxt.strip():
            continue
        
        note[src], note[dst] = multi_lookup(srcTxt, getPronunciations)

        note.flush()
    mw.progress.finish()
    mw.reset()


# ************************************************
#                   Main                         *
# ************************************************

# First check that either the original database, or the derivative text file are present:
if not os.path.exists(derivative_database) and not os.path.exists(accent_database):
    raise IOError("Could not locate the original base or the derivative database!")

# Generate the derivative database if it does not exist yet
if (os.path.exists(accent_database) and not os.path.exists(derivative_database)) or (os.path.exists(accent_database) and os.stat(thisfile).st_mtime > os.stat(derivative_database).st_mtime):
    build_database()

# If a pickle exists of the derivative file, use that. Otherwise, read from the derivative file and generate a pickle.
if  (os.path.exists(derivative_pickle) and
    os.stat(derivative_pickle).st_mtime > os.stat(derivative_database).st_mtime):
    f = open(derivative_pickle, 'rb')
    thedict = cPickle.load(f)
    f.close()
else:
    read_derivative()
    f = open(derivative_pickle, 'wb')
    cPickle.dump(thedict, f, cPickle.HIGHEST_PROTOCOL)
    f.close()

#fix encoding:
reload(sys)  
sys.setdefaultencoding('utf8')
    
# Create the manual look-up menu entry
createMenu()

from anki.hooks import addHook

addHook("mungeFields", add_pronunciation_once)

addHook('editFocusLost', add_pronunciation_focusLost)

# Bulk add
addHook("browser.setupMenus", setupBrowserMenu)
