# AEOS-LIVE-002A — Business profile and targeted market discovery

## Scope

LIVE-002A adds a JSON business profile to the existing deterministic LIVE
assessment flow. It reuses `BusinessInput`, the evidence contracts, the
`assess_business` use case, and the one-request Overpass adapter. The supported
Overpass mapping remains the documented HOUSE_CLEANING pilot mapping from
[LIVE-001C](AEOS-LIVE-001C.md). Other verticals are accepted as profiles but
are not searched until their categories have documented mappings.

The adapter searches named country, state/region, city, and additional service
areas in one Overpass request. It does not turn an owner-entered service radius
into a distance circle. The profile contains no verified business coordinate,
and this phase adds no geocoding provider. The report preserves the declared
radius, explains that it was not applied, and records which named areas were
searched. Areas returned by OSM may not match the owner's actual service
boundary.

## Evidence and classification

- Profile facts are recorded as `REPORTED`; a supplied website or service area
  is not thereby verified.
- Provider fields are `OBSERVED`; relationship interpretations are
  `INFERRED` and include their assumptions.
- `craft=cleaning` remains an unqualified cleaning-services listing. It is not
  called a residential cleaning competitor without matching observed service,
  customer-segment, coverage, and business-model evidence.
- Property management listings may appear as customer candidates and as
  possible referral channels. Neither role confirms a current need, a buyer,
  nor an existing relationship.
- The benchmark requires at least two competitors supported across all four
  comparison dimensions. Otherwise it reports
  `INSUFFICIENT_COMPARABLE_DATA` and lists the missing evidence.
- No market gap, sales intent, revenue, price, stock, or supplier term is
  estimated from directory inclusion or absence.

The mapped tags, provider terms, and OSM attribution constraints are documented
in [LIVE-001C](AEOS-LIVE-001C.md). This phase adds no provider or runtime
dependency.

## Profiles and execution

- Example profile: `examples/live/business_profiles/orlando_house_cleaning.json`
  (fictional data, marked in the JSON and report).
- Reusable input template: `examples/live/business_profiles/template.json`.
- JSON and Markdown reports default to `artifacts/live/`, which is ignored by
  Git. Use `--output-dir` to select another review directory.
- The previous `--city`, `--state`, and `--industry` Orlando pilot invocation
  remains available when `--profile` is omitted.

From Windows CMD at the repository root:

```cmd
set PYTHONPATH=src && .venv\Scripts\python.exe -m aeos.live.real_demo --profile examples/live/business_profiles/orlando_house_cleaning.json
```

From PowerShell:

```powershell
$env:PYTHONPATH = 'src'; .\.venv\Scripts\python.exe -m aeos.live.real_demo --profile examples/live/business_profiles/orlando_house_cleaning.json
```

The command performs one Overpass request for a supported profile and writes a
JSON and Markdown report. Unit and integration tests use simulated provider
responses; they do not contact Overpass.

## Known information gaps

Overpass does not provide consistent residential service scope, customer
segments, business models, purchase intent, recurring needs, Google Business
Profile URLs, review ratings, commercial differentiators, supplier stock,
pricing, or terms. An owner-declared radius cannot be checked without verified
coordinates. These gaps appear in the report rather than being filled with
assumptions.
