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
        python -c "from scraper import sync_gifa_2023; print(sync_gifa_2023())"
    }
    "export" {
        python -c "from excel_export import export_database_to_excel; print(export_database_to_excel('exports/GIFA_Sales_Database_current.xlsx'))"
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
        Write-Host "  sync    Synchronize current GIFA records"
        Write-Host "  export  Export records to Excel"
        Write-Host "  check   Compile Python and check the diff"
    }
}