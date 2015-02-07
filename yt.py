import re
import urlparse
import urllib2
import xml.etree.ElementTree as ET
import Ice
import Murmur

href_re = 'href="([^"]*)"'

class YoutubeBotCallback(Murmur.ServerCallback):
    def __init__(self, server, adapter):
        self.server = server
        self.adapter = adapter

    def get_ids(self, message):
        ids = set()
        uris = re.findall(href_re, message)
        for uri in uris:
            i = None
            res = urlparse.urlparse(uri)
            if res.netloc in ['www.youtube.com', 'youtube.com'] and res.path == '/watch':
                qs = urlparse.parse_qs(res.query)
                if 'v' in qs:
                    i = qs['v'][0]
            elif res.netloc in ['www.youtu.be', 'youtu.be']:
                i = re.match('^/(?P<vid>.*)', res.path).group('vid')
            if i is not None:
                ids.add(i)
        return ids

    def get_title(self, vid):
        video = {}
        url = "http://gdata.youtube.com/feeds/api/videos/" + vid
        request = urllib2.Request(url)
        response = urllib2.urlopen(request, timeout=2)
        if response.getcode() == 200:
            tree = ET.parse(response)
            t = tree
            channel = tree.find('./{http://www.w3.org/2005/Atom}author/{http://www.w3.org/2005/Atom}name')
            if channel is None:
                video['error'] = 'No channel name found'
                return video
            else:
                video['channel'] = channel.text
            group = tree.find('./{http://search.yahoo.com/mrss/}group')
            if group is None:
                video['error'] = 'No media:group found'
                return video
            else:
                title = group.find('./{http://search.yahoo.com/mrss/}title')
                if title is None:
                    video['error'] = 'No title found'
                    return video
                else:
                    video['title'] = title.text
                duration = group.find('./{http://gdata.youtube.com/schemas/2007}duration')
                if duration is None:
                    video['error'] = 'No duration found'
                    return video
                else:
                    seconds = int(duration.get('seconds'))
                    minutes = seconds / 60
                    video['duration'] = "%d minutes %02d seconds" % (minutes, seconds % 60)
                thumb = group.find('./{http://search.yahoo.com/mrss/}thumbnail')
                if thumb is not None:
                    video['thumb'] = thumb.get('url')
        else:
            video['error'] = response.read()
        return video

    def process(self, message, vid):
        video = self.get_title(vid)
	url = "http://youtu.be/%s" % (vid)
        if 'error' in video:
            for c in message.channels:
                self.server.sendMessageChannel(c, False, video['error'])
        else:
            text = '<p><b><span style="color: red;">YouTube</span></b> video: <b>%s</b> (%s) by <b>%s</b></p>' % (video['title'], video['duration'], video['channel'])
            if 'thumb' in video:
                text += '<p><a href="%s"><img src="%s" height="180" width="240"></a></p>' % (url, video['thumb'])
            for c in message.channels:
                self.server.sendMessageChannel(c, False, text)

    def userTextMessage(self, user, message, current=None):
        for i in self.get_ids(message.text):
            self.process(message, i)

def make_cb(comm, server):
    adapter = comm.createObjectAdapterWithEndpoints("Callback.Client", "tcp -h 127.0.0.1")
    adapter.activate()
    cb = Murmur.ServerCallbackPrx.uncheckedCast(adapter.addWithUUID(YoutubeBotCallback(server, adapter)))
    return cb

if __name__ == "__main__":
    import time
    import sys
    import os

    try:
        pid = os.fork()
    except OSerror, e:
        raise Exception, "%s [%d]" % (e.strerror, e.errno)
    
    if pid == 0:
        os.setsid()
        try:
            pid = os.fork()
        except OSError, e:
            raise Exception, "%s [%d]" % (e.strerror, e.errno)
        if pid == 0:
            os.chdir("/")
            os.umask(0)
        else:
            os._exit(0)
    else:
        os._exit(0)

    comm = Ice.initialize()
    proxy = comm.stringToProxy("Meta:tcp -p 6502")
    meta = Murmur.MetaPrx.checkedCast(proxy)
    server = meta.getServer(1)

    cb = make_cb(comm,server)
    server.addCallback(cb)
    while True:
        try:
            time.sleep(3)
        except KeyboardInterrupt:
            sys.exit(0)