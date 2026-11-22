# Add “My commits” to @DARHWOLF's GitHub profile

This adds an auto-updating visual panel to your existing profile README, without changing the existing PR updater.

## Install

1. Open your profile repository: https://github.com/DARHWOLF/DARHWOLF
2. Copy the files from this package into the repository, preserving paths:
   - `README.md` (updated with the new section)
   - `.github/workflows/update-commits.yml`
   - `scripts/update_commits.py`
   - `assets/my-commits.svg`
3. Commit these files on the repository's **default branch** (`main`).
4. In GitHub, go to **Actions → Update My Commits → Run workflow**. It will fetch public push activity, update the SVG and add clickable repository links to the README.
5. Verify that GitHub Actions has permission to push: **Settings → Actions → General → Workflow permissions → Read and write permissions**. Your organization or repository policies may control this setting.

## Behavior and limitations

- Displays up to four repositories with the most recent public pushes.
- Each card includes repository name, latest push's commit subject when available, last pushed date, branch and number of **push events** (not a lifetime total of commits).
- Public events are subject to GitHub's 30-day / 300-event limit and may be delayed by hours; private repositories and local unpushed commits cannot appear.
- Updates every 6 hours using the built-in `GITHUB_TOKEN`; no personal access token is needed.
- Excludes the `DARHWOLF/DARHWOLF` profile repo to avoid showing the automation's own updates.
- Existing `OPEN_PRS` and `MERGED_PRS` sections remain present.
- Does not modify your live GitHub repository until you commit the files yourself (or authorize a connected GitHub integration to do it).
