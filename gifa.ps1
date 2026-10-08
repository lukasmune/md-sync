param(
    [ValidateSet("test", "smoke", "sync", "export", "check", "help")]
    [string]$Command = "help"
)

switch ($Command) {
    "test" {
        python -m pytest -q
    }
    "smoke" {
        python -c "from scraper import fetch_directory_letter, filter_exhibitors_by_event; records=fetch_directory_letter('a'); exhibitors=filter_exhibitors_by_event(records, 'GIFA 2023'); print('directory records:', len(records)); print('GIFA 2023 profiles:', len(exhibitors))"
    }
    "sync" {
        foreach ($event in @("GIFA", "METEC", "THERMPROCESS", "NEWCAST")) {
            Write-Host "`nSynchronizing $event..."
            python scraper.py $event
            if ($LASTEXITCODE -ne 0) {
                exit $LASTEXITCODE
            }
        }
    }
    "export" {
        python -c "from excel_export import export_database_to_excel; print(export_database_to_excel('exports'))"
    }
    "check" {
        python -m compileall -q .
        if ($LASTEXITCODE -eq 0) {
            git diff --check
        }
    }
    "help" {
        Write-Host "Usage: .\gifa.ps1 <command>"
        Write-Host "  test    Run the complete test suite"
        Write-Host "  smoke   Test the live GIFA API"
        Write-Host "  sync    Synchronize GIFA, METEC, THERMPROCESS, and NEWCAST records"
        Write-Host "  export  Export records to Excel"
        Write-Host "  check   Compile Python and check the diff"
    }
}