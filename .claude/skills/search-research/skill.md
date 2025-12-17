# Search Research Materials

Search indexed Zotero and Scrivener content using semantic similarity.

## Parameters

- `query` (string, required): What to search for
- `chapter_number` (integer, optional): Limit to specific chapter
- `source_type` (string, optional): "zotero" or "scrivener"
- `limit` (integer, optional): Max results (default: 20)

## Example

```json
{
  "query": "early firewall implementations at DEC",
  "chapter_number": 2,
  "source_type": "zotero",
  "limit": 10
}
```
