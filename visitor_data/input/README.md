# Visitor pipeline inputs

Place the source files here before running `visitor/VisitorData_local.ipynb`:

```text
visitor_data/input/
├── archive.zip
└── StoreVisit/
    ├── first-file.parquet
    ├── second-file.parquet
    └── ...
```

The notebook writes results to `visitor_data/output/` and DuckDB spill files
to `visitor_data/work/`. Nothing is written to Google Drive.
