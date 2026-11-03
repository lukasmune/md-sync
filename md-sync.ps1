param(
    [ValidateSet("test", "smoke", "sync", "export", "mailchimp", "mailchimp-rebuild", "mailchimp-baseline", "check", "help")]
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
    "mailchimp" {
        python -c "from mailchimp_export import export_mailchimp_list; path = export_mailchimp_list(); print(path if path else 'No new Mailchimp contacts')"
    }
    "mailchimp-rebuild" {
        python -c "from mailchimp_export import rebuild_mailchimp_list; path = rebuild_mailchimp_list(); print(path if path else 'No earlier Mailchimp export to rebuild')"
    }
    "mailchimp-baseline" {
        python -c "from mailchimp_export import mark_current_contacts_as_exported as m; print('Marked as already exported:', m())"
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
        Write-Host "  export  Export records to Excel (internal, all data)"
        Write-Host "  mailchimp  Write the Mailchimp upload list (new contacts only)"
        Write-Host "  mailchimp-rebuild  Recreate the last Mailchimp list (log unchanged)"
        Write-Host "  mailchimp-baseline  Mark all current contacts as already exported"
        Write-Host "  check   Compile Python and check the diff"
    }
}
