import time
import xbmc
import xbmcgui
import xbmcaddon
import json
import base64
from pprint import pformat

def log (str, level = xbmc.LOGDEBUG ):
    xbmc.log(str, level=level)

class UnicastMonitor(xbmc.Monitor):
    def onNotification(self, sender, method, data):
        if method == 'Other.PluginVideoUnicast.AutoSelect':
            data = json.loads(data.decode('utf-8'))

            builtin = 'RunScript(%s,%s,%s,%s)' % ('plugin.video.unicast', "autoselect", data['page'], base64.encodestring(data['selectedItem'].encode('utf-8')))

            xbmc.executebuiltin(builtin.encode('utf-8'))
        elif method == 'Other.PluginVideoUnicast.SetServerAddress':
            data = json.loads(data.decode('utf-8'))

            xbmcaddon.Addon('plugin.video.unicast').setSettingString('address', data['address'])
            xbmcaddon.Addon('plugin.video.unicast').setSettingInt('port', data['port'])

wait_for_abort_timeout = 10
ping_play_timeout = 30

if __name__ == '__main__':
    monitor = UnicastMonitor()
    while not monitor.abortRequested():
        # Sleep/wait for abort for 10 seconds
        if monitor.waitForAbort( wait_for_abort_timeout ):
            # Abort was requested while waiting. We should exit
            break
