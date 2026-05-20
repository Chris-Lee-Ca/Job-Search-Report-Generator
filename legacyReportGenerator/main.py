import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re

# ==========================================================
# CONFIG
# ==========================================================

INPUT_FILE = "jobs.md"
OUTPUT_FILE = "job_report.md"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ==========================================================
# HELPERS
# ==========================================================

def clean_text(text):

    if not text:
        return ""

    return re.sub(r"\s+", " ", text).strip()


# ==========================================================
# EXTRACT JOB LINKS FROM MARKDOWN
#
# Supports:
#
# [Stripe -- Frontend Engineer](https://...)
#
# ==========================================================

def extract_job_links(markdown_text):

    pattern = r"(https?://[^\s]+|linkedin\.com/[^\s]+)"

    matches = re.findall(pattern, markdown_text)

    cleaned_links = []

    for url in matches:

        url = url.strip()

        # add https if missing
        if url.startswith("linkedin.com"):
            url = "https://" + url

        cleaned_links.append(url)

    return cleaned_links

# ==========================================================
# FETCH PAGE
# ==========================================================

def fetch_job_page(url):

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()

        return response.text

    except Exception as e:

        print(f"Failed to fetch: {url}")
        print(e)

        return None


# ==========================================================
# PARSE LINKEDIN JOB PAGE
# ==========================================================

def parse_linkedin_job(html):

    soup = BeautifulSoup(html, "html.parser")

    company = None
    title = None
    location = None
    employment_type = None
    salary = None

    # ------------------------------------------------------
    # TITLE
    # ------------------------------------------------------

    title_tag = soup.find("h1")

    if title_tag:
        title = clean_text(title_tag.get_text())

    # ------------------------------------------------------
    # COMPANY
    # ------------------------------------------------------

    company_tag = soup.find(
        "a",
        class_=re.compile("topcard__org-name-link")
    )

    if not company_tag:

        company_tag = soup.find(
            "span",
            class_=re.compile("topcard__flavor")
        )

    if company_tag:
        company = clean_text(company_tag.get_text())

    # ------------------------------------------------------
    # LOCATION
    # ------------------------------------------------------

    location_tag = soup.find(
        "span",
        class_=re.compile("topcard__flavor--bullet")
    )

    if location_tag:
        location = clean_text(location_tag.get_text())

    # ------------------------------------------------------
    # DESCRIPTION
    # ------------------------------------------------------

    description = ""

    desc_tag = soup.find(
        "div",
        class_=re.compile("show-more-less-html")
    )

    if desc_tag:
        description = clean_text(desc_tag.get_text())

    # ------------------------------------------------------
    # EMPLOYMENT TYPE
    # ------------------------------------------------------

    employment_keywords = [
        "Full-time",
        "Part-time",
        "Contract",
        "Internship",
        "Temporary",
        "Hybrid",
        "Remote",
    ]

    for keyword in employment_keywords:

        if keyword.lower() in description.lower():

            employment_type = keyword
            break

    # ------------------------------------------------------
    # SALARY
    # ------------------------------------------------------

    salary_match = re.search(
        r"(\$[\d,]+(?:\s*-\s*\$[\d,]+)?(?:\/year|\/hr| per year| annually)?)",
        description,
        re.IGNORECASE,
    )

    if salary_match:
        salary = salary_match.group(1)

    return {
        "company": company or "Unknown Company",
        "title": title or "Unknown Title",
        "location": location,
        "employment_type": employment_type,
        "salary": salary,
        "description": description,
    }


# ==========================================================
# SUMMARY EXTRACTION
# ==========================================================

def summarize_description(description, max_items=4):

    keywords = [
        "develop",
        "build",
        "design",
        "maintain",
        "collaborate",
        "experience",
        "python",
        "react",
        "javascript",
        "typescript",
        "api",
        "cloud",
    ]

    summary = []

    sentences = re.split(r"(?<=[.!?])\s+", description)

    for sentence in sentences:

        if any(
            keyword.lower() in sentence.lower()
            for keyword in keywords
        ):

            cleaned = clean_text(sentence)

            if 25 < len(cleaned) < 220:
                summary.append(cleaned)

        if len(summary) >= max_items:
            break

    return summary


# ==========================================================
# GENERATE MARKDOWN REPORT
# ==========================================================

def generate_report(job_links):

    today = datetime.now().strftime("%B %d, %Y")

    report = [f"# {today}\n"]

    for index, url in enumerate(job_links, start=1):

        print(f"Processing {index}: {url}")

        html = fetch_job_page(url)

        # --------------------------------------------------
        # FAILED FETCH
        # --------------------------------------------------

        if not html:

            report.append(
                f"""
{index}. Unknown Company -- Unable to retrieve job details | {url}

<details>
<summary>Brief Details</summary>

- Other Important Notes:
  - Failed to retrieve job posting.

</details>
"""
            )

            continue

        # --------------------------------------------------
        # PARSE JOB
        # --------------------------------------------------

        job = parse_linkedin_job(html)

        summary_lines = summarize_description(
            job["description"]
        )

        # --------------------------------------------------
        # HEADER
        # --------------------------------------------------

        report.append(
            f"""
{index}. {job['company']} -- {job['title']} | {url}

<details>
<summary>Brief Details</summary>
"""
        )

        # --------------------------------------------------
        # LOCATION
        # --------------------------------------------------

        if job["location"]:
            report.append(
                f"\n- Location: {job['location']}"
            )

        # --------------------------------------------------
        # EMPLOYMENT TYPE
        # --------------------------------------------------

        if job["employment_type"]:
            report.append(
                f"\n- Employment Type: {job['employment_type']}"
            )

        # --------------------------------------------------
        # SUMMARY
        # --------------------------------------------------

        if summary_lines:

            report.append(
                "\n- Key Responsibilities / Qualifications:"
            )

            for line in summary_lines:

                report.append(f"  - {line}")

        # --------------------------------------------------
        # SALARY
        # --------------------------------------------------

        if job["salary"]:

            report.append(
                f"\n- Salary: {job['salary']}"
            )

        # --------------------------------------------------
        # CLOSE DETAILS
        # --------------------------------------------------

        report.append(
            """

</details>
"""
        )

    return "\n".join(report)


# ==========================================================
# OPTIONAL:
# CONVERT REPORT TO MARKDOWN HYPERLINKS
#
# Example:
#
# Stripe -- Frontend Engineer | https://...
#
# ->
#
# [Stripe -- Frontend Engineer](https://...)
#
# ==========================================================

def convert_to_markdown_links(text):

    lines = text.splitlines()

    converted = []

    pattern = r"^(.*?)\s*\|\s*(https?://.+)$"

    for line in lines:

        line = line.strip()

        if not line:
            converted.append("")
            continue

        match = re.match(pattern, line)

        if match:

            title = match.group(1).strip()
            url = match.group(2).strip()

            converted.append(
                f"[{title}]({url})"
            )

        else:
            converted.append(line)

    return "\n".join(converted)


# ==========================================================
# MAIN
# ==========================================================

if __name__ == "__main__":

    # ------------------------------------------------------
    # READ MARKDOWN FILE
    # ------------------------------------------------------

    with open(INPUT_FILE, "r", encoding="utf-8") as f:

        markdown_text = f.read()

    # ------------------------------------------------------
    # EXTRACT URLS
    # ------------------------------------------------------

    job_links = extract_job_links(markdown_text)

    print(f"Found {len(job_links)} job links")

    # ------------------------------------------------------
    # GENERATE REPORT
    # ------------------------------------------------------

    report = generate_report(job_links)

    # ------------------------------------------------------
    # OPTIONAL:
    # Convert "Title | URL"
    # into markdown hyperlink format
    # ------------------------------------------------------

    report = convert_to_markdown_links(report)

    # ------------------------------------------------------
    # SAVE REPORT
    # ------------------------------------------------------

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:

        f.write(report)

    print(f"\nSaved report to: {OUTPUT_FILE}")