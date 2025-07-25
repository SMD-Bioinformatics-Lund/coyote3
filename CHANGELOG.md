# Changelog

## v3.0.3
### Report Filename Update
- Report should follow a naming structure of <CASE_ID>_<CLARITY_CASE_ID>-<CONTROL_ID>_<CLARITY_CONTROL_ID>.<REPORT_NUM>.html for paired samples and <CASE_ID>_<CLARITY_CASE_ID>.<REPORT_NUM>.html for unpaired samples.
- static files cleanup -> css, icons, images
- replaced groups with assays where needed
- 

## v3.0.2
### BugFix
Fixed an IndexError in the variant summary generation logic where an empty germline intersection caused the summary view to crash. Now safely handles cases with no overlapping germline variants.


## v3.0.1
### BugFix
hotfix: report paired status key update - replaced `sample_num` with the correct key `sample.sample_no` to get the number of samples (case/control)

## v3.0.0
### Added
- Initial release.- Initial release.
- User authentication and authorization.
- Admin dashboard for managing data.
- Responsive UI with modern design.
- Real-time notifications.
- Comprehensive logging and error handling.
- New database schema with optimized queries.
- RBAC (Role-Based Access Control) for user permissions.
- Configurable settings for assays, configs, genelists, etc via UI.