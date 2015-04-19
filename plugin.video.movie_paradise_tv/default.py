#!/usr/bin/python
# -*- coding: utf-8 -*-
import urllib, urllib2, re, xbmcaddon, xbmcplugin, xbmcgui, xbmc
from jsunpacker import cJsUnpacker
from stream import *

dbg = False
pluginhandle = int(sys.argv[1])
itemcnt = 0
baseurl = 'http://movie-paradise.tv'
settings = xbmcaddon.Addon(id='plugin.video.movie_paradise_tv')
maxitems = (int(settings.getSetting("items_per_page"))+1)*15
filterUnknownHoster = settings.getSetting("filterUnknownHoster") == 'true'
forceViewMode = settings.getSetting("forceViewMode") == 'true'
viewMode = str(settings.getSetting("viewMode"))
userAgent = 'Mozilla/5.0 (X11; Linux x86_64; rv:18.0) Gecko/20100101 Firefox/18.0'

def START():
	addDir('Neue Filme', baseurl, 1, '', True)
	addDir('Kategorien', baseurl, 2, '', True)
	addDir('Archiv', baseurl + '/?page_id=14056&pgno=1', 3, '', True)
	addDir('Suche...', baseurl+'/?s=', 4, '', True)
	if forceViewMode: xbmc.executebuiltin("Container.SetViewMode("+viewMode+")")

def CATEGORIES(url):
	data = getUrl(url)
	for genre in re.findall('<h3>[^<]*Genres[^<]*</h3>[^<]*</div>[^<]*<ul>(.*?)</ul>', data, re.S|re.I):
		for (href, name) in re.findall('<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', genre, re.S|re.I):
			addDir(clean(name), href, 1, '', True)
	if forceViewMode: xbmc.executebuiltin("Container.SetViewMode("+viewMode+")")

def SHOWARCHIVE(url):
	if (dbg): print url
	data = getUrl(url)
	for (url, title) in re.findall('<li><a href="([^"]+)"><span class="head">([^<]+)</span></a></li>', data, re.S|re.I):
		if 'http:' not in url: url =  baseurl + url
		addLink(clean(title), url, 10, '')
	nextPage = re.findall('<span class="azlink azdisabled">[^<]*</span>[^<]*<span class="azlink "><a href="([^"]*)"', data, re.S|re.I)
	if nextPage:
		if (dbg): print nextPage
		SHOWARCHIVE(nextPage[0])
	if forceViewMode: xbmc.executebuiltin("Container.SetViewMode("+viewMode+")")

def INDEX(caturl):
	if (dbg): print caturl
	global itemcnt
	data = getUrl(caturl)
	for url, title, image in re.findall('<div class=[\'"]post-body[\'"]>[^<]*<a href="([^"]+)"[^>]*title="([^"]+)">[^<]*<img[^>]*src="([^"]+)"', data, re.S|re.I):
		if 'http:' not in url: url =  baseurl + url
		if 'http:' not in image: image =  baseurl + image
		addLink(clean(title), clean(url), 10, clean(image))
		itemcnt = itemcnt + 1
	nextPage = re.findall('<a class="next page-numbers" href="([^"]+)">Weiter &raquo;</a>', data, re.S|re.I)
	if nextPage:
		if (dbg): print nextPage
		np = clean(nextPage[0])
		if itemcnt >= maxitems: addDir('Weiter >>', np, 1, '',  True)
		else: INDEX(np)
	if forceViewMode: xbmc.executebuiltin("Container.SetViewMode("+viewMode+")")

def SEARCH(url):
    keyboard = xbmc.Keyboard('', 'Suche')
    keyboard.doModal()
    if keyboard.isConfirmed() and keyboard.getText():
		search_string = urllib.quote(keyboard.getText())
		INDEX(url + search_string)

def clean(s):
	s = re.sub('Permalink to ', '', s)
	s = re.sub('<[^>]*>', '', s)
	s = s.replace('&amp;', '&')
	matches = re.findall("&#\d+;", s)
	for hit in set(matches):
		try: s = s.replace(hit, unichr(int(hit[2:-1])))
		except ValueError: pass
	return urllib.unquote(s)

def selectVideoDialog(videos):
	titles = []
	for name, src in videos:
		titles.append(name)
	idx = xbmcgui.Dialog().select("", titles)
	if idx > -1: return videos[idx][1]

def PLAYVIDEO(url):
	global filterUnknownHoster
	print url
	data = getUrl(url)
	if not data: return
	videos = []
	for streams in re.findall('<div[^>]*id="main_content">(.*?)<div[^>]*class="related-posts">', data, re.S|re.I|re.DOTALL):
		for (stream, title) in re.findall('<a[^>]*href=["\']([^"\']*)["\'][^>]*>(.*?)</a>', streams, re.S|re.I|re.DOTALL):
			hoster = get_stream_link().get_hostername(stream)
			if filterUnknownHoster and hoster == 'Not Supported': continue
			videos += [('[COLOR=blue]' + hoster + '[/COLOR] ' + clean(title), stream)]
		for (stream) in re.findall('<iframe[^>]*src="([^"]*)"', streams, re.S|re.I):
			hoster = get_stream_link().get_hostername(stream)
			if filterUnknownHoster and hoster == 'Not Supported': continue
			videos += [('[COLOR=blue]' + hoster + '[/COLOR] ', stream)]	
	lv = len(videos)
	if lv == 0:
		xbmc.executebuiltin("XBMC.Notification(Fehler!, Video nicht gefunden, 4000)")
		return
	url = selectVideoDialog(videos) if lv > 1 else videos[0][1]
	if url:
		stream_url = GetStream(url)
		if stream_url:
			print 'open stream: ' + stream_url
			listitem = xbmcgui.ListItem(path=stream_url)
			return xbmcplugin.setResolvedUrl(pluginhandle, True, listitem)
	
def GetStream(url):
	stream_url = get_stream_link().get_stream(url)
	if stream_url is None:
		xbmc.executebuiltin("XBMC.Notification(Fehler!, Resolver liefert leeres Ergebnis, 4000)")
	elif re.match('.*not.*supported', stream_url, re.S|re.I):
		xbmc.executebuiltin("XBMC.Notification(Fehler!, Hoster nicht unterstützt, 4000)")
	elif re.match('^Error: ', stream_url, re.S|re.I):
		xbmc.executebuiltin("XBMC.Notification(Fehler!, " + re.sub('^Error: ','',stream_url) + ", 4000)")
	elif re.match('plugin:', stream_url, re.S|re.I):
		return stream_url
	else:
		req = urllib2.Request(stream_url)
		req.add_header('User-Agent', 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-GB; rv:1.9.0.3) Gecko/2008092417 Firefox/3.0.3')
		response = urllib2.urlopen(req)
		stream_url = response.geturl()
		response.close()
		return stream_url

def getUrl(url):
	req = urllib2.Request(url)
	req.add_header('User-Agent', userAgent)
	response = urllib2.urlopen(req, timeout=30)
	data = response.read()
	response.close()
	return data#.decode('utf-8')

def get_params():
	param = []
	paramstring = sys.argv[2]
	if len(paramstring) >= 2:
		params = sys.argv[2]
		cleanedparams = params.replace('?','')
		if (params[len(params)-1]=='/'): params = params[0:len(params)-2]
		pairsofparams = cleanedparams.split('&')
		param = {}
		for i in range(len(pairsofparams)):
			splitparams = pairsofparams[i].split('=')
			if (len(splitparams)) == 2:
				param[splitparams[0]] = splitparams[1]
	return param

def addLink(name, url, mode, image):
	u = sys.argv[0] + "?url=" + urllib.quote_plus(url) + "&mode=" + str(mode)
	liz = xbmcgui.ListItem(name, iconImage="DefaultVideo.png", thumbnailImage=image)
	liz.setInfo( type="Video", infoLabels={ "Title": name } )
	liz.setProperty('IsPlayable', 'true')
	return xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=liz)

def addDir(name, url, mode, image, is_folder=False):
	u = sys.argv[0] + "?url=" + urllib.quote_plus(url) + "&mode=" + str(mode)
	liz = xbmcgui.ListItem(name, iconImage="DefaultFolder.png", thumbnailImage=image)
	liz.setInfo( type="Video", infoLabels={ "Title": name } )
	return xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=liz, isFolder=is_folder)

params = get_params()
url = None
mode = None

try: url = urllib.unquote_plus(params["url"])
except: pass
try: mode = int(params["mode"])
except: pass

if mode==None or url==None or len(url)<1: START()
elif mode==1: INDEX(url)
elif mode==2: CATEGORIES(url)
elif mode==3: SHOWARCHIVE(url)
elif mode==4: SEARCH(url)
elif mode==10: PLAYVIDEO(url)

xbmcplugin.endOfDirectory(pluginhandle)
