from collections import defaultdict
from json import load, dump
from plexapi.server import PlexServer

class PlexBackend():

    def __init__(self, plexurl, token, libname, data_path, client_name):

        self.token = token
        self.plexurl = plexurl
        self.lib_name = libname
        self.data_path = data_path
        self.client_name = client_name
        self.plex = PlexServer(self.plexurl, self.token)
        self.music = self.plex.library.section(self.lib_name)
                       
    def down_plex_lib(self):
        songs = {}
        try:
            playlists = self.plex.playlists()
            songs["playlist"] = {}
            for p in playlists:
                p_name = p.title
                songs["playlist"][p_name] = []
                for track in p.items():
                    title = track.title
                    album = track.album().title
                    artist = track.artist().title
                    file_key = self.get_file(track)
                    file = self.get_tokenized_uri( file_key )
                    songs["playlist"][p_name].append([artist, album, title, file])
            root = self.music.all()
            artists = defaultdict(list)
            albums = defaultdict(list)
            titles = defaultdict(list)
            count = 0
            for artist in root:
                artist_title = artist.title
                songs[artist_title] = {}
                for album in artist.albums():
                    album_title = album.title
                    songs[artist_title][album_title] = []
                    for track in album.tracks():
                        title = track.title
                        key = track.key
                        file_key = self.get_file(track)
                        file = self.get_tokenized_uri( file_key )
                        try:
                            print("""%d 
            %s -- %s 
            %s
            %s
            %s

                            """ % (count, artist_title, album_title, title,file_key, key))
                            songs[artist_title][album_title].append([title, file, key])
                            count += 1
                        except Exception as ex:
                            print(ex)
            self.json_save(songs, self.data_path)
            print("done loading library")
        except Exception as e:
            print(e)
            return None

    def json_save(self, data, fname):
        with open(fname, 'w') as fp:
            dump(data, fp)

    def json_load(self, fname):
        with open(fname, 'r') as fp:
            return load(fp)
        
    def get_tokenized_uri(self, uri):
        return self.plexurl+uri+"?X-Plex-Token="+self.token

    def get_file(self,track):
        for media in track.media:
            for p in media.parts:
                return p.key

    def play_media(self, key, media_type):
        client = self.plex.client(self.client_name)
        item = self.plex.library.fetchItem(key)
        if media_type == "album":
            item = self.plex.library.fetchItem(item.parentKey)
            client.playMedia(item)
        elif media_type == "artist":
            item = self.plex.library.fetchItem(item.grandparentKey)
            queue = self.plex.createPlayQueue(item, shuffle = 1)
            client.playMedia(queue)
        else:
            client.playMedia(item)

    def pause(self):
        client = self.plex.client(self.client_name)
        client.pause("music")

    def next(self):
        client = self.plex.client(self.client_name)
        client.skipNext("music")

    def previous(self):
        client = self.plex.client(self.client_name)
        client.skipPrevious("music")

    def resume(self):
        client = self.plex.client(self.client_name)
        client.play("music")

    def stop(self):
        client = self.plex.client(self.client_name)
        client.stop("music")