/* Small map helpers shared by the gym page (directions) and the gym owner's map picker.
   Place search = OpenStreetMap Nominatim. Driving route = OSRM public server. Both are free, no API key. */
const Geo = {
  async search(q, limit) {
    const url = 'https://nominatim.openstreetmap.org/search?format=jsonv2&limit=' + (limit || 1) +
                '&countrycodes=ph&q=' + encodeURIComponent(q);
    const r = await fetch(url, { headers: { 'Accept': 'application/json' } });
    if (!r.ok) throw new Error('search failed');
    return (await r.json()).map(function (d) { return { lat: +d.lat, lng: +d.lon, name: d.display_name }; });
  },
  /* try several wordings, most exact first, and return the first place found */
  async first(queries) {
    for (const q of queries) {
      if (!q) continue;
      try { const hits = await Geo.search(q, 1); if (hits.length) return Object.assign({ query: q }, hits[0]); } catch (e) { /* try next */ }
    }
    return null;
  },
  km(a, b) {                                   // straight-line distance (haversine)
    const rad = Math.PI / 180, dLat = (b.lat - a.lat) * rad, dLng = (b.lng - a.lng) * rad;
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2;
    return 12742 * Math.asin(Math.sqrt(h));
  },
  async route(from, to) {
    const url = 'https://router.project-osrm.org/route/v1/driving/' + from.lng + ',' + from.lat + ';' + to.lng + ',' + to.lat +
                '?overview=full&geometries=geojson';
    const r = await fetch(url);
    const d = await r.json();
    if (!d.routes || !d.routes.length) throw new Error('no route');
    return d.routes[0];
  }
};
