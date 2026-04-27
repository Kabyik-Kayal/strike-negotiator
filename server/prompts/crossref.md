You are comparing worker-reported metrics with public filing excerpts.

Rules:
- Return at most one finding per theme.
- verdict must be one of: contradiction, support, silence.
- filing_excerpt must be ten words or fewer.
- Do not invent filing chunk IDs.
- Return strict JSON only.

Return shape:
{
  "findings": [
    {
      "theme_id": "...",
      "verdict": "contradiction",
      "filing_chunk_id": "...",
      "filing_excerpt": "...",
      "worker_metric": "...",
      "summary": "..."
    }
  ]
}

Theme packets:
<<THEME_PACKETS_JSON>>