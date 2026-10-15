param(
    [ValidateSet("test", "smoke", "sync", "export", "check", "help")]
    [string]$Command = "help"
)

switch ($Command) {
    "test" {
        python -m pytest -q
    }
    "smoke" {
        python -c "from scraper import fetch_directory_letter, filter_exhibitors_by_event; from config import EVENTS; config=EVENTS['GIFA']; records=fetch_directory_letter('a', config); exhibitors=filter_exhibitors_by_event(records, config['event_label']); print('GIFA', config['edition'], 'directory records:', len(records), 'matching profiles:', len(exhibitors))"
    }
    "sync" {
        python -c "from scraper import sync_configured_events; sync_configured_events()"
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
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
        Write-Host "Usage: .\md-sync.ps1 <command>"
        Write-Host "  test    Run the complete test suite"
        Write-Host "  smoke   Test the live GIFA API"
        Write-Host "  sync    Synchronize GIFA, METEC, THERMPROCESS, and NEWCAST records"
        Write-Host "  export  Export records to Excel"
        Write-Host "  check   Compile Python and check the diff"
    }
}
