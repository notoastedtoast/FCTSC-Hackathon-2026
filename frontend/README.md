# Frontend

The FastAPI app serves this directory at `/` when running `make run`.

- `index.html` contains the analysis form, two separate result panels, library filters,
  and the scam-detail dialog.
- `app.js` calls only `POST /analyze`. The backend owns the sequential Detective then
  Cô tâm lý flow; there is no character-chat request.
- `scam-library.json` contains the twelve filterable scam-library entries.
- `styles.css` provides the responsive presentation.

The Cô tâm lý panel is populated only when `/analyze` returns `character` or
`character_notice`; safe results explain that the second AI call was not activated.
