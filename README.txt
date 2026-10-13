CivicLens site folder
  index.html                      the website
  data/air.json                   placeholder; the robot overwrites it with live data
  scripts/fetch_air.py            downloads CPCB air quality via data.gov.in
  .github/workflows/refresh.yml   runs the script every 3 hours on GitHub
Upload this whole folder to a GitHub repository, keeping the folder names exactly.
