# -*- coding: utf-8 -*-
# Module: default
# Author: Pedro M. Silva
# Created on: 08.07.2019
# License: GPL v.3 https://www.gnu.org/copyleft/gpl.html

#import requests

import time
start = time.time()


import sys
import json
import urllib
import urllib.request
import routing
import random
import xbmcaddon
import xbmc
import xbmcvfs
import base64
from datetime import datetime
from xbmcgui import ListItem
from xbmcplugin import addDirectoryItem, addDirectoryItems, endOfDirectory, setContent, setPluginCategory, setPluginFanart, setResolvedUrl
import xml.etree.ElementTree as ET
import os

plugin = routing.Plugin()
my_addon = xbmcaddon.Addon()

__profile__ = xbmcvfs.translatePath(my_addon.getAddonInfo('profile'))

poster_size = 500

def try_get(obj, *properties):
    for prop in properties:
        if obj is not None:
            obj = obj.get(prop)

    return obj

def without_none(d):
    return {k: v for k, v in d.items() if v is not None}

# link https://stackoverflow.com/questions/1630320/what-is-the-pythonic-way-to-detect-the-last-element-in-a-for-loop
def lookahead(iterable):
    """Pass through all values from the given iterable, augmented by the
    information if there are more values to come after the current one
    (True), or if it is the last value (False).
    """
    # Get an iterator and pull the first value.
    it = iter(iterable)
    last = next(it)
    # Run the iterator to exhaustion (starting from the second value).
    for val in it:
        # Report the *previous* value (more to come).
        yield last, True
        last = val
    # Report the last value.
    yield last, False

def merge (*ds):
    bd = {}
    for d in ds:
        bd.update(d)
    return bd

def get_server_media_url ():
    url = my_addon.getSetting( 'url' ).strip() or 'http://127.0.0.1:3030'

    # Allow bare "host:port" values by assuming plain HTTP
    if '://' not in url:
        url = 'http://' + url

    url = url.rstrip( '/' )

    # Tolerate users pasting the API endpoint itself
    if url.endswith( '/api' ):
        url = url[:-len( '/api' )]

    return url

def get_server_url ():
    return get_server_media_url() + '/api'

def build_collection_filters ( collection_settings, all_collections, value ):
    ids_dict = dict( [ ( c['title'], c['id'] ) for c in all_collections ] )

    collection_names = collection_settings if isinstance(collection_settings, list) else [ c.strip() for c in collection_settings.split( ',' ) ]

    collection_ids = set( [ ids_dict[ c ] for c in collection_names if c in ids_dict ] )

    params = [ ( 'filterCollections[%s]' % id, value ) for id in collection_ids ]

    return dict( params )

def api_post(url,body={}):
    url = "%s/%s" % (get_server_url(), url)

    if body is dict:
        body = list(body.items())

    if body:
        url = '%s?%s' % (url, '&'.join(['%s=%s' % p for p in body ]))

    with urllib.request.urlopen(url, urllib.parse.urlencode({}).encode('utf-8')) as resp:
        content = resp.read()

        return json.loads( content )

def api_request(url, params = {}, filter_collections = None):
    url = "%s/%s" % (get_server_url(), url)

    needs_collections = bool( filter_collections or 'filterCollections' in params )

    if needs_collections:
        collections = api_request('media/collection/', { 'kind': filter_collections })

    if filter_collections:
        included_collections = build_collection_filters( my_addon.getSetting( 'includedCategories' ), collections, 'include' )
        excluded_collections = build_collection_filters( my_addon.getSetting( 'excludedCategories' ), collections, 'exclude' )

        params = merge( included_collections, excluded_collections, params )

    if 'filterCollections' in params:
        p = params[ 'filterCollections' ]

        included_collections = build_collection_filters( [ n for n,s in p.items() if s == 'include' ], collections, 'include' )
        excluded_collections = build_collection_filters( [ n for n,s in p.items() if s == 'exclude' ], collections, 'exclude' )

        params = merge( included_collections, excluded_collections, params )

        del params[ 'filterCollections' ]

    if params:
        url = '%s?%s' % ( url, '&'.join( [ '%s=%s' % p for p in params.items() ] ) )

    with urllib.request.urlopen( url ) as resp:
        content = resp.read()

        return json.loads( content )

def load_custom_filters ():
    filters_path = os.path.join(__profile__, "custom_filters.xml")

    try:
        tree = ET.parse( filters_path )
    except:
        return []

    root = tree.getroot()

    filters = []

    for child in root:
        if child.tag == 'filter':
            parameters = {}

            for param in child:
                if param.tag == 'sort':
                    parameters[ 'filterSort[field]' ] = param.text
                    if 'direction' in param.attrib:
                        parameters[ 'filterSort[direction]' ] = param.attrib[ 'direction' ]
                    else:
                        parameters[ 'filterSort[direction]' ] = 'asc'
                elif param.tag == 'watched':
                    parameters[ 'filterWatched' ] = param.text
                elif param.tag == 'take':
                    parameters[ 'take' ] = int(param.text)
                elif param.tag == 'skip':
                    parameters[ 'skip' ] = int(param.text)
                elif param.tag == 'sample':
                    parameters[ 'sample' ] = int(param.text)
                elif param.tag == 'collections':
                    if 'filterCollections' not in parameters:
                        parameters[ 'filterCollections' ] = dict()

                    for collection in param:
                        parameters[ 'filterCollections' ][ collection.text ] = collection.tag
                elif param.tag == 'genres':
                    for collection in param:
                        parameters[ 'filterGenres[%s]' % collection.text ] = collection.tag

            filters.append( ( child.attrib[ 'name' ], child.attrib[ 'kind' ], parameters ) )

    return filters

@plugin.route('/')
def index():
    addDirectoryItem(plugin.handle, plugin.url_for(list_movies), ListItem("Movies"), True)
    addDirectoryItem(plugin.handle, plugin.url_for(list_tvshows), ListItem("Tv Shows"), True)
    addDirectoryItem(plugin.handle, plugin.url_for(list_history, 0), ListItem("History"), True)
    addDirectoryItem(plugin.handle, plugin.url_for(list_playlists, 0), ListItem("Playlists"), True)
    addDirectoryItem(plugin.handle, plugin.url_for(list_custom_filters), ListItem("Custom Filters"), True)
    endOfDirectory(plugin.handle)

# TV SHOWS
def create_tvshow_item(show):
    item = ListItem(show['title'])

    item.setArt({
        'banner': show['cachedArtwork']['banner'],
        'background': show['cachedArtwork']['background'],
        'landscape': show['cachedArtwork']['background'],
        'poster': show['cachedArtwork']['poster'] + '?width=' + str(poster_size),
        'fanart': show['cachedArtwork']['background']
    })
    item.setInfo('video', {
        'DBID': 'show-' + show['id'],
        'year': show['year'],
        'plot': show['plot'],
        'mediatype': 'tvshow'
    })
    item.setProperties({
        'TotalSeasons': show['seasonsCount'],
        'TotalEpisodes': show['episodesCount'],
        'WatchedEpisodes': show['watchedEpisodesCount'],
        'UnwatchedEpisodes': show['episodesCount'] - show['watchedEpisodesCount'],
    })

    return item

def render_tvshows(shows):
    buffer = []

    for show, has_more in lookahead(shows):
        item = create_tvshow_item(show)

        url = plugin.url_for(list_tvshows_seasons, show['id'])

        buffer.append((url, item, True))

        if len(buffer) > 100 or not has_more:
            addDirectoryItems(plugin.handle, buffer)

            buffer = []

    setContent(plugin.handle, 'tvshows')
    endOfDirectory(plugin.handle)

@plugin.route('/tvshows')
def list_tvshows():
    addDirectoryItem(plugin.handle, plugin.url_for(list_tvshows_titles), ListItem("Titles"), True)
    addDirectoryItem(plugin.handle, plugin.url_for(list_tvshows_genres), ListItem("Genres"), True)
    addDirectoryItem(plugin.handle, plugin.url_for(list_tvshows_collections), ListItem("Categories"), True)
    addDirectoryItem(plugin.handle, plugin.url_for(list_tvshows_random), ListItem("Random"), True)
    addDirectoryItem(plugin.handle, plugin.url_for(list_tvshows_recent), ListItem("Recent"), True)
    endOfDirectory(plugin.handle)

@plugin.route('/tvshows/single/<tvshow_id>')
def list_tvshows_single_items(tvshow_id):
    show = api_request('media/show/%s' % tvshow_id, filter_collections = 'show')

    render_tvshows([show])

@plugin.route('/tvshows/genres')
def list_tvshows_genres():
    genres = api_request('media/show/genres')

    for genre in genres:
        addDirectoryItem(plugin.handle, plugin.url_for(list_tvshows_genres_items, genre), ListItem(genre), True)

    endOfDirectory(plugin.handle)

@plugin.route('/tvshows/genres/<genre_id>')
def list_tvshows_genres_items(genre_id):
    shows = api_request('media/show', [ ('filterGenres[%s]' % genre_id, 'include') ], filter_collections = 'show' )

    render_tvshows(shows)

@plugin.route('/tvshows/collections')
def list_tvshows_collections():
    collections = api_request('media/collection/', { 'kind': 'show' } )

    for collection in collections:
        addDirectoryItem(plugin.handle, plugin.url_for(list_tvshows_collections_items, collection['title']), ListItem(collection['title']), True)

    endOfDirectory(plugin.handle)

@plugin.route('/tvshows/collections/<collection_title>')
def list_tvshows_collections_items(collection_title):
    shows = api_request('media/show', { 'filterCollections': { collection_title: 'include' } }, filter_collections = 'show' )

    render_tvshows(shows)

@plugin.route('/tvshows/titles')
def list_tvshows_titles():
    shows = api_request('media/show', filter_collections = 'show')

    render_tvshows(shows)


@plugin.route('/tvshows/random')
def list_tvshows_random():
    shows = api_request('media/show', { 'sample': 20 }, filter_collections = 'show')

    render_tvshows(shows)

@plugin.route('/tvshows/recent')
def list_tvshows_recent():
    shows = api_request('media/show', { 'filterSort[field]': 'addedAt', 'filterSort[direction]': 'desc' }, filter_collections = 'show')

    render_tvshows(shows)

# SEASONS
def create_tvseason_item(season, show = None):
    item = ListItem("Season %d" % season['number'])

    item.setInfo('video', {
        'DBID': 'season-' + season['id']
    })

    item.setArt({
        'poster': season['cachedArtwork']['poster'] + '?width=' + str(poster_size),
        'fanart': show['cachedArtwork']['background'] if show is not None else season['cachedArtwork']['tvshow']['background']
    })

    return item

def render_tvseasons(seasons):
    if len(seasons) > 0:
        show = api_request('media/show/%s' % seasons[0]['tvShowId'])

        setPluginFanart(plugin.handle, show['cachedArtwork']['background'])

        setPluginCategory(plugin.handle, show['title'])

    for season in seasons:
        item = create_tvseason_item(season, show)

        url = plugin.url_for(list_tvseasons_episodes, season['id'])

        addDirectoryItem(plugin.handle, url, item, True)

    setContent(plugin.handle, 'videos')
    endOfDirectory(plugin.handle)


@plugin.route('/tvshows/<show_id>/seasons')
def list_tvshows_seasons(show_id):
    seasons = api_request('media/season?show=%s' % show_id)

    render_tvseasons(seasons)

# EPISODES
def create_tvepisode_item(episode, season = None, show = None):
    item = ListItem(episode['title'])

    item.setArt({
        'thumb': episode['cachedArtwork']['thumbnail'],
        'poster': episode['cachedArtwork']['thumbnail'],
        'fanart': show['cachedArtwork']['background'] if show is not None else episode['cachedArtwork']['tvshow']['background']
    })

    item.setInfo('video', {
        'DBID': 'episode-' + episode['id'],
        'premiered': (episode['airedAt'] or '').split('T')[0],
        'title': episode['title'],
        'tvshowtitle': show['title'] if show is not None else 'Test',
        'episode': episode['number'],
        'season': episode['seasonNumber'],
        'plot': episode['plot'],
        'playcount': 1 if episode['watched'] else 0,
        'duration': episode['runtime'],
        'rating': episode['rating'],
        'mediatype': 'episode'
    })

    item.setProperties(without_none({
        'VideoCodec': try_get(episode, 'metadata', 'video', 'codec'),
        'VideoResolution': try_get(episode, 'metadata', 'video', 'resolution'),
        'IsPlayable': True,
    }))

    return item

def render_tvepisodes(episodes):
    if len(episodes) > 0:
        season = api_request('media/season/%s' % episodes[0]['tvSeasonId'])

        show = api_request('media/show/%s' % season['tvShowId'])

        setPluginFanart(plugin.handle, show['cachedArtwork']['background'])

        setPluginCategory(plugin.handle, show['title'])

    for episode in episodes:
        item = create_tvepisode_item(episode, season, show)

        url = plugin.url_for(play_media, episode['kind'], episode['id'])

        addDirectoryItem(plugin.handle, url, item)

    setContent(plugin.handle, 'episodes')
    endOfDirectory(plugin.handle)

@plugin.route('/tvseasons/<season_id>/episodes')
def list_tvseasons_episodes(season_id):
    episodes = api_request('media/episode?season=%s' % season_id)

    render_tvepisodes(episodes)

# MOVIES
def create_movie_item(movie):
    item = ListItem(movie['title'])

    item.setArt({
        'banner': movie['cachedArtwork']['banner'],
        'background': movie['cachedArtwork']['background'],
        'landscape': movie['cachedArtwork']['background'],
        'poster': movie['cachedArtwork']['poster'] + '?width=' + str(poster_size),
        'fanart': movie['cachedArtwork']['background']
    })

    item.setInfo('video', {
        'DBID': 'movie-' + movie['id'],
        'year': movie['year'],
        'plot': movie['plot'],
        'genre': movie['genres'],
        'playcount': 1 if movie['watched'] else 0,
        'duration': movie['runtime'],
        'tagline': movie['tagline'],
        'rating': movie['rating'],
        'mpaa': movie['parentalRating'],
        'mediatype': 'movie'
    })

    item.setProperties(without_none({
        'VideoCodec': try_get(movie, 'metadata', 'video', 'codec'),
        'VideoResolution': try_get(movie, 'metadata', 'video', 'resolution'),
        'IsPlayable': True
    }))
    return item

def render_movies(movies):
    buffer = []

    for movie, has_more in lookahead(movies):
        item = create_movie_item(movie)

        url = plugin.url_for(play_media, movie['kind'], movie['id'])

        buffer.append((url, item, False))

        if len(buffer) > 100 or not has_more:
            addDirectoryItems(plugin.handle, buffer)

            buffer = []

    setContent(plugin.handle, 'movies')
    endOfDirectory(plugin.handle)

@plugin.route('/movies')
def list_movies():
    addDirectoryItem(plugin.handle, plugin.url_for(list_movies_titles), ListItem("Titles"), True)
    addDirectoryItem(plugin.handle, plugin.url_for(list_movies_watched), ListItem("Watched"), True)
    addDirectoryItem(plugin.handle, plugin.url_for(list_movies_genres), ListItem("Genres"), True)
    addDirectoryItem(plugin.handle, plugin.url_for(list_movies_collections), ListItem("Categories"), True)
    addDirectoryItem(plugin.handle, plugin.url_for(list_movies_random), ListItem("Random"), True)
    addDirectoryItem(plugin.handle, plugin.url_for(list_movies_recent), ListItem("Recent"), True)
    endOfDirectory(plugin.handle)

@plugin.route('/movies/single/<movie_id>')
def list_movies_single_items(movie_id):
    movie = api_request('media/movie/%s' % movie_id, filter_collections = 'movie' )

    render_movies([movie])

@plugin.route('/movies/genres')
def list_movies_genres():
    genres = api_request('media/movie/genres')

    for genre in genres:
        addDirectoryItem(plugin.handle, plugin.url_for(list_movies_genres_items, genre), ListItem(genre), True)

    endOfDirectory(plugin.handle)

@plugin.route('/movies/genres/<genre_id>')
def list_movies_genres_items(genre_id):
    movies = api_request('media/movie', [ ( 'filterGenres[%s]' % genre_id, 'include' ) ], filter_collections = 'movie' )

    render_movies(movies)

@plugin.route('/movies/collections')
def list_movies_collections():
    collections = api_request('media/collection/', { 'kind': 'movie' } )

    for collection in collections:
        addDirectoryItem(plugin.handle, plugin.url_for(list_movies_collections_items, collection['id']), ListItem(collection['title']), True)

    endOfDirectory(plugin.handle)

@plugin.route('/movies/collections/<collection_id>')
def list_movies_collections_items(collection_id):
    movies = api_request('media/movie', [ ( 'filterCollections[%s]' % collection_id, 'include' ) ], filter_collections = 'movie')

    render_movies(movies)

@plugin.route('/movies/titles')
def list_movies_titles():
    movies = api_request('media/movie', filter_collections = 'movie')

    render_movies(movies)

@plugin.route('/movies/watched')
def list_movies_watched():
    movies = api_request('media/movie', { 'filterWatched': 'include' }, filter_collections = 'movie')

    render_movies(movies)


@plugin.route('/movies/random')
def list_movies_random():
    movies = api_request('media/movie', { 'sample': 20 }, filter_collections = 'movie')

    render_movies(movies)

@plugin.route('/movies/recent')
def list_movies_recent():
    movies = api_request('media/movie', { 'filterSort[field]': 'addedAt', 'filterSort[direction]': 'desc' }, filter_collections = 'movie')

    render_movies(movies)

# Mixed Media
def create_media_item(media):
    if media['kind'] == 'movie':
        return create_movie_item(media)
    elif media['kind'] == 'show':
        return create_tvshow_item(media)
    elif media['kind'] == 'season':
        return create_tvseason_item(media)
    elif media['kind'] == 'episode':
        return create_tvepisode_item(media)
    elif media['kind'] == 'custom':
        return create_custom_item(media)

def render_media(media_list, tail_items = []):
    buffer = []

    for media, has_more in lookahead(media_list):
        item = create_media_item(media)

        url = plugin.url_for(play_media, media['kind'], media['id'])

        buffer.append((url, item, False))

        if len(buffer) > 100 or not has_more:
            addDirectoryItems(plugin.handle, buffer)

            buffer = []

    if tail_items:
        addDirectoryItems(plugin.handle, tail_items)

    setContent(plugin.handle, 'movies')
    endOfDirectory(plugin.handle)

def strptime(string_date, format):
    try:
        return datetime.strptime(string_date, format)
    except TypeError:
        return datetime(*(time.strptime(string_date, format)[0:6]))

@plugin.route('/history/<page>')
def list_history(page):
    page = int(page)

    history_page_size = 10

    receiver = my_addon.getSetting( 'receiver' ) or None

    params = {'records': 'true', 'take': history_page_size, 'skip': page * history_page_size}
    sessions = api_request('media/sessions', params = params)

    pagination_items = []
    if len(sessions) == history_page_size:
        pagination_items.append((plugin.url_for(list_history, page + 1), ListItem("Next Page"), True))

    setPluginCategory(plugin.handle, 'History (Page %s)' % (page + 1))
    render_media([session['record'] for session in sessions], tail_items = pagination_items)

    endOfDirectory(plugin.handle)

@plugin.route('/playlists/page/<page>')
def list_playlists(page):
    page = int(page)

    playlist_page_size = 10

    receiver = my_addon.getSetting( 'receiver' ) or None

    params = {'items': 'true', 'take': playlist_page_size, 'skip': page * playlist_page_size, 'filterSort[field]': 'createdAt', 'filterSort[direction]': 'desc'}
    playlists = api_request('player/%s/playlists' % urllib.parse.quote(receiver), params = params)

    setPluginCategory(plugin.handle, 'Playlists (Page %s)' % (page + 1))

    for playlist in playlists:
        playlist_date = strptime(playlist['createdAt'], '%Y-%m-%dT%H:%M:%S.%fZ')

        date_format = '%d %b %Y, %A'
        time_format = '%H:%M'

        playlist_title = playlist_date.strftime(date_format)
        playlist_subtitle = '%s (%d items)' % (playlist_date.strftime(time_format), len(playlist['items']))

        addDirectoryItem(plugin.handle, plugin.url_for(list_playlist_items, playlist['id']), ListItem(playlist_title, playlist_subtitle), True)

    if len(playlists) == playlist_page_size:
        addDirectoryItem(plugin.handle, plugin.url_for(list_playlists, page + 1), ListItem("Next Page"), True)

    endOfDirectory(plugin.handle)

@plugin.route('/playlists/items/<playlist_id>')
def list_playlist_items(playlist_id):
    receiver = my_addon.getSetting( 'receiver' ) or None

    playlist = api_request('player/%s/playlists/%s' % (urllib.parse.quote(receiver), playlist_id))

    playlist_items = api_request('player/%s/playlists/%s/items/' % (urllib.parse.quote(receiver), playlist_id))

    # Set the page title
    playlist_date = strptime(playlist['createdAt'], '%Y-%m-%dT%H:%M:%S.%fZ')

    date_format = '%d %b %Y, %A, %H:%M'

    playlist_title = playlist_date.strftime(date_format)

    setPluginCategory(plugin.handle, playlist_title)

    # Render the page items
    render_media(playlist_items)

@plugin.route('/custom-filters')
def list_custom_filters():
    filters = load_custom_filters()

    setPluginCategory(plugin.handle, 'Custom Filters')

    for name, _kind, _parameters in filters:
        addDirectoryItem(plugin.handle, plugin.url_for(list_custom_filter_named, name), ListItem(name), True)

    endOfDirectory(plugin.handle)

@plugin.route('/custom-filters/<filter_name>')
def list_custom_filter_named(filter_name):
    filters = load_custom_filters()

    selectedFilter = next((f for f in filters if f[0] == filter_name), None)

    if selectedFilter != None:
        name, kind, parameters = selectedFilter

        if kind == 'movie':
            movies = api_request('media/movie', parameters, filter_collections = 'movie')

            render_movies(movies)
        elif kind == 'show':
            shows = api_request('media/show', parameters, filter_collections = 'show')

            render_tvshows(shows)
        else:
            endOfDirectory(plugin.handle)

        setPluginCategory(plugin.handle, name)
    else:
        endOfDirectory(plugin.handle)

def create_custom_item(custom):
    item = ListItem(custom['title'])

    poster = None if custom['cachedArtwork']['poster'] == None else custom['cachedArtwork']['poster'] + '?width=' + str(poster_size)

    item.setArt({
        'banner': custom['cachedArtwork']['banner'],
        'background': custom['cachedArtwork']['background'],
        'landscape': custom['cachedArtwork']['background'],
        'poster':  poster,
        'fanart': custom['cachedArtwork']['background']
    })

    item.setInfo('video', {
        'plot': custom['plot'] if 'plot' in custom else '',
        'playcount': 1 if custom['watched'] else 0,
        'mediatype': 'video'
    })

    item.setProperties(without_none({
        'VideoCodec': try_get(custom, 'metadata', 'video', 'codec'),
        'VideoResolution': try_get(custom, 'metadata', 'video', 'resolution'),
        'IsPlayable': True
    }))
    return item


def find (seq, fn):
    for x in seq:
        if fn(x): return x

    return None

def filter(seq, fn):
    return [x for x in seq if fn(x)]

def create_stream_url(kind, id, stream, session = None):
    if session is None:
        return get_server_url() + '/media/raw/%s/%s/stream/%s' % (kind, id, stream)
    else:
        rec_type = 'kodi'
        rec_name = urllib.parse.quote(session['receiver'])

        return get_server_media_url() + '/media/send/%s/%s/session/%s/stream/%s' % (rec_type, rec_name, session['id'], stream)

def create_playable_session(record, receiver):
    kind, id = record['kind'], record['id']

    resp = api_post('player/%s/command/create-play-session' % urllib.parse.quote(receiver), [('args[]', kind), ('args[]', id)])

    return resp['streams'], resp['session']

def get_playable_session(id, receiver):
    resp = api_post('player/%s/command/get-play-session' % urllib.parse.quote(receiver), [('args[]', id)])

    return resp['streams'], resp['session']

def create_playable_item(record, video, subtitles, session = None):
    if record['kind'] == 'movie':
        play_item = create_movie_item(record)
    elif record['kind'] == 'episode':
        season = api_request('media/season/%s' % record['tvSeasonId'])

        show = api_request('media/show/%s' % season['tvShowId'])

        play_item = create_tvepisode_item(record, season, show)
    elif record['kind'] == 'custom':
        play_item = create_custom_item(record)

    play_item.setPath(create_stream_url(record['kind'], record['id'], video['id'], session = session))

    play_item.setProperties({
        'IsPlayable': True
    })

    if len(subtitles) > 0:
        play_item.setSubtitles([create_stream_url(record['kind'], record['id'], sub['id'], session = session) for sub in subtitles])

    return play_item


@plugin.route('/play-session/<id>')
def play_session(id):
    receiver = my_addon.getSetting( 'receiver' ) or None

    if receiver is not None:
        streams, session = get_playable_session(id, receiver)

        mediaKind = session['mediaKind']
        mediaId = session['mediaId']

        record = api_request('media/%s/%s' % (mediaKind, mediaId), params = {'transient': 'all'})

        video_stream = find(streams, lambda s: s['type'] == 'video')

        subtitles_stream = filter(streams, lambda s: s['type'] == 'subtitles')

        # Create a playable item with a path to play.
        play_item = create_playable_item(record, video_stream, subtitles_stream, session = session)

        # Pass the item to the Kodi player.
        setResolvedUrl(plugin.handle, True, listitem=play_item)

@plugin.route('/play/<kind>/<id>')
def play_media(kind, id):
    receiver = my_addon.getSetting( 'receiver' ) or None

    record = api_request('media/%s/%s' % (kind, id), params = {'transient': 'all'})

    if receiver is not None:
        streams, session = create_playable_session(record, receiver)
    else:
        streams = api_request('media/%s/%s/streams' % (kind, id))
        session = None

    video_stream = find(streams, lambda s: s['type'] == 'video')

    subtitles_stream = filter(streams, lambda s: s['type'] == 'subtitles')

    # Create a playable item with a path to play.
    play_item = create_playable_item(record, video_stream, subtitles_stream, session = session)

    # Pass the item to the Kodi player.
    setResolvedUrl(plugin.handle, True, listitem=play_item)

if __name__ == '__main__':
    start_user = time.time()
    plugin.run()
    end = time.time()
    xbmc.log( "PAGE: %s%s in %.3f secs (user code in %.3f secs)" % ( sys.argv[ 0 ], sys.argv[ 2 ], end - start, end - start_user ), level=xbmc.LOGDEBUG )

    if 'select' in plugin.args:
        builtin = 'RunScript(%s,%s,%s,%s)' % ('plugin.video.unicast', 'autoselect', sys.argv[0] + sys.argv[ 2 ], base64.b64encode(plugin.args['select'][0].encode('utf-8')).decode('ascii'))

        xbmc.executebuiltin(builtin)
