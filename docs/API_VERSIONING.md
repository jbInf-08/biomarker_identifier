## API Versioning

This project exposes both unversioned and versioned REST endpoints to match
the Week 9 API versioning plan.

### Versions

- **v1** – current stable API
- **v2** – alias endpoints intended for forward-compatible evolution

### Routing

Core routes are available at:

- Unversioned:
  - `/api/biomarkers`
  - `/api/analysis`
  - `/api/data`
  - `/api/clinical`
  - `/api/auth`
- Versioned:
  - `/api/v1/system`
  - `/api/v2/biomarkers`
  - `/api/v2/analysis`
  - `/api/v2/data`
  - `/api/v2/clinical`
  - `/api/v2/auth`
  - `/api/v2/system`

Both v1 and v2 paths currently route to the same handlers; v2 paths exist to
support future non-breaking evolution while maintaining backward compatibility
for existing clients.

### Version Header

The helper in `backend/app/core/versioning.py` reads an optional
`X-API-Version` header and normalizes it to a supported version (`v1` or
`v2`). This can be used by endpoints to apply version-specific behavior
without changing URLs.

