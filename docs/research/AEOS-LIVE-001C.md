# AEOS-LIVE-001C: Orlando live discovery pilot

## Provider decision

The pilot uses OpenStreetMap data through the public Overpass instance hosted at
`https://maps.mail.ru/osm/tools/overpass/api/interpreter`. The OpenStreetMap
Overpass instance list describes that operator's policy as permitting use in any
project and reports no request limit. The pilot still makes only one HTTP
request, identifies itself as `AEOS-LIVE-001C/1.0`, limits each tag search to
five elements, caps the response at 2 MB, times out after 25 seconds, and never
retries. These settings are for this one-off internal run, not a production
service commitment.

OpenStreetMap data is licensed under ODbL 1.0. Reports include the required
`© OpenStreetMap contributors` attribution and a link to the license. Any reuse
or distribution of an OSM-derived database must be reviewed against ODbL
attribution and share-alike requirements. The public endpoint is not treated as
a future paid-SaaS dependency; recurring production use would require a
self-hosted or contracted provider and a fresh terms review.

Google Places was evaluated and not selected. It requires an API key and a
linked billing account, prices requests by SKU, and restricts storing or
redistributing business listing content outside Google services. The pilot
needs local JSON and Markdown review artifacts, and no authorized key or
explicit billing approval was provided. No Google account or billing setup was
attempted.

## Tag mapping

| OSM tags | LIVE classification | Qualification boundary |
|---|---|---|
| `craft=cleaning` | Possible competitor | OSM documents building, industrial, window, or janitorial cleaning generally. It does not prove residential house-cleaning scope. |
| `office=property_management` | Potential customer | Category-based fit only; outsourced need, service demand, authority, and intent remain unknown. |
| `office=estate_agent` or `shop=estate_agent` | Possible partner | Possible referral/channel fit only; no relationship is established. |
| `shop=cleaning_supplies` | Supplier | Product mix, pricing, stock, and supplier terms are unknown. |

The query does not classify apartment building features as organizations, and
does not search for moving or vacation-rental operators because no sufficiently
clear, documented OSM business tag was selected for those categories. The
adapter only retains named elements and deduplicates exact OSM element IDs; it
does not merge similar business names.

## Run the pilot

From the repository root, explicitly run:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m aeos.live.real_demo --city Orlando --state FL --industry HOUSE_CLEANING
```

This executes exactly one Overpass request and then calls the existing
`assess_business` use case with the merged results from the four
`MarketDiscoveryPort` methods. Unit tests inject mocked responses and never run
the live command.

Reports are written locally to `artifacts/live/`, which is git-ignored so live
research data is not committed by accident. Use `--output-dir` to choose a
different review directory.

The pilot uses an approximate Downtown Orlando origin of latitude 28.5383,
longitude -81.3792. It is a 15-mile research circle, not a city boundary or an
individual business's verified service area. Public source fields are preserved
as `OBSERVED`; Overpass center coordinates and calculated distance are labeled
`INFERRED`. The assessment engine requires direct city/state evidence for local
qualification, so entries without mapped `addr:city` and `addr:state` remain
unqualified.

## Provider references

- [Public Overpass instances and usage policies](https://wiki.openstreetmap.org/wiki/Overpass_API)
- [OpenStreetMap attribution and ODbL](https://www.openstreetmap.org/copyright)
- [OSM `craft=cleaning`](https://wiki.openstreetmap.org/wiki/Tag:craft%3Dcleaning)
- [OSM `office=property_management`](https://wiki.openstreetmap.org/wiki/Tag:office%3Dproperty_management)
- [OSM `office=estate_agent`](https://wiki.openstreetmap.org/wiki/Tag:office%3Destate_agent)
- [OSM `shop=cleaning_supplies`](https://wiki.openstreetmap.org/wiki/Tag:shop%3Dcleaning_supplies)
- [Google Places usage and billing](https://developers.google.com/maps/documentation/places/web-service/usage-and-billing)
- [Google Places data policies](https://developers.google.com/maps/documentation/places/web-service/policies)
- [Google Maps Platform pricing](https://developers.google.com/maps/billing-and-pricing/pricing)
