# MIT LICENSE
# Mycroft Skill: Application Launcher, opens/closes Linux desktop applications
# Copyright © 2019 Philip Mayer philip.mayer@shadowsith.de

# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


import os
import random
import sys
import time
from collections import defaultdict
import re
from mycroft.skills.core import intent_file_handler
from mycroft.util.log import LOG
from mycroft.skills.common_play_skill import CommonPlaySkill, CPSMatchLevel
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
from json import load, dump
from .plex_backend import PlexBackend
from mycroft.audio.services.vlc import VlcService

__author__ = 'colla69'


class PlexMusicSkill(CommonPlaySkill):

    def CPS_match_query_phrase(self, phrase):
        if self.refreshing_lib:
            self.speak_dialog("refresh.library")
            return None
        else:
            phrase = re.sub(self.translate_regex('on_plex'), '', phrase)
            title = ""
            artist = ""
            album = ""
            playlist = ""
            t_prob = 0
            a_prob = 0
            al_prob = 0
            p_prob = 0
            if phrase.startswith("artist"):
                artist, a_prob = self.artist_search(phrase[7:])
            elif phrase.startswith("album"):
                album, al_prob = self.album_search(phrase[6:])
            elif phrase.startswith("playlist"):
                playlist, p_prob = self.playlist_search(phrase[9:])
            else:
                title, t_prob = self.title_search(phrase)
                artist, a_prob = self.artist_search(phrase)
                album, al_prob = self.album_search(phrase)
                playlist, p_prob = self.playlist_search(phrase)
            print(""" Plex Music skill
    Title      %s  %f
    Artist     %s  %d
    Album      %s  %d        
    Playlist   %s  %d        
            """ % (title, t_prob, artist, a_prob, album, al_prob, playlist, p_prob))
            if t_prob > al_prob and t_prob > a_prob:
                data = {
                    "title": title,
                    "file": self.titles[title],
                    "media_type": "title"
                }
                return phrase, CPSMatchLevel.TITLE, data
            elif a_prob >= al_prob and a_prob != 0:
                data = {
                    "title": artist,
                    "file": self.artists[artist],
                    "media_type": "artist"
                }
                return phrase, CPSMatchLevel.MULTI_KEY, data
            elif al_prob >= a_prob and al_prob != 0:
                data = {
                    "title": album,
                    "file": self.albums[album],
                    "media_type": "album"
                }
                return phrase, CPSMatchLevel.MULTI_KEY, data
            elif p_prob > al_prob:
                data = {
                    "title": playlist,
                    "file": self.playlists[playlist]
                }
                return phrase, CPSMatchLevel.MULTI_KEY, data
            else:
                return None

    def CPS_start(self, phrase, data):
        if data is None:
            return None
        if not self.client:
            if self.get_running():
                self.vlc_player.clear_list()
                self.vlc_player.stop()
        title = data["title"]
        link = data["file"]
        media_type = data["media_type"]
        random.shuffle(link)
        try:
            if not self.client:
                self.vlc_player.add_list(link)
                self.vlc_player.play()
                """
                if len(link) >= 1:
                    self.vlc_player = self.vlcI.media_list_player_new()
                    m = self.vlcI.media_list_new(link)
                    self.vlc_player.set_media_list(m)
                    self.vlc_player.play()
                elif len(link) > 0:
                    self.vlc_player = self.vlcI.media_player_new()
                    m = self.vlcI.media_new(link[0])
                    self.vlc_player.set_media(m)
                    self.vlc_player.play() """
            else:
                # plex doesn't take a collection of items like vlc
                # just pass a single key, and let the backend decide what to do
                key = self.keys[link[0]]
                self.plex.play_media(key, media_type)
        except Exception as e:
            LOG.info(type(e))
            LOG.info("Unexpected error:", sys.exc_info()[0])
            raise
        finally:
            time.sleep(2)
            if not self.client:
                if not self.get_running():
                    self.speak_dialog("playback.problem")
                    self.speak_dialog("excuses")

    def __init__(self):
        super().__init__(name="TemplateSkill")
        self.uri = ""
        self.token = ""
        self.lib_name = ""
        self.client = ""
        self.ducking = "True"
        self.regexes = {}
        self.refreshing_lib = False
        self.p_uri = self.uri+":32400"
        self.p_token = "?X-Plex-Token="+self.token
        self.data_path = os.path.expanduser("~/.config/plexSkill/")
        if not os.path.exists(self.data_path):
            os.mkdir(self.data_path)
        self.data_path += "data.json"
        self.plex = None
        self.artists = defaultdict(list)
        self.albums = defaultdict(list)
        self.titles = defaultdict(list)
        self.playlists = defaultdict(list)
        self.keys = defaultdict(list)
        self.tracks = {}
        self.vlc_player = None

    def initialize(self):
        self.uri = self.settings.get("musicsource", "")
        self.token = self.settings.get("plextoken", "")
        self.lib_name = self.settings.get("plexlib", "")
        self.client = self.settings.get("plexclient", "")
        self.ducking = self.settings.get("ducking", "True")
        self.p_uri = self.uri+":32400"
        if self.load_plex_backend():
            if not os.path.exists(self.data_path):
                self.speak_dialog("library.unknown")
            self.load_data()
        self.vlc_player = VlcService(config={'duck': self.ducking})
        self.vlc_player.normal_volume = 85
        self.vlc_player.low_volume = 20
        if self.ducking:
            self.add_event('recognizer_loop:record_begin', self.handle_listener_started)
            self.add_event('recognizer_loop:record_end', self.handle_listener_stopped)
            self.add_event('recognizer_loop:audio_output_start', self.handle_audio_start)
            self.add_event('recognizer_loop:audio_output_end', self.handle_audio_stop)

    def get_running(self):
        return self.vlc_player.player.is_playing()

    def load_data(self):
        LOG.info("loading "+self.data_path)
        try:
            if not os.path.isfile(self.data_path):
                LOG.info("making new JsonData")
                if self.load_plex_backend():
                    self.plex.down_plex_lib()
                    self.speak_dialog("done")
            data = self.json_load(self.data_path)
            for artist in data:
                if artist == "playlist":
                    for playlist in data[artist]:
                        for song in data[artist][playlist]:
                            p_artist = song[0]
                            album = song[1]
                            title = song[2]
                            file = song[3]
                            self.playlists[playlist].append(file)
                            self.tracks[file] = (p_artist, album, title)
                for album in data[artist]:
                    for song in data[artist][album]:
                        title = song[0]
                        file = song[1]  # link
                        key = song[2] #media key for remote play
                        self.albums[album].append(file)
                        self.artists[artist].append(file)
                        self.titles[title].append(file)
                        self.tracks[file] = (artist, album, title)
                        self.keys[file] = key
        finally:
            self.refreshing_lib = False

    # thanks to forslund
    def translate_regex(self, regex):
        if regex not in self.regexes:
            path = self.find_resource(regex + '.regex')
            if path:
                with open(path) as f:
                    string = f.read().strip()
                self.regexes[regex] = string
        return self.regexes[regex]

    ###################################
    # Utils

    def load_plex_backend(self):
        if self.plex is None:
            LOG.info("\n\nconnecting to:\n{} \n{} {}\n".format(self.p_uri, self.token, self.lib_name))
            if self.token and self.p_uri and self.lib_name:
                self.plex = PlexBackend(self.p_uri, self.token, self.lib_name, self.data_path, self.client)
                return True
            else:
                self.speak_dialog("config.missing")
                return False
        else:
            return True

    def json_save(self, data, fname):
        with open(fname, 'w') as fp:
            dump(data, fp)

    def json_load(self, fname):
        with open(fname, 'r') as fp:
            return load(fp)

    def get_tokenized_uri(self, uri):
        return self.p_uri + uri + self.token

    def title_search(self, phrase):
        probabilities = process.extractOne(phrase, self.titles.keys(), scorer=fuzz.ratio)
        artist = probabilities[0]
        confidence = probabilities[1]
        return artist, confidence

    def artist_search(self, phrase):
        probabilities = process.extractOne(phrase, self.artists.keys(), scorer=fuzz.ratio)
        artist = probabilities[0]
        confidence = probabilities[1]
        return artist, confidence

    def album_search(self, phrase):
        probabilities = process.extractOne(phrase, self.albums.keys(), scorer=fuzz.ratio)
        album = probabilities[0]
        confidence = probabilities[1]
        return album, confidence

    def playlist_search(self, phrase):
        probabilities = process.extractOne(phrase, self.playlists.keys(), scorer=fuzz.ratio)
        playlist = probabilities[0]
        confidence = probabilities[1]
        return playlist, confidence

    ######################################################################
    # audio ducking

    def handle_listener_started(self, message):
        if not self.client and self.ducking:
            self.vlc_player.lower_volume()

    def handle_listener_stopped(self, message):
        if not self.client and self.ducking:
            self.vlc_player.restore_volume()

    def handle_audio_start(self, event):
        if not self.client and self.ducking:
            self.vlc_player.lower_volume()

    def handle_audio_stop(self, event):
        if not self.client and self.ducking:
            self.vlc_player.restore_volume()

    ##################################################################
    # intents

    @intent_file_handler('play.music.intent')
    def handle_play_music_intent(self, message):
        pass

    @intent_file_handler('resume.music.intent')
    def handle_resume_music_intent(self, message):
        if self.refreshing_lib:
            self.speak_dialog("refresh.library")
            return None
        else:
            if not self.client:
                self.vlc_player.resume()

    @intent_file_handler('pause.music.intent')
    def handle_pause_music_intent(self, message):
        if self.refreshing_lib:
            self.speak_dialog("refresh.library")
            return None
        else:
            if not self.client:
                self.vlc_player.pause()

    @intent_file_handler('next.music.intent')
    def handle_next_music_intent(self, message):
        if self.refreshing_lib:
            self.speak_dialog("refresh.library")
            return None
        else:
            if not self.client:
                self.vlc_player.next()

    @intent_file_handler('prev.music.intent')
    def handle_prev_music_intent(self, message):
        if self.refreshing_lib:
            self.speak_dialog("refresh.library")
            return None
        else:
            if not self.client:
                self.vlc_player.previous()

    @intent_file_handler('information.intent')
    def handle_music_information_intent(self, message):
        if not self.client:
            if self.get_running():
                meta = self.vlc_player.track_info()
                artist, album, title = meta["artists"], meta["album"], meta["name"]
                if title.startswith("file"):
                    media = self.vlc_player.player.get_media()
                    link = media.get_mrl()
                    artist, album, title = self.tracks[link]
                    if isinstance(artist, list):
                        artist = artist[0]
                LOG.info("""\nPlex skill is playing:
    {}   by   {}  
    Album: {}        
                """.format(title, artist, album))
                self.speak_dialog('information', data={'title': title, "artist": artist})
        else:
            return None

    @intent_file_handler('reload.library.intent')
    def handle_reload_library_intent(self, message):
        if self.refreshing_lib:
            self.speak_dialog("already.refresh.library")
            return None
        else:
            self.refreshing_lib = True
            self.speak_dialog("refresh.library")
            try:
                os.remove(self.data_path)
            except FileNotFoundError:
                pass                
            self.load_data()

    def converse(self, utterances, lang="en-us"):
        return False

    def stop(self):
        if not self.client:
            self.vlc_player.stop()


def create_skill():
    return PlexMusicSkill()
