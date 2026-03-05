# Corpus Metrics

Measured against `data/` using `scripts/validate_corpus.py`:

- Indexed COBOL-like files: `96`
- Non-comment LOC: `249,351`
- Minimum target: `>= 50 files`, `>= 10,000 LOC`
- Status: `PASS`

Command:

```bash
python scripts/validate_corpus.py --codebase data --min-files 50 --min-loc 10000
```
