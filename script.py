import xbmcaddon
import xbmcgui
import xbmc
import sys
import base64
import urllib

my_addon = xbmcaddon.Addon()

def log (str, level = xbmc.LOGDEBUG ):
    xbmc.log(str, level=level)

def container_items ( properties, container = None ):
    cid = ( '(%s)' % container ) if container is not None else ''

    num_items = int(xbmc.getInfoLabel("Container%s.NumAllItems" % cid))

    for i in range(num_items):
        item = dict()

        for prop_name in properties:
            label_name = 'Container%s.ListItemAbsolute(%s).%s' % ( cid, i, prop_name )

            item[prop_name] = xbmc.getInfoLabel( label_name )

        yield item

def get_control_id ( content ):
    if content == 'videos':
        return 50
    elif content == 'episodes':
        return 51
    elif content == 'tvshows' or content == 'movies':
        return 52


def get_server_url ():
    address = my_addon.getSetting( 'address' )
    port = my_addon.getSetting( 'port' )

    return 'http://%s:%s/api' % ( address, port )

def api_request(url, params = {}):
    import json
    import urllib
    import urllib.request

    url = "%s/%s" % (get_server_url(), url)

    with urllib.request.urlopen( url ) as resp:
        content = resp.read()

    return json.loads( content )

if __name__ == '__main__':
    if len(sys.argv) >= 3:
        command = sys.argv[ 1 ]

        if command == 'autoselect':
            target_page = sys.argv[ 2 ]
            target_label = base64.b64decode(sys.argv[ 3 ]).decode('utf-8')

            for i in range(20):
                xbmc.sleep(200)

                win = xbmcgui.Window(xbmcgui.getCurrentWindowId())

                page_path = xbmc.getInfoLabel('Container.FolderPath')

                if page_path != target_page:
                    continue

                try:
                    controlId = get_control_id(xbmc.getInfoLabel('Container.Content'))
                    control = win.getControl(controlId)

                    log('Focused %s:%s' % (controlId, win.getFocusId()))

                    has_items = False

                    if isinstance(control, xbmcgui.ControlList):
                        for i, item in enumerate(container_items( [ 'Label' ] )):
                            if item['Label'] == target_label:
                                control.selectItem( i )
                                has_items = True
                                break

                    if has_items:
                        break
                except:
                    pass
        elif command == 'play-previous':
            receiver = my_addon.getSetting( 'receiver' ) or None

            api_request('/player/%s/play/previous' % (urllib.parse.quote(receiver)))
        elif command == 'play-next':
            receiver = my_addon.getSetting( 'receiver' ) or None

            api_request('/player/%s/play/next' % (urllib.parse.quote(receiver)))
