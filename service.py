import time
import threading
import xbmc
import xbmcgui
import xbmcaddon
import json
import base64
from pprint import pformat

def log (str, level = xbmc.LOGDEBUG ):
    xbmc.log(str, level=level)

# Widgets add ?reload=$INFO[Window(Home).Property(<name>)] to their path: Kodi reloads a
# widget when its path changes, so changing these properties reloads those widgets only
RELOAD_PROPERTIES = ('Unicast.Reload.Playlists', 'Unicast.Reload.History')
# Seconds to wait after waking from suspend, for the network and the server to come back
WAKE_REFRESH_DELAY = 5

def refresh_tokens(reason):
    token = str(int(time.time() * 1000))
    home = xbmcgui.Window(10000)
    for name in RELOAD_PROPERTIES:
        home.setProperty(name, token)
    log('Unicast: widget reload tokens refreshed (%s): %s' % (reason, token))

class UnicastMonitor(xbmc.Monitor):
    def onScreensaverDeactivated(self):
        refresh_tokens('screensaver')

    def onNotification(self, sender, method, data):
        if method == 'System.OnWake':
            timer = threading.Timer(WAKE_REFRESH_DELAY, refresh_tokens, ('wake',))
            timer.daemon = True
            timer.start()
        elif method == 'Other.PluginVideoUnicast.AutoSelect':
            data = json.loads(data)

            builtin = 'RunScript(%s,%s,%s,%s)' % ('plugin.video.unicast', "autoselect", data['page'], base64.b64encode(data['selectedItem'].encode('utf-8')).decode('ascii'))

            xbmc.executebuiltin(builtin)
        elif method == 'Other.PluginVideoUnicast.SetServerAddress':
            data = json.loads(data)

            if 'url' in data:
                url = data['url']
            else:
                # Legacy payload: separate address and port
                url = 'http://%s:%s' % (data['address'], data['port'])

            xbmcaddon.Addon('plugin.video.unicast').setSettingString('url', url)

wait_for_abort_timeout = 10
ping_play_timeout = 30

if __name__ == '__main__':
    monitor = UnicastMonitor()
    while not monitor.abortRequested():
        # Sleep/wait for abort for 10 seconds
        if monitor.waitForAbort( wait_for_abort_timeout ):
            # Abort was requested while waiting. We should exit
            break
