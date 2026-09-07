# GitHub and HACS setup

1. Complete every blocking item in `PUBLICATION_CHECKLIST.md`.
2. Create `powerassistant/ha-siemens-sentron` as a public GitHub repository.
3. Push this repository tree to the default branch.
4. Configure the repository description, topics, Issues, private vulnerability reporting and branch protection.
5. Wait for the Repository, HACS, Hassfest and runtime-import jobs to pass on
   the exact final commit.
6. Create the immutable tag `V26.09.08` on that commit and publish a full,
   non-draft, non-prerelease GitHub Release titled
   `V26.09.08: VersiCharge load-safety redesign`.
7. Add the repository URL to HACS as a custom integration and test installation plus upgrade.
8. Submit to the HACS default catalog only after the custom-repository release is stable.

No `zip_release` option is configured in `hacs.json`. HACS therefore installs the standard `custom_components/siemens_sentron` subtree from the GitHub release source. Do not attach a separately packaged integration ZIP.

Use `docs/RELEASE_NOTES_V26.09.08.md` as the release body. Never rewrite or
move a published tag; prepare the manifest, changelog and release notes before
tagging.
