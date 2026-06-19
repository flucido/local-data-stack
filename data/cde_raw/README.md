# CDE raw data drop folder

Place manually downloaded California Department of Education (CDE) downloadable
data files here. They are typically **pipe-delimited (`|`) `.txt`** files.

Source: https://www.cde.ca.gov/ds/ad/downloadabledata.asp

## What to download (last 5 school years)

Prioritized domains (all ~16 are in scope; these are the highest-signal first):

- Absenteeism (chronic absenteeism counts/rates)
- Annual Enrollment
- Discipline (suspensions/expulsions, restraint/seclusion)
- Graduate and Dropout
- Assessment (CAASPP, ELPAC)
- FRPM / CALPADS UPC (free-reduced meals, unduplicated pupil count)
- English Learners
- Special Education
- Foster Youth
- Homeless
- Stability Rate
- Post-Secondary Enrollment
- Staff
- Accountability (Dashboard)

### Dashboard downloadable files

In addition to the raw data files above, the CDE publishes **pre-computed
Dashboard data files** that contain Status, Change, Performance Color (Red→Blue),
and 5×5 box placement for each state indicator. These are the authoritative
source for the California School Dashboard and are what the Rill dashboards
consume:

- `chronicdownloadYYYY.txt` — Chronic Absenteeism Indicator
- `suspdownloadYYYY.txt` — Suspension Rate Indicator
- `eladownloadYYYY.txt` — Academic Indicator (ELA)
- `elpidownloadYYYY.txt` — English Learner Progress Indicator (ELPI)

Source: https://www.cde.ca.gov/ta/ac/cm/he30rpt.asp

These files use **Style B** column naming (lowercase, pre-concatenated 14-char
CDS code, student-group codes like ALL/AA/HI/EL/SWD) and are loaded into the
`cde_raw` schema as `cde_chronic_absenteeism_dashboard`, `cde_suspension_dashboard`,
`cde_ela_dashboard`, and `cde_elpac_dashboard`. The dbt export views
(`rill_cde_*.sql`) clean, type-cast, and label these for Rill consumption.

## Conventions

- Keep the original filenames from CDE (they encode year + domain).
- One subfolder per domain is fine but not required; the loader will detect file type.
- These raw files are git-ignored by default (see repo .gitignore). Do not commit
  large raw files unless intentionally tracked via Git LFS.

## Notes for the loader (Phase 1)

- Delimiter: `|`
- Suppressed cells: `*` → should be parsed as NULL
- Levels in one file: state / county / district / school (filter via CDS code parts)
- Disaggregation: race/ethnicity, gender, program subgroup, grade span
