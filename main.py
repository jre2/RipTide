from tidalapi import *
username    = 'overture2112@gmail.com'
password    = 'Seohyun9'
S = None

import gzip as C
from   mutagen.flac import FLAC
import cPickle as pickle
import os
from   pprint import pprint as pp
import time
import urllib2

import signal
STOP = False
def _sigint_handler( signal, frame ):
    global STOP
    STOP = True
    print 'User requested stop. Halting...'
signal.signal( signal.SIGINT, _sigint_handler )

class Database:
    def __init__( self ):
        self.load()

    def load( self ):
        try:
            self.artists = pickle.load( C.open('artists.db','rb') )
            self.albums = pickle.load( C.open('albums.db','rb') )
            self.tracks = pickle.load( C.open('tracks.db','rb') )
        except IOError:
            self.clear()

    def save( self ):
        t0 = time.time()
        pickle.dump( self.artists, C.open('artists.db','wb') )
        pickle.dump( self.albums, C.open('albums.db','wb') )
        pickle.dump( self.tracks, C.open('tracks.db','wb') )
        t = time.time() - t0
        print '-- Saved DBs in %0.2fs --' % t

    def clear( self ):
        self.artists, self.albums, self.tracks = {}, {}, {}

    def update( self ):
        self.updateWantedArtists()
        self.save()
        if STOP: return
        self.updateWantedAlbums()
        self.save()

    def updateWantedArtists( self ):
        print 'Updating wanted artists...'
        wanted = S.user.favorites.artists()
        for i, artist in enumerate( wanted ):
            if 1 or artist.id not in self.artists: #TODO: or data stale
                self.addArtist( artist, i, len(wanted) )
            if STOP: return
        print '...done'

    def updateWantedAlbums( self ): # sometimes needed for Various Artists
        print 'Updating wanted albums...'
        wanted = S.user.favorites.albums()
        for i, album in enumerate( wanted ):
            if 1 or album.id not in self.albums: #TODO: or data stale
                self.addAlbum( album, i, len(wanted) )
            if STOP: return
        print '...done'

    def addArtist( self, a, i, n ):
        print '[%d/%d] Fetching albums for artist [%d] %s' % ( i+1, n, a.id, a.name )
        albums = S.get_artist_albums( a.id )
        self.artists[ a.id ] = { 'name':a.name, 'id':a.id, 'albums': [x.id for x in albums] }
        for i, album in enumerate( albums ):
            if 1 or album.id not in self.albums: #TODO: or data stale
                self.addAlbum( album, i, len(albums) )

    def addAlbum( self, a, i, n ):
        d = { 'name':a.name, 'id':a.id,
            'albumArtist':a.artist.id, 'albumArtistName':a.artist.name,
            'duration':a.duration, 'num_tracks':a.num_tracks, 'release_date':a.release_date,
            'copyright':a.copyright, 'upc':a.upc, 'tidaltype':a.tidaltype, 'version':a.version,
            }

        # do only quick update if already in db
        if a.id in self.albums: return self.albums[ a.id ].update( d )

        print '  [%d/%d] Fetching tracks for album [%d] %s' % ( i+1, n, a.id, a.name )
        self.albums[ a.id ] = d
        tracks = S.get_album_tracks( a.id )
        self.albums[ a.id ]['tracks'] = [ x.id for x in tracks ]

        # if some tracks are unavailable, note that
        if len( tracks ) != a.num_tracks:
            self.albums[ a.id ][ 'num_tracks_missing' ] = a.num_tracks - len( tracks )

        # process all tracks
        for track in tracks:
            if track.id not in self.tracks: #TODO: or data stale
                self.addTrack( track )

    def addTrack( self, t ):
        self.tracks[ t.id ] = { 'name':t.name, 'id':t.id,
                'duration':t.duration, 'available':t.available,
                'album':t.album.id, 'artist':t.artist.id, 'artistName':t.artist.name,
                'num_track':t.track_num, 'num_disc':t.disc_num,
                'copyright':t.copyright, 'isrc':t.isrc, 'replayGain':t.replayGain, 'version':t.version,
            }

    def lookupArtist( self, name ): return [ v for k,v in self.artists.items() if v['name']==name ]
    def lookupAlbum( self, name ):  return [ v for k,v in self.albums.items() if v['name']==name ]
    def lookupTrack( self, name ):  return [ v for k,v in self.tracks.items() if v['name']==name ]

    def pullAll( self ):
        print 'Pulling everything [%d]' % len(self.artists)
        for i, artid in enumerate( self.artists ):
            self.pullArtist( artid, i+1, len(self.artists) )
            if STOP: return

    def pullArtist( self, artid, cur=-1, total=-1 ):
        a = self.artists[ artid ]
        print 'Pulling artist %d: %s [%d/%d]' % ( artid, a['name'], cur, total )
        for i, albid in enumerate( a['albums'] ):
            self.pullAlbum( albid, i+1, len(a['albums']) )
            if STOP: return

    def pullAlbum( self, albid, cur=-1, total=-1 ):
        a = self.albums[ albid ]
        print 'Pulling album %d: %s - %s [%d/%d]' % ( albid, a['albumArtistName'], a['name'], cur, total )
        for i,tid in enumerate( a['tracks'] ):
            self.pullTrack( tid, i+1, len(a['tracks']) )

    def pullTrack( self, tid, cur=-1, total=-1, idParent=u'~/music/byId', nameParent=u'~/music/byName', debug=False, dry_run=False ):
        t = self.tracks[ tid ]
        print '  Pulling track %d: %s [%d/%d]' % ( tid, t['name'], cur, total )
        if dry_run: return

        idPath      = os.path.expanduser( os.path.join( idParent, self.getIdPath( tid ) ) )
        namePath    = os.path.expanduser( os.path.join( nameParent, self.getPath( tid ) ) )

        if debug: print '    saving', idPath
        if not os.path.exists( idPath ):
            url = S.get_media_url( tid )
            if debug: print '    fetching...', url
            r   = urllib2.urlopen( url )
            parent = os.path.dirname( idPath )
            if not os.path.exists( parent ): os.makedirs( parent )
            open( idPath, 'wb' ).write( r.read() )

            if debug: print '    tagging...'
            self.setTags( tid, idPath )     # also (soft) verifcation

        if debug: print '    linking', namePath
        if not os.path.exists( namePath ):
            parent = os.path.dirname( namePath )
            if not os.path.exists( parent ): os.makedirs( parent )
            os.link( idPath, namePath )

    def setTags( self, tid, path ):
        t = FLAC( path )
        if int( t.get('tidal_rip_version',u'0') ) < 1:
            d = self.getTags( tid )
            for k in ['title','album','artist','albumartist','tracknumber','totaltracks','discnumber','date','isrc','barcode','copyright','releasetype']:
                t[k] = unicode( d[k] )
            for k in ['tidal_release_date','replaygain_track_gain']:
                t[k] = unicode( d[k] )
            t['tidal_rip_version'] = u'1'
            if 0:
                print 'DICT', d
                print t.pprint()
                print t.tags
            t.save()

    def getTags( self, tid ):
        t = self.tracks[ tid ]
        a = self.albums[ t['album'] ]
        d = {
            'title': t['name'],
            'album': a['name'],
            'artist': t['artistName'],
            'albumartist': a['albumArtistName'],
            'tracknumber': t['num_track'],
            'totaltracks': a['num_tracks'],
            'discnumber': t['num_disc'],
            'date': a['release_date'].year,

            'isrc': t['isrc'],
            'barcode': a['upc'],
            'copyright': a['copyright'],
            'releasetype': a['tidaltype'],

            'tidal_release_date': a['release_date'].strftime('%Y-%m-%d'),
            'replaygain_track_gain': '%s dB' % t['replayGain'],

            'a_copyright': a['copyright'],
            't_copyright': t['copyright'],
            'a_version': a['version'],
            't_version': t['version'],
            'duration': t['duration'],
            'albumDuration': a['duration'],
        }
        return d

    def getPath( self, tid ):
        s = u'{albumartist}/{date} {album} [Tidal {barcode}]/{discnumber}-{tracknumber} - {title}.flac'
        return s.format( **self.getTags( tid ) )
    def getIdPath( self, tid ):
        t = self.tracks[ tid ]
        a = self.albums[ t['album'] ]
        albumId = t['album']
        albumArtistId = a['albumArtist']
        return u'%d/%d/%d.flac' % ( albumArtistId, albumId, tid )

def login():
    global S
    S = Session( Config( quality=Quality.lossless ) )
    S.login( username, password )

d = Database()

def main():
    print 'Start\n'
    if 0:
        #d.clear()
        login()
        #d.update()
        #d.updateWantedAlbums()
    if 1:
        login()
        d.pullAll()
    if 0:
        print 'Test artist', d.lookupArtist( 'Yes' )[0]
        print 'Test album', d.lookupAlbum( 'Love Rain OST' )[0]
        print 'Test track', d.lookupTrack( 'Yours Is No Disgrace' )[0]
    if 0:
        #print d.getTags( 39225196 )
        print d.getPath( 39225196 )
        print d.getIdPath( 39225196 )

    if 0:
        #login()
        d.pullTrack( 39225196 )
        d.pullTrack( 2062754 )
        d.pullTrack( 68710601 )
    #print 'Done'

if __name__ == '__main__': main()
