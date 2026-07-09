import QtQuick 2.15
import QtWebEngine 1.10

Rectangle {
    id: root
    color: "#000"
    property string apiKey: ""
    property alias webView: webView
    signal mapClicked(double lat, double lng)
    signal placeNavigateRequested(double lat, double lng, string name)
    signal placeAnnotateRequested(double lat, double lng, string name)

    WebEngineView {
        id: webView
        anchors.fill: parent
        settings.localContentCanAccessRemoteUrls: true
        settings.localContentCanAccessFileUrls: true
        url: "qrc:/web/amap.html?v=2026070701"

        onLoadingChanged: {
            if (loadRequest.status === WebEngineView.LoadSucceededStatus) {
                webView.runJavaScript("window.__carViewApiKey = '" + root.apiKey + "'; startMap();")
            }
        }

        onNavigationRequested: {
            var url = request.url.toString()
            if (url.indexOf("carview://click") === 0) {
                request.action = WebEngineView.IgnoreRequest
                var lat = url.match(/lat=([\d.]+)/)
                var lng = url.match(/lng=([\d.]+)/)
                if (lat && lng) root.mapClicked(parseFloat(lat[1]), parseFloat(lng[1]))
            } else if (url.indexOf("carview://navigate") === 0) {
                request.action = WebEngineView.IgnoreRequest
                var lat = url.match(/lat=([\d.]+)/)
                var lng = url.match(/lng=([\d.]+)/)
                var name = url.match(/name=([^&]+)/)
                if (lat && lng) {
                    root.placeNavigateRequested(parseFloat(lat[1]), parseFloat(lng[1]),
                                                name ? decodeURIComponent(name[1]) : "")
                }
            } else if (url.indexOf("carview://annotate") === 0) {
                request.action = WebEngineView.IgnoreRequest
                var lat = url.match(/lat=([\d.]+)/)
                var lng = url.match(/lng=([\d.]+)/)
                var name = url.match(/name=([^&]+)/)
                if (lat && lng && name) {
                    root.placeAnnotateRequested(parseFloat(lat[1]), parseFloat(lng[1]),
                                                decodeURIComponent(name[1]))
                }
            }
        }
    }

    function updatePosition(lat, lng) {
        webView.runJavaScript("tryPos(" + lat + "," + lng + ")")
    }

    function clearTrajectory()         { webView.runJavaScript("clearTrajectory()") }
    function showWaypoint(lat, lng)    { webView.runJavaScript("showWaypoint(" + lat + "," + lng + ")") }
    function clearWaypoints()          { webView.runJavaScript("clearWaypoints()") }
    function showPlaces(json) {
        var s = json.replace(/\\/g, '\\\\').replace(/'/g, "\\'")
        webView.runJavaScript("showPlaces('" + s + "')")
    }

    function replayTrajectory(json) {
        var s = json.replace(/\\/g, '\\\\').replace(/'/g, "\\'")
        webView.runJavaScript("replayTrajectory('" + s + "')")
    }
}
