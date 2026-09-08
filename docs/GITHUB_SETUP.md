# Releases and download counts

Starting with `V26.09.10`, HACS downloads the `siemens_sentron.zip` asset attached
to each release. GitHub counts downloads of this file, and the README badge
shows the sum across releases. Updates and repeated downloads are included;
the count is not a count of unique users or active installations. Previous
source-based downloads cannot be added retrospectively.

## Prepare a release

1. Update the version in `custom_components/siemens_sentron/manifest.json`,
   `EXPECTED_VERSION` in `scripts/validate_repository.py`, and the expected
   version in `tests/test_release_contract.py`. Update the changelog.
2. Merge the changes into `main` and let the validation checks finish.
3. On GitHub, open **Actions → Prepare release → Run workflow**. Select `main`,
   enter the same version as a new tag (for example `V26.09.10`), and enter the
   release notes. The workflow runs only from `main`.
4. The workflow runs all four validation jobs, creates the ZIP, and prepares a
   **draft** release with the file attached. The tag points to the exact commit
   that was validated. Do not create the tag separately beforehand.
5. Open **Releases**, review the draft and its `siemens_sentron.zip` attachment,
   and select **Publish release**. HACS can then discover the new version.

Use this workflow to prepare releases: publishing a release before its ZIP is
attached makes that version unavailable for HACS downloads. Older tags retain
their original `hacs.json` and continue to use the source download method.
Existing tags or releases are never overwritten. If a preparation run fails
after creating its tag or draft, inspect that run before retrying.

## View the counts

- The README's **downloads** badge totals downloads of `siemens_sentron.zip`
  across published releases. The badge may take a few minutes to refresh.
- HACS displays the selected release asset's download count.
- For individual release counts, the [GitHub Releases API](https://api.github.com/repos/powerassistant/ha-siemens-sentron/releases)
  includes `download_count` in the `assets` entry named `siemens_sentron.zip`.
- Keep the filename stable. Replacing an uploaded asset resets its individual
  counter; publish a new version instead of overwriting an existing ZIP.

No tracking is added to the integration or to Home Assistant. The counts come
from GitHub's existing release-download statistics.

## Local package verification

After running the repository validator and tests, build outside the checkout:

```bash
python3 scripts/build_release.py --tag V26.09.10 --output /tmp/siemens_sentron.zip
```

The ZIP contains `manifest.json`, `__init__.py` and the other integration files
directly at its root, with `translations/` and `brand/` beneath it. It must not
contain an enclosing `custom_components/` or `siemens_sentron/` directory.
The builder checks the tag against the manifest and refuses to overwrite an
existing output file.
