# AI-SEO-Analysis
A SEO auditing script that automatically scrapes a website’s content and structure, compiles the data into a clean CSV, ready for use with a custom-tailored prompt and a language model (LLM) of your choice to deliver a complete SEO report.
Report includes:
- Technical Health Check (broken links, meta tag issues, structure)

- Content & Readability Analysis

- Keyword Gap & Opportunity Detection

- Actionable SEO Recommendations

I originally built this tool for my own websites. If you're using it on a site you don’t own, check that you’re not violating the site's Terms of Service as some websites prohibit scraping.

Note: You must install the following packages before running this script.
pip install requests beautifulsoup4 pandas selenium webdriver-manager

There’s also a second version of this script (OpenAI-Seo-Analysis.py) that runs the full process automatically using the OpenAI API.
To use it, make sure to add your own OpenAI API key and install the following packages before running the script.
pip install selenium webdriver-manager beautifulsoup4 pandas openai tiktoken

Have fun optimizing!
