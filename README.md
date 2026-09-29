# Letterboxd Movie Analyzer 🎬

A Python tool that analyzes a Letterboxd movie watch history and calculates how much time you've spent watching movies.

It uses the [TMDB API](https://www.themoviedb.org/) to retrieve movie runtimes.

## Features

- 🎬 Count total movies watched
- ⏱️ Calculate total viewing time in minutes, hours, and days
- 📊 Calculate average and median movie runtime
- 🏆 Find the longest and shortest movie
- 📅 Analyze movies watched by year
- 🗓️ Analyze movies watched by month
- 📈 Generate movie-watching graphs
- 🎞️ Categorize movies by runtime
- ⚡ Process multiple TMDB requests concurrently
- 🔄 Automatically retry temporary network/API failures
- 💾 Cache successful runtime lookups
- ▶️ Resume after interruption
- 📝 Save an updated CSV containing movie runtimes

## Requirements

- Python 3.10+
- A TMDB API key
- A Letterboxd `watched.csv` export

## Installation

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/letterboxd-movie-analyzer.git
cd letterboxd-movie-analyzer
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

## TMDB API Key

Create a TMDB account and obtain an API key.

Open `movie_analyzer.py` and find:

```python
TMDB_API_KEY = "YOUR_NEW_TMDB_API_KEY"
```

Replace the placeholder with your own API key.

### ⚠️ Keep your API key private

Do **not** commit your API key to GitHub.

The repository's `.gitignore` already excludes common secret files, but you should still make sure the key is not present in any committed file before pushing.

For a public repository, a better long-term approach is to store the key in an environment variable rather than directly in the Python file.

## Letterboxd Data

Export your Letterboxd watch history and place the resulting:

```text
watched.csv
```

in the project directory.

Your CSV should contain at least:

- `Name`
- `Year`
- `Date`

`watched.csv` is intentionally excluded from Git because it represents personal watch-history data.

## Run

```bash
python movie_analyzer.py
```

The program will look up the runtime of each movie using TMDB.

It uses multiple workers to process movies concurrently, making the lookup significantly faster than processing every movie sequentially.

## Output

The program creates:

```text
watched_with_runtimes.csv
movies_per_year.png
hours_per_year.png
runtime_distribution.png
runtime_cache.json
```

These generated files are excluded from Git where appropriate.

### Example statistics

```text
Movies watched:          522
Runtimes found:          522
Total minutes:           XXXX
Total hours:             XXXX
Total days:              XX.XX
Average movie:           XXX.X minutes
Median movie:            XXX.X minutes
```

## Project Structure

```text
letterboxd-movie-analyzer/
│
├── movie_analyzer.py
├── requirements.txt
├── README.md
└── .gitignore
```

Personal/generated files such as `watched.csv` and the runtime cache are kept locally and are not uploaded to GitHub.

## How It Works

For each movie in the Letterboxd CSV:

1. Search TMDB for the movie.
2. Match the closest release year.
3. Retrieve the movie's runtime.
4. Cache the runtime locally.
5. Add the runtime to the output CSV.
6. Use the collected runtimes to calculate viewing statistics.

The program also retries temporary connection, timeout, SSL, and TMDB server errors.

## Future Ideas

Some possible extensions:

- Genre statistics
- Directors with the most films watched
- Decade breakdown
- Country/language breakdown
- Monthly viewing trends
- Rating analysis
- Letterboxd rating vs. personal rating
- Interactive dashboard

## License

MIT
