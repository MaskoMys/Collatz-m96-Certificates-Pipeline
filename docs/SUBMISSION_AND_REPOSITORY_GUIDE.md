# Submission and repository guide

This guide explains how to verify, publish, archive, and submit the accompanying
paper and certificate package. The steps are written so that no specialist
software knowledge is required beyond copying terminal commands.

## 1. Keep one untouched release folder

1. Make a backup copy of the complete release folder.
2. Do all tests in one working copy.
3. After the final SHA-256 manifest is generated, do not edit files in the
   release folder. Any edit changes the archive hash and should create a new
   version number.

## 2. Verify the package locally

Open a terminal in the release folder and run:

```bash
python3 -B verify_all.py
```

A successful run ends with a clear success message. This command checks the
whole-file manifest, exact analytic certificates, the 75-branch cover and raw
logs, the frontier/descent certificates, and adversarial verifier tests.

For a fresh full recomputation of the expensive `m=96` search, install a C++
compiler and GMP development files, then run:

```bash
g++ -O3 -std=c++17 code/m96/affine_ladder_prefix.cpp -lgmpxx -lgmp \
  -o affine_ladder_prefix
python3 code/m96/run_tasks.py \
  --exe ./affine_ladder_prefix \
  --tasks certificates/m96_tasks.jsonl \
  --out reproduced_m96_runs \
  --jobs 8 --timeout 14400
python3 code/m96/verify_branch_certificate.py \
  --tasks certificates/m96_tasks.jsonl \
  --runs reproduced_m96_runs \
  --source code/m96/affine_ladder_prefix.cpp
```

The number after `--jobs` is the number of branches run at once. Use half to
all of the available CPU cores. The fast release check does not require this
rerun because the raw logs are already shipped.

## 3. Create the GitHub repository

1. Sign in to GitHub.
2. Select **New repository**.
3. Use a descriptive name such as
   `prefix-rigidity-collatz-96-cycles`.
4. Choose **Public** so referees can inspect it.
5. Do not ask GitHub to create a second README or license; those files are
   already present.
6. Create the repository.
7. In a terminal, from the release folder, run the commands displayed by
   GitHub. A typical sequence is:

```bash
git init
git add .
git commit -m "Release v2.0.0"
git branch -M main
git remote add origin https://github.com/YOUR-ACCOUNT/YOUR-REPOSITORY.git
git push -u origin main
```

Replace the account and repository placeholders with the names shown by
GitHub.

## 4. Check GitHub Actions

The repository includes a workflow that runs the fast verifier on every push.
Open the **Actions** tab and wait for the verification job to become green. A
green job is useful evidence that the archive works on a clean machine.

## 5. Create the immutable GitHub release

1. Open the repository's **Releases** page.
2. Select **Draft a new release**.
3. Create tag `v2.0.0` from the verified commit.
4. Use the release title
   `Prefix Rigidity and Collatz 96-Cycle Certificate v2.0.0`.
5. State that the release contains the paper, all 75 raw branch logs, exact
   analytic certificates, source code, and verifiers.
6. Attach the complete ZIP archive.
7. Publish the release.

Do not move the tag after publication. A later edit should become a new tag.

## 6. Mint a Zenodo DOI

1. Sign in to Zenodo using the GitHub option.
2. Open Zenodo's **GitHub** integration page.
3. Find the repository and switch archiving **On**.
4. If the GitHub release was made after enabling the switch, Zenodo normally
   archives it automatically. Otherwise create a new patch release after the
   integration is enabled.
5. Open the resulting Zenodo record and check the title, author, description,
   license, and files.
6. Copy both the version DOI and the concept DOI.

GitHub's official documentation explains that Zenodo archives the repository
and issues a new DOI for each GitHub release. Put the version DOI in the paper's
Data Availability statement when possible. If the manuscript has already been
frozen, provide the DOI in the journal submission form and cover letter.

## 7. Suggested repository front page

The README should let a referee find four things immediately:

1. the main theorem;
2. the one-command verifier;
3. the paper PDF;
4. the full recomputation command.

Keep issue tracking enabled so readers can report reproducibility problems.
Use the GitHub release, not the moving `main` branch, as the cited artifact.

## 8. Submit to Experimental Mathematics

This is the recommended first venue because the paper combines a formal
mathematical reduction with an exact, reproducible computer-assisted proof.

Prepare these files:

- `paper/Prefix_Rigidity_Collatz_Circuits.pdf`;
- the LaTeX source if requested by the submission system;
- the cover letter text in `COVER_LETTER.md`;
- the Zenodo DOI and GitHub release URL;
- the complete ZIP as supplementary material if the portal accepts it.

In the submission form:

1. copy the exact title and abstract from the manuscript;
2. enter the author and affiliation exactly as they appear in the paper;
3. use the listed keywords and MSC codes;
4. identify the article as a research article;
5. paste the Data Availability statement and DOI;
6. mention that the proof uses exact integer/rational arithmetic and that all
   raw branch logs are archived;
7. suggest referees only when the journal asks, choosing researchers in
   computational number theory, continued fractions, or Collatz-cycle theory;
8. upload the PDF and supplementary archive;
9. preview every generated page before final submission.

## 9. Alternative: INTEGERS

INTEGERS instructs authors to email a PDF to
`integersjournal@gmail.com`. The accompanying email must provide:

- Mathematical Subject Classification codes;
- keywords;
- confirmation of compliance with the journal's AI-use guideline.

The journal requests its source template after acceptance. Attach or link the
certificate DOI in the email and explain that the full raw archive is too large
to treat as ordinary manuscript source.

## 10. Alternative: Journal of Integer Sequences

The Journal of Integer Sequences requires electronic submission in LaTeX,
12-point font, and says not to send the manuscript PDF. It prefers a single
LaTeX source file and no cover letter. Before using this route:

1. change the document class to 12 point;
2. follow the journal's LaTeX style guide;
3. remove unnecessary packages and comments;
4. make sure the single source file compiles without errors;
5. use the email subject exactly requested by the journal;
6. provide the public certificate DOI in the submission message.

This venue is narrower in scope, so explain the relevance of the continued-
fraction frontier and the exact integer sequences generated by the proof.

## 11. What to tell a referee

A concise reproducibility statement is:

> The fast verifier checks the immutable release, regenerates the analytic
> reduction and task cover, verifies all 75 raw branch logs and metadata files,
> and runs adversarial tests. The exhaustive C++ search can also be rebuilt and
> rerun from source. All mathematical decisions use exact integer or rational
> arithmetic.

The Python branch verifier is an integrity-and-coverage verifier for the raw
logs. The mathematical completeness of the C++ enumeration is separately
proved in `docs/m96/FIXED_BRANCH_COMPLETENESS.md` and audited in
`docs/m96/SOURCE_AUDIT.md`.

## 12. Final pre-submission checklist

- [ ] `python3 -B verify_all.py` succeeds.
- [ ] GitHub Actions is green.
- [ ] The GitHub release tag points to the verified commit.
- [ ] Zenodo has archived the release and issued a DOI.
- [ ] The paper's title, author, abstract, and DOI metadata agree.
- [ ] The manuscript PDF was visually checked page by page.
- [ ] The cover letter states the theorem without claiming a proof of the full
      Collatz conjecture.
- [ ] The supplementary ZIP opens and contains the raw branch archive.
- [ ] No file was edited after the final manifest was generated.
