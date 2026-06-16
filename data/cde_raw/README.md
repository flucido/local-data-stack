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
