JMR_ARTIST_SKIP = 0
username    = 'overture2112@gmail.com'
password    = 'Seohyun9'
S = None        # session object

from tidalapi import *
import tidalapi as T

import gzip as C
from   mutagen.flac import FLAC
import pickle as pickle
import os
from   pprint import pprint as pp
import time
import urllib.request, urllib.error, urllib.parse

import signal
STOP = False
def _sigint_handler( signal, frame ):
    global STOP
    STOP = True
    print('User requested stop. Halting...')
signal.signal( signal.SIGINT, _sigint_handler )

FORCE_REDO_ARTIST = False
FORCE_REDO_ALBUM = False

MUSIC_PATH_BYID = "~/direct/tidal/byId"
MUSIC_PATH_BYNAME = "~/direct/tidal/byName"

#MUSIC_PATH_BYID = '/arc/music/tidal/byId'
#MUSIC_PATH_BYNAME = '/arc/music/tidal/byName'


def escape_dict( d ):
    '''Simple escape of things that ruin file paths. Probably not aggressive enough'''
    def escape_val( s ):
        if not isinstance( s, str ): return s
        s = s.replace('/','-')          # usually from dates in the track title (from lives, bootlegs, alternate takes, etc)
        s = s.replace(':','-')          # usually from subtitles in the album title
        s = s.replace('?','')
        if len(s) > 240: s = s[:240]+'...'  # fix for absurdly long track titles
        return s
    return { k:escape_val(v) for k,v in d.items() }

class Database:
    def __init__( self ):
        self.load()

    def load( self ):
        try:
            t0 = time.time()
            self.artists = pickle.load( C.open('artists.db','rb') )
            self.albums = pickle.load( C.open('albums.db','rb') )
            self.tracks = pickle.load( C.open('tracks.db','rb') )
            self.skipped = pickle.load( C.open('skipped.db','rb') )
            self.downloaded = pickle.load( C.open('downloaded.db','rb') )
            t = time.time() - t0
            print( f'--Loaded DBs with {len(self.downloaded)} downloaded, {len(self.skipped)} skipped, {len(self.artists)} artists, {len(self.albums)} albums {len(self.tracks)} tracks in {t:0.2f} sec --' )
        except IOError:
            self.clear()

    def save( self ):
        t0 = time.time()
        pickle.dump( self.artists, C.open('artists.db','wb') )
        pickle.dump( self.albums, C.open('albums.db','wb') )
        pickle.dump( self.tracks, C.open('tracks.db','wb') )
        pickle.dump( self.skipped, C.open('skipped.db','wb') )
        pickle.dump( self.downloaded, C.open('downloaded.db','wb') )
        t = time.time() - t0
        print('-- Saved DBs in %0.2fs --' % t)

    def clear( self ):
        self.artists, self.albums, self.tracks, self.skipped, self.downloaded = {}, {}, {}, {}, {}

    def update( self ):
        self.updateWantedArtists()
        self.save()
        if STOP: return
        self.updateWantedAlbums()
        self.save()

    def updateWantedArtists( self ):
        print('Updating wanted artists...')
        wanted = S.user.favorites.artists()
        for i, artist in enumerate( wanted ):
            if FORCE_REDO_ARTIST or artist.id not in self.artists: #TODO: or data stale
                self.addArtist( artist, i, len(wanted) )
            if STOP: return
            #if i % 5 == 0: self.save()  # save every few artists
        print('...done')

    def updateWantedAlbums( self ): # sometimes needed for Various Artists
        print('Updating wanted albums...')
        wanted = S.user.favorites.albums()
        for i, album in enumerate( wanted ):
            if 0 or album.id not in self.albums: #TODO: or data stale
                self.addAlbum( album, i, len(wanted) )
            if STOP: return
        print('...done')

    def addArtist( self, a, i, n ):
        print('[%d/%d] Fetching albums for artist [%d] %s' % ( i+1, n, a.id, a.name ))
        albums = S.get_artist_albums( a.id )
        self.artists[ a.id ] = { 'name':a.name, 'id':a.id, 'albums': [x.id for x in albums] }
        for i, album in enumerate( albums ):
            if FORCE_REDO_ALBUM or album.id not in self.albums: #TODO: or data stale
                self.addAlbum( album, i, len(albums) )

    def addAlbum( self, a, i, n ):
        d = { 'name':a.name, 'id':a.id,
            'albumArtist':a.artist.id, 'albumArtistName':a.artist.name,
            'duration':a.duration, 'num_tracks':a.num_tracks, 'num_discs':a.num_discs, 'num_videos':a.num_videos,
            'release_date':a.release_date, 'copyright':a.copyright, 'upc':a.upc, 'tidaltype':a.tidaltype, 'version':a.version,
            'explicit':a.explicit, 'cover':a.cover,
            }

        # do only quick update if already in db
        if a.id in self.albums: return self.albums[ a.id ].update( d )

        print('  [%d/%d] Fetching tracks for album [%d] %s' % ( i+1, n, a.id, a.name ))
        tracks = S.get_album_tracks( a.id ) #TODO: this can fail if album was removed from site
        d['tracks'] = [ x.id for x in tracks ]
        self.albums[ a.id ] = d

        # only add album to DB once we have all the track ids
        # note: a crash can cause an album to exist in the DB but the tracks might not be

        # if some tracks are unavailable, note that
        if len( tracks ) != a.num_tracks:
            self.albums[ a.id ][ 'num_tracks_missing' ] = a.num_tracks - len( tracks )

        # process all tracks
        for track in tracks:
            if track.id not in self.tracks: #TODO: or data stale
                self.addTrack( track )

    def addTrack( self, t ):
        self.tracks[ t.id ] = { 'name':t.name, 'id':t.id,
                'num_track':t.track_num, 'num_disc':t.disc_num,
                'album':t.album.id, 'artist':t.artist.id, 'artistName':t.artist.name,
                'duration':t.duration,
                'replayGain':t.replayGain, 'peak':t.peak,
                'audioQuality':t.audioQuality, 'available':t.available,
                'copyright':t.copyright, 'isrc':t.isrc, 'version':t.version, 'tidaltype':t.tidaltype,
                'explicit':t.explicit,
            }

    def lookupArtist( self, name ): return [ v for k,v in list(self.artists.items()) if v['name']==name ]
    def lookupAlbum( self, name ):  return [ v for k,v in list(self.albums.items()) if v['name']==name ]
    def lookupTrack( self, name ):  return [ v for k,v in list(self.tracks.items()) if v['name']==name ]

    def pullAll( self, dry_run=False ):
        print('Pulling everything [%d]' % len(self.artists))
        try:
            for i, artid in enumerate( self.artists ):
                if i < JMR_ARTIST_SKIP: continue #JMR temp to resume faster
                self.pullArtist( artid, i+1, len(self.artists), dry_run=dry_run )
                if STOP:
                    self.save()
                    return
            self.save()
        except Exception as e:
            self.save()
            raise e

    def pullArtist( self, artid, cur=-1, total=-1, dry_run=False ):
        a = self.artists[ artid ]
        header_artist = 'Pulling artist %d: %s [%d/%d]' % ( artid, a['name'], cur, total )
        # ideally we print artist header here but only if an album's header is
        # but for now we just have each album print the artist header. crap solution
        for i, albid in enumerate( a['albums'] ):
            self.pullAlbum( albid, i+1, len(a['albums']), cur, total, header_artist, dry_run=dry_run )
            if STOP: return

    def pullAlbum( self, albid, cur=-1, total=-1, cur_artist=-1, total_artist=-1, header_artist='?Artist?', debug=False, dry_run=False ):
        displayed_header = False
        a = self.albums[ albid ]
        t = 0
        t_num = 0
        for i,tid in enumerate( a['tracks'] ):
            try:
                if tid in self.downloaded: continue     # db might contain tracks we don't have locally but have been archived
                if tid in self.skipped: continue        # don't try skipped tracks unless we expect Tidal had a major change in catalog

                if not displayed_header:
                    #print( header_artist )
                    print('  Pulling album %d: %s - %s [%d/%d] [%d/%d]' % ( albid, a['albumArtistName'], a['name'], cur, total, cur_artist, total_artist ))
                    displayed_header = True

                t += self.pullTrack( tid, i+1, len(a['tracks']), dry_run=dry_run )
                if t > 0: t_num += 1

                if not dry_run:
                    self.downloaded[ tid ] = time.time()    # timestamp may be useful later for updating

            except AssertionError as e:                     # likely not available in right format or encryption issue
                print( f'    >>> skipping assert: {e}' )
                self.skipped[ tid ] = f'assert: {e}'
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    print( '    --- sleeping 5 to reduce rate limiting' )
                    time.sleep( 5 )
                elif e.response.status_code == 401:         # likely track isn't available on Tidal but some of the album is
                    print( '    >>> skipping missing track' )
                    self.skipped[ tid ] = 'missing'
                else:
                    print( f'    HTTPError: {e}' )

        #TODO: pull cover art

        t_avg = t/t_num if t_num > 0 else 0
        if displayed_header and debug:
            print( f'  ...done ({t_avg:.1f}s avg)' )

    def pullTrack( self, tid, cur=-1, total=-1, idParent=MUSIC_PATH_BYID, nameParent=MUSIC_PATH_BYNAME, debug=False, dry_run=False ):
        t = self.tracks[ tid ]
        if debug:
            print('  Pulling track %d: %s [%d/%d]' % ( tid, t['name'], cur, total ))

        idPath      = os.path.expanduser( os.path.join( idParent, self.getIdPath( tid ) ) )
        namePath    = os.path.expanduser( os.path.join( nameParent, self.getPath( tid ) ) )

        time_downloading = 0

        # Create missing byName<>byId links

        if os.path.exists( idPath ) and not os.path.exists( namePath ):
            if debug: print('    added missing byName')
            parent = os.path.dirname( namePath )
            if not os.path.exists( parent ): os.makedirs( parent )
            os.link( idPath, namePath )

        if dry_run: return

        # Download missing files

        if debug: print('    saving', idPath)
        if not os.path.exists( idPath ):
            t0 = time.time()
            url = S.get_media_url( tid )
            if debug: print('    fetching...', url)
            r   = urllib.request.urlopen( url )
            parent = os.path.dirname( idPath )
            if not os.path.exists( parent ): os.makedirs( parent )
            open( idPath, 'wb' ).write( r.read() )

            if debug: print('    tagging...')
            self.setTags( tid, idPath )     # also (soft) verifcation

            time_downloading = time.time() - t0

        # Possibly update tags
        if 0:
            self.setTags( tid, idPath )

        # Create links

        if debug: print('    linking', namePath)
        if not os.path.exists( namePath ):
            parent = os.path.dirname( namePath )
            if not os.path.exists( parent ): os.makedirs( parent )
            os.link( idPath, namePath )

        return time_downloading

    def setTags( self, tid, path ):
        t = FLAC( path )
        if int( t.get('tidal_rip_version','0') ) < 1:
            d = self.getTags( tid )
            for k in ['title','album','artist','albumartist',
                    'tracknumber','tracktotal','discnumber','disctotal',
                    'duration','albumduration',
                    'date','isrc','barcode','copyright','releasetype']:
                t[k] = str( d[k] )
            for k in ['replaygain_track_gain','replaygain_track_peak']:
                t[k] = str( d[k] )
            t['tidal_rip_version'] = '2'
            if 0:
                print('DICT', d)
                print(t.pprint())
                print(t.tags)
            t.save()

    def getTags( self, tid ):
        t = self.tracks[ tid ]
        a = self.albums[ t['album'] ]

        #FIXME temp hack
        import datetime
        if a['release_date'] is None: a['release_date'] = datetime.date.fromtimestamp(0)

        d = {
            'title': t['name'],
            'album': a['name'],
            'artist': t['artistName'],
            'albumartist': a['albumArtistName'],    # album_artist ?

            'tracknumber': t['num_track'],          # track ?
            'tracktotal': a['num_tracks'],
            'discnumber': t['num_disc'],            # disc ?
            'disctotal': a['num_discs'],

            'duration': t['duration'],
            'albumduration': a['duration'],         # ???

            'date': a['release_date'].year,
            'date_tidal': a['release_date'].strftime('%Y-%m-%d'),
            'isrc': t['isrc'],
            'barcode': a['upc'],
            'copyright': t['copyright'] or a['copyright'],
            'releasetype': a['tidaltype'],

            'replaygain_track_gain': '%s dB' % t['replayGain'],
            'replaygain_track_peak': t['peak'],

            # is this Tidal 'version' useful? it seems to always be null
        }
        return d

    def getPath( self, tid ):
        #TODO: consider padding disc/track number to two digits ?
        s = '{albumartist}/{date} {album} [Tidal {barcode}]/{discnumber}-{tracknumber} {title}.flac'
        return s.format( **escape_dict( self.getTags( tid ) ) )

    def getIdPath( self, tid ):
        t = self.tracks[ tid ]
        a = self.albums[ t['album'] ]
        albumId = t['album']
        albumArtistId = a['albumArtist']
        return '%d/%d/%d.flac' % ( albumArtistId, albumId, tid )

def login():
    global S
    S = Session( Config( quality=Quality.lossless ) )
    #S._config.quality = "LOSSLESS" # LOW HIGH LOSSLESS HI_RES
    S.login( username, password )

d = Database()

def main():
    print('Start\n')
    if 0:   # Rebuild database from scratch
        d.clear()
        login()
        d.update()
    if 0:   # Update database incremental
        login()
        d.update()

    if 1:   # Download music
        login()
        d.pullAll()
    if 0:   # Don't download, just fix byName links
        login()
        d.pullAll( dry_run=True )

    # various tests
    if 0:
        p = d.getPath( 101982695 )
        print( p )
        print( len(p) )
    if 0:
        login()
        artist_todo = { 'snsd':4128766, 'yes':13686, 'rush':19141 }
        for aid in artist_todo.values():
            d.pullArtist( aid )
    if 0:
        print('Test artist', d.lookupArtist( 'Yes' )[0])
        print('Test album', d.lookupAlbum( 'Love Rain OST' )[0])
        print('Test track', d.lookupTrack( 'Yours Is No Disgrace' )[0])
    if 0:
        #print d.getTags( 39225196 )
        print(d.getPath( 39225196 ))
        print(d.getIdPath( 39225196 ))
    if 0:
        login()
        d.pullArtist(4206502)
        #d.pullAlbum(19817010)

    print( 'Done' )

if __name__ == '__main__': main()
