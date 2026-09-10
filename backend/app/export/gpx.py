from xml.etree.ElementTree import Element, SubElement, tostring

from app.models.responses import RouteResponse


def route_to_gpx(route: RouteResponse, *, name: str = "Bikeable Route") -> str:
    gpx = Element(
        "gpx",
        {
            "version": "1.1",
            "creator": "Bikeable",
            "xmlns": "http://www.topografix.com/GPX/1/1",
        },
    )
    metadata = SubElement(gpx, "metadata")
    SubElement(metadata, "name").text = name

    track = SubElement(gpx, "trk")
    SubElement(track, "name").text = name
    segment = SubElement(track, "trkseg")

    for lon, lat in route.geometry.coordinates:
        point = SubElement(
            segment,
            "trkpt",
            {"lat": f"{lat:.6f}", "lon": f"{lon:.6f}"},
        )
        profile_match = next(
            (sample for sample in route.profile if sample.elevation_m is not None),
            None,
        )
        if profile_match and profile_match.elevation_m is not None:
            SubElement(point, "ele").text = f"{profile_match.elevation_m:.1f}"

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(
        gpx, encoding="unicode"
    )
